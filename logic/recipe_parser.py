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

def analyze_video_content(text: str, language: str = "en", stream: bool = False, **kwargs) -> Optional[Recipe]:
    """
    Analyzes video content to extract a recipe.
    If stream is True, it returns an async generator that yields JSON chunks.
    Otherwise, it will block and return the full recipe (not implemented for streaming focus).
    """
    if stream:
        # This is the streaming path, which is now the primary path.
        return stream_recipe_from_text(
            text, 
            language, 
            thumbnail_path=kwargs.get("thumbnail_path"), 
            frame_paths=kwargs.get("frame_paths")
        )
    else:
        # Non-streaming path, can be implemented if needed but we focus on streaming.
        logger.warning("Non-streaming call to 'analyze_video_content' is not fully implemented.")
        # For now, let's make it work by running the async generator and collecting results.
        # This is inefficient and should be avoided in production.
        import asyncio
        recipe = asyncio.run(_collect_recipe_from_stream(stream_recipe_from_text(text, language)))
        return recipe

async def _collect_recipe_from_stream(stream):
    """Helper to collect the final recipe from a stream."""
    async for chunk in stream:
        if isinstance(chunk, dict) and not chunk.get("error"):
            return chunk
    return None

async def stream_recipe_from_text(text: str, language: str, thumbnail_path: Optional[str] = None, frame_paths: Optional[list] = None):
    """
    Uses a streaming LLM call to generate a recipe, accumulates the response,
    and yields a single, complete JSON object.
    """
    MIN_TEXT_LENGTH = 150
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        logger.warning(f"Input text for LLM is too short ({len(text.strip())} chars).")
        yield {"error": "The video did not contain enough text to create a recipe."}
        return

    logger.info("Starting LLM call for recipe generation...")
    full_response = ""
    try:
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
        )

        prompt_template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a master chef specializing in creating easy-to-follow recipe guides from messy, transcribed text. "
             "Your goal is to extract and structure a complete recipe from the provided transcript. "
             f"The recipe should be in {language}.\n\n"
             "Create a recipe with the following structure:\n"
             "- title: The recipe name\n"
             "- description: A brief description of the dish\n"
             "- servings: Number of people the recipe serves\n"
             "- prep_time: Preparation time\n"
             "- cook_time: Cooking time\n"
             "- ingredients: Array of ingredients with quantity, name, and optional notes\n"
             "- instructions: Array of numbered steps with detailed descriptions. IMPORTANT: This field is REQUIRED and must contain at least 3-5 detailed steps.\n"
             "- chef_tips: Array of professional tips to enhance the recipe\n"
             "- nutritional_information: Basic nutritional data if available\n\n"
             "Return ONLY a valid JSON object with this structure. No markdown, no explanations. Make sure the instructions field is always present and contains detailed steps, even if you have to infer them from the ingredients and context."
            ),
            ("human", "Here is the transcript from a cooking video: {transcript}")
        ])

        chain = prompt_template | llm | StrOutputParser()

        full_response = await chain.ainvoke({"transcript": text, "language": language})
        
        # Extract clean JSON from the potentially markdown-formatted response
        json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
        if not json_match:
            raise json.JSONDecodeError("No JSON object found in the LLM response.", full_response, 0)
        
        json_str = json_match.group(0)
        recipe_json = json.loads(json_str)
        
        if thumbnail_path:
            recipe_json['thumbnail_path'] = thumbnail_path
        
        # Ensure instructions exist and are in the correct format
        if 'instructions' not in recipe_json or not recipe_json['instructions']:
            recipe_json['instructions'] = [
                {"description": "Förbered alla ingredienser enligt listan."},
                {"description": "Blanda ingredienserna enligt receptet."},
                {"description": "Tillaga enligt anvisningarna i videon."}
            ]
        elif isinstance(recipe_json['instructions'], list):
            # Ensure each instruction has the correct format
            formatted_instructions = []
            for i, instruction in enumerate(recipe_json['instructions']):
                if isinstance(instruction, str):
                    formatted_instructions.append({"step": i + 1, "description": instruction})
                elif isinstance(instruction, dict) and 'description' in instruction:
                    instruction['step'] = i + 1
                    formatted_instructions.append(instruction)
                else:
                    formatted_instructions.append({"step": i + 1, "description": f"Steg {i+1}"})
            recipe_json['instructions'] = formatted_instructions
            
        if frame_paths:
            num_steps = len(recipe_json['instructions'])
            num_frames = len(frame_paths)
            if num_steps > 0 and num_frames > 0:
                frames_per_step = num_frames // num_steps
                for i in range(num_steps):
                    frame_index = i * frames_per_step
                    if frame_index < num_frames:
                        recipe_json['instructions'][i]['image_path'] = frame_paths[frame_index]
            
        yield recipe_json

    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from LLM response. Raw response: {full_response}")
        yield {"error": "Failed to parse recipe data. Please try again."}
    except Exception as e:
        logger.error(f"Error during recipe generation: {str(e)}")
        yield {"error": f"Recipe generation failed: {str(e)}"}
    finally:
        logger.info("LLM processing finished.") 