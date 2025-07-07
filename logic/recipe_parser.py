import os
from dotenv import load_dotenv
from typing import Optional, Tuple
import json
import traceback
import logging
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from models.types import VideoContent, Step

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- AI Configuration ---
# Use a global variable for the model and initialize it lazily
llm = None

def get_llm_instance():
    """Initializes and returns the LLM instance, creating it only if it doesn't exist."""
    global llm
    if llm is None:
        logger.info("Initializing DeepSeek LLM...")
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0.7,
            max_tokens=4096,
        )
        logger.info("DeepSeek LLM initialized.")
    return llm

def validate_step(step_data: dict) -> Tuple[bool, str]:
    """Validate a single step data."""
    required_fields = ['number', 'action', 'timestamp', 'explanation']
    for field in required_fields:
        if field not in step_data:
            return False, f"Missing required field: {field}"
        if not step_data[field]:  # Check if field is empty
            return False, f"Empty required field: {field}"
    
    # Validate step number is integer
    if not isinstance(step_data['number'], int):
        return False, "Step number must be an integer"
    
    return True, ""

def validate_response(response_data: dict) -> Tuple[bool, str]:
    """Validate the AI response data."""
    if not isinstance(response_data, dict):
        return False, "Response is not a dictionary"
    
    # Check required fields
    required_fields = ['video_type', 'title', 'materials_or_ingredients', 'steps']
    for field in required_fields:
        if field not in response_data:
            return False, f"Missing required field: {field}"
    
    # Validate materials/ingredients is a list of strings
    if not isinstance(response_data['materials_or_ingredients'], list):
        return False, "materials_or_ingredients must be a list"
    
    # Validate steps
    if not isinstance(response_data['steps'], list):
        return False, "steps must be a list"
    
    for i, step in enumerate(response_data['steps']):
        is_valid, error_msg = validate_step(step)
        if not is_valid:
            return False, f"Step {i+1}: {error_msg}"
    
    return True, ""

def call_deepseek_api(prompt: str) -> dict:
    """Send prompt to DeepSeek API and get JSON response."""
    try:
        # Get the LLM instance
        active_llm = get_llm_instance()

        messages = [
            SystemMessage(content="You are a helpful assistant that provides JSON responses."),
            HumanMessage(content=prompt)
        ]
        
        logger.info("Sending request to DeepSeek API...")
        response = active_llm.invoke(messages)
        response_text = response.content
        
        logger.info("Received response from DeepSeek API")
        logger.debug(f"Raw response: {response_text}")
        
        if response_text.startswith("```json"):
            response_text = response_text[7:-4].strip()
        
        try:
            parsed_response = json.loads(response_text)
            logger.info("Successfully parsed JSON response")
            return parsed_response
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response that failed to parse: {response_text}")
            return {}
            
    except Exception as e:
        logger.error(f"Error calling DeepSeek API: {e}")
        logger.error(traceback.format_exc())
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
               "Focus only on the main steps and filter out any irrelevant chatter. "
               "IMPORTANT: 'step_number' MUST be an integer, starting from 1."),
        "sv": ("Du är en expert på att analysera videotranskriptioner. "
               "Din uppgift är att bestämma videotypen (t.ex. 'matlagning', 'DIY', 'handledning'), "
               "extrahera dess titel, en lista över material eller ingredienser, och en steg-för-steg-guide. "
               "Användaren kommer att ge dig transkriptionen av en video. "
               "Formatera ditt svar som ett JSON-objekt med nycklarna: "
               "'video_type', 'title', 'materials_or_ingredients' (som en lista med strängar), och 'steps' "
               "(som en lista med objekt, var och en med 'step_number', 'action', 'timestamp' och 'explanation'). "
               "Se till att instruktionerna är tydliga, koncisa och lätta att följa. "
               "Fokusera endast på de huvudsakliga stegen och filtrera bort allt irrelevant prat. "
               "VIKTIGT: 'step_number' MÅSTE vara ett heltal, med start från 1.")
    }
    
    prompt = prompts.get(language, prompts["en"]) + f"\n\nTranscript:\n{text}"

    try:
        logger.info("Starting video content analysis")
        response_data = call_deepseek_api(prompt)
        
        # Validate response
        is_valid, error_msg = validate_response(response_data)
        if not is_valid:
            logger.error(f"Invalid AI response: {error_msg}")
            logger.error(f"Response data: {json.dumps(response_data, indent=2)}")
            return None

        logger.info("Creating VideoContent object")
        video_content = VideoContent(
            video_type=response_data["video_type"],
            title=response_data["title"],
            materials_or_ingredients=response_data["materials_or_ingredients"],
            steps=[Step(**step) for step in response_data["steps"]]
        )
        
        logger.info("Successfully created VideoContent object")
        return video_content
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error processing AI response: {e}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred in analyze_video_content: {e}")
        logger.error(traceback.format_exc())
        return None 