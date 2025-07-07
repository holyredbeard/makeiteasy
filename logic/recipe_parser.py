import os
from dotenv import load_dotenv
from typing import Optional, Tuple
import json
import traceback
import logging
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from models.types import Step, Recipe

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
    required_fields = ['step_number', 'description', 'timestamp']
    for field in required_fields:
        if field not in step_data:
            return False, f"Missing required field: {field}"
        if not step_data[field] and field != 'timestamp':  # Allow empty timestamp
            return False, f"Empty required field: {field}"
    
    # Validate step number is integer
    if not isinstance(step_data['step_number'], int):
        return False, "Step number must be an integer"
    
    return True, ""

def validate_response(response_data: dict) -> Tuple[bool, str]:
    """Validate the AI response data."""
    if not isinstance(response_data, dict):
        return False, "Response is not a dictionary"
    
    # Check required fields
    required_fields = ['title', 'description', 'servings', 'prep_time', 'cook_time', 'materials_or_ingredients', 'steps']
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

def analyze_video_content(text: str, language: str = "en") -> Optional[Recipe]:
    """Analyze video transcript to extract structured data."""
    prompts = {
        "en": ("You are an expert at analyzing video transcripts. Your task is to extract structured recipe data. "
               "Format your response as a JSON object with the following keys: 'title', 'description', "
               "'servings', 'prep_time', 'cook_time', 'materials_or_ingredients', and 'steps'.\n\n"
               "Follow these specific instructions:\n"
               "1. 'title': The full, official name of the recipe.\n"
               "2. 'description': A brief, engaging summary of the dish. If not mentioned, create a suitable one.\n"
               "3. 'servings', 'prep_time', 'cook_time': Extract these values. If they are not mentioned, YOU MUST ESTIMATE them based on the ingredients and cooking process. Provide them as strings (e.g., '2-3 people', '15 minutes').\n"
               "4. 'materials_or_ingredients': A list of all ingredients as an array of strings.\n"
               "5. 'steps': A step-by-step guide as an array of objects, each with 'step_number' (integer), 'description' (string), and 'timestamp' (string, 'MM:SS').\n\n"
               "Ensure your entire response is a single, valid JSON object."),
        "sv": ("Du är en expert på att analysera videotranskriptioner. Din uppgift är att extrahera strukturerad receptdata. "
               "Formatera ditt svar som ett JSON-objekt med följande nycklar: 'title', 'description', "
               "'servings', 'prep_time', 'cook_time', 'materials_or_ingredients', och 'steps'.\n\n"
               "Följ dessa specifika instruktioner:\n"
               "1. 'title': Det fullständiga, officiella namnet på receptet.\n"
               "2. 'description': En kort, engagerande sammanfattning av rätten. Om den inte nämns, skapa en passande.\n"
               "3. 'servings', 'prep_time', 'cook_time': Extrahera dessa värden. Om de inte nämns, MÅSTE DU UPPSKATTA dem baserat på ingredienserna och tillagningsprocessen. Ange dem som strängar (t.ex. '2-3 personer', '15 minuter').\n"
               "4. 'materials_or_ingredients': En lista över alla ingredienser som en array av strängar.\n"
               "5. 'steps': En steg-för-steg-guide som en array av objekt, var och en med 'step_number' (heltal), 'description' (sträng), och 'timestamp' (sträng, 'MM:SS').\n\n"
               "Se till att hela ditt svar är ett enda, giltigt JSON-objekt.")
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
            raise ValueError(f"Invalid AI response: {error_msg}")

        logger.info("Creating Recipe object")
        recipe = Recipe(
            title=response_data["title"],
            description=response_data.get("description"),
            servings=response_data.get("servings", "N/A"),
            prep_time=response_data.get("prep_time", "N/A"),
            cook_time=response_data.get("cook_time", "N/A"),
            ingredients=response_data["materials_or_ingredients"],
            steps=[Step(**step) for step in response_data["steps"]]
        )
        
        logger.info("Successfully created Recipe object")
        return recipe
        
    except ValueError as e:
        logger.error(f"Error processing AI response: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred in analyze_video_content: {e}", exc_info=True)
        return None 