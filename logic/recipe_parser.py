import os
from dotenv import load_dotenv
from typing import Optional
import json
import traceback
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from models.types import VideoContent, Step

# Load environment variables from .env file
load_dotenv()

# --- AI Configuration ---
# Use a global variable for the model and initialize it lazily
llm = None

def get_llm_instance():
    """Initializes and returns the LLM instance, creating it only if it doesn't exist."""
    global llm
    if llm is None:
        print("Initializing DeepSeek LLM...")
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
            max_tokens=4096,
        )
        print("DeepSeek LLM initialized.")
    return llm

def call_deepseek_api(prompt: str) -> dict:
    """Send prompt to DeepSeek API and get JSON response."""
    try:
        # Get the LLM instance
        active_llm = get_llm_instance()

        messages = [
            SystemMessage(content="You are a helpful assistant that provides JSON responses."),
            HumanMessage(content=prompt)
        ]
        response = active_llm.invoke(messages)
        response_text = response.content
        if response_text.startswith("```json"):
            response_text = response_text[7:-4].strip()
        return json.loads(response_text)
    except Exception as e:
        print(f"Error calling DeepSeek API: {e}")
        traceback.print_exc()
        return {}

def analyze_video_content(text: str, language: str = "en") -> Optional[VideoContent]:
    """Analyze video transcript to extract structured data."""
    prompts = {
        "en": ("You are an expert at analyzing video transcripts. "
               "Your task is to determine the video's type (e.g., 'cooking', 'DIY', 'tutorial'), "
               "extract its title, a list of materials or ingredients, and a step-by-step guide. "
               "The user will provide the transcript of a video. "
               "Format your response as a JSON object with the keys: "
               "'video_type', 'title', 'materials_or_ingredients' (as an array of strings), and 'steps' "
               "(as an array of objects, each with 'step_number', 'action', 'timestamp', and 'explanation'). "
               "Ensure the instructions are clear, concise, and easy to follow. "
               "Focus only on the main steps and filter out any irrelevant chatter."),
        "sv": ("Du är en expert på att analysera videotranskriptioner. "
               "Din uppgift är att bestämma videotypen (t.ex. 'matlagning', 'DIY', 'handledning'), "
               "extrahera dess titel, en lista över material eller ingredienser, och en steg-för-steg-guide. "
               "Användaren kommer att ge dig transkriptionen av en video. "
               "Formatera ditt svar som ett JSON-objekt med nycklarna: "
               "'video_type', 'title', 'materials_or_ingredients' (som en lista med strängar), och 'steps' "
               "(som en lista med objekt, var och en med 'step_number', 'action', 'timestamp' och 'explanation'). "
               "Se till att instruktionerna är tydliga, koncisa och lätta att följa. "
               "Fokusera endast på de huvudsakliga stegen och filtrera bort allt irrelevant prat.")
    }
    
    prompt = prompts.get(language, prompts["en"]) + f"\n\nTranscript:\n{text}"

    try:
        response_data = call_deepseek_api(prompt)
        
        # Add a more detailed validation check
        if not all(k in response_data for k in ['video_type', 'title', 'materials_or_ingredients', 'steps']):
             raise ValueError("AI response is missing required keys.")

        video_content = VideoContent(
            video_type=response_data.get("video_type", "Unknown"),
            title=response_data.get("title", "No Title Provided"),
            materials_or_ingredients=response_data.get("materials_or_ingredients", []),
            steps=[Step(**step) for step in response_data.get("steps", [])]
        )
        return video_content
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error processing AI response: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"An unexpected error occurred in analyze_video_content: {e}")
        traceback.print_exc()
        return None 