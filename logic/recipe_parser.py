import re
import json
import logging
import os
from typing import Optional, Dict, Any, AsyncGenerator

from langchain_core.prompts import ChatPromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser

from models.types import Recipe, Step
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

def combine_transcripts(audio_transcript: str, ocr_text: Optional[str], description: Optional[str]) -> str:
    """Combines text from audio, OCR, and video description into a single context document."""
    combined = []
    if description and len(description) > 50:
        combined.append(f"Video Description:\n{description}")

    if ocr_text and len(ocr_text) > 20:
        combined.append(f"Text found in video (OCR):\n{ocr_text}")

    if audio_transcript and len(audio_transcript) > 20:
        combined.append(f"Audio Transcript:\n{audio_transcript}")

    logger.info(f"Combined transcripts from {len(combined)} sources.")
    return "\n\n---\n\n".join(combined)

async def analyze_video_content(text: str, language: str = "en", stream: bool = False, **kwargs):
    """
    Analyzes video content to extract a recipe.
    If stream is True, it returns an async generator.
    If stream is False, it returns the complete recipe dictionary.
    """
    stream_generator = stream_recipe_from_text(
        text, 
        language, 
        thumbnail_path=kwargs.get("thumbnail_path"), 
        frame_paths=kwargs.get("frame_paths")
    )

    if stream:
        return stream_generator
    else:
        # Await the helper function to collect the final result from the async generator
        return await _collect_recipe_from_stream(stream_generator)


async def _collect_recipe_from_stream(stream):
    """Helper to collect the final, complete recipe from a stream."""
    last_valid_chunk = None
    async for chunk in stream:
        if isinstance(chunk, dict) and "error" not in chunk:
            last_valid_chunk = chunk  # The last chunk yielded should be the complete one
    return last_valid_chunk

async def stream_recipe_from_text(text: str, language: str, thumbnail_path: Optional[str] = None, frame_paths: Optional[list] = None):
    """
    Uses a streaming LLM call to generate a recipe and yields JSON chunks as they arrive.
    """
    MIN_TEXT_LENGTH = 50  # Lowered from 150 to handle TikTok videos better
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        yield {"error": "The video did not contain enough text to create a recipe."}
        return

    logger.info("Starting streaming LLM call for recipe generation...")
    try:
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
            streaming=True
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a master chef creating recipe guides from transcribed text. "
             f"The recipe must be in {language}.\n\n"
             "IMPORTANT: Even if the transcript is short (like from TikTok videos), use your culinary knowledge to create a complete recipe. "
             "Fill in missing details with reasonable assumptions based on the dish type.\n\n"
             "Structure your response as a single, complete JSON object with these keys:\n"
             "- title: A creative and appealing title for the recipe.\n"
             "- description: A longer, enticing description of the dish, at least 2-3 sentences. Describe the flavors, origin, and why someone should try it.\n"
             "- servings, prep_time, cook_time\n"
             "- ingredients: Array of objects with 'quantity', 'name', 'notes'.\n"
             "- instructions: Array of objects with 'step', 'description'. This is REQUIRED and must be detailed.\n"
             "- nutritional_information: An object with estimated values for 'calories', 'protein', 'carbohydrates', and 'fat'. Also include a 'summary' string.\n"
             "- chef_tips: An array of strings with helpful tips or variations.\n\n"
             "Begin streaming the JSON immediately. Do not use markdown."
            ),
            ("human", "Here is the transcript: {transcript}")
        ])

        chain = prompt_template | llm | StrOutputParser()
        
        buffer = ""
        async for chunk in chain.astream({"transcript": text, "language": language}):
            buffer += chunk
            try:
                # Attempt to parse what we have so far
                partial_json = json.loads(buffer)
                if isinstance(partial_json, dict):
                    # Yield valid partial data
                    yield partial_json
            except json.JSONDecodeError:
                # Continue accumulating if the JSON is not yet complete
                continue
        
        # Final parse and yield
        try:
            # Clean the buffer from markdown and other artifacts
            clean_buffer = re.sub(r'```json\s*|\s*```', '', buffer).strip()
            final_recipe = json.loads(clean_buffer)
            if thumbnail_path:
                final_recipe['thumbnail_path'] = thumbnail_path
            
            # Final validation and formatting
            if 'instructions' in final_recipe:
                formatted_instructions = []
                for i, inst in enumerate(final_recipe['instructions']):
                    if isinstance(inst, str):
                        formatted_instructions.append({"step": i + 1, "description": inst})
                    elif isinstance(inst, dict):
                        inst['step'] = inst.get('step', i + 1)
                        formatted_instructions.append(inst)
                final_recipe['instructions'] = formatted_instructions

            if frame_paths and 'instructions' in final_recipe:
                num_steps = len(final_recipe['instructions'])
                num_frames = len(frame_paths)
                if num_steps > 0 and num_frames > 0:
                    frames_per_step = num_frames // num_steps
                    for i in range(num_steps):
                        frame_index = i * frames_per_step
                        if frame_index < num_frames:
                            final_recipe['instructions'][i]['image_path'] = frame_paths[frame_index]
            
            yield final_recipe
        except json.JSONDecodeError:
            logger.error(f"Final JSON parsing failed. Buffer: {buffer}")
            yield {"error": "Failed to finalize recipe data."}

    except Exception as e:
        logger.error(f"Error during recipe generation: {e}")
        yield {"error": f"Recipe generation failed: {e}"}
    finally:
        logger.info("LLM streaming finished.") 