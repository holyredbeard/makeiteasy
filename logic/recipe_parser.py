import os
from dotenv import load_dotenv
from typing import Optional, Tuple, List, Dict, Union
import json
import traceback
import logging
import re
from collections import defaultdict
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from models.types import Step, Recipe
from .video_processing import contains_ingredients

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

def validate_ingredients_safety(ingredients: list) -> Tuple[list, list]:
    """Filter out dangerous ingredients and return safe ones."""
    # List of dangerous/illegal substances to filter out
    dangerous_keywords = [
        'lsd', 'acid', 'mdma', 'ecstasy', 'cocaine', 'heroin', 'methamphetamine', 'meth',
        'cannabis', 'marijuana', 'weed', 'thc', 'cbd', 'mushroom', 'shroom', 'psilocybin',
        'opium', 'morphine', 'fentanyl', 'amphetamine', 'barbiturate', 'benzodiazepine',
        'pcp', 'ketamine', 'ghb', 'rohypnol', 'dmt', 'ayahuasca', 'mescaline', 'peyote',
        'chemical', 'poison', 'toxic', 'bleach', 'ammonia', 'base', 'alkali',
        'chöringen', 'choringen', 'psychedelic', 'hallucinogen', 'narcotic'
    ]
    
    safe_ingredients = []
    removed_ingredients = []
    
    for ingredient in ingredients:
        ingredient_lower = ingredient.lower()
        is_dangerous = any(dangerous in ingredient_lower for dangerous in dangerous_keywords)
        
        if is_dangerous:
            removed_ingredients.append(ingredient)
            logger.warning(f"Removed dangerous ingredient: {ingredient}")
        else:
            safe_ingredients.append(ingredient)
    
    return safe_ingredients, removed_ingredients

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
    
    # Safety check: Filter dangerous ingredients
    safe_ingredients, removed = validate_ingredients_safety(response_data['materials_or_ingredients'])
    response_data['materials_or_ingredients'] = safe_ingredients
    
    if removed:
        logger.warning(f"Removed {len(removed)} dangerous ingredients: {removed}")
    
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
        
        # Robustly extract JSON from the response text
        # This regex finds a JSON block that might be wrapped in ```json ... ```
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        
        json_str = ""
        if json_match:
            json_str = json_match.group(1)
        else:
            # Fallback: if no markdown block, assume the whole text might be JSON
            # and try to find the first '{' and last '}'
            start = response_text.find('{')
            end = response_text.rfind('}')
            if start != -1 and end != -1:
                json_str = response_text[start:end+1]
            else:
                logger.error("No JSON object found in the response.")
                logger.error(f"Raw response: {response_text}")
                return {}

        try:
            parsed_response = json.loads(json_str)
            logger.info("Successfully parsed JSON response")
            return parsed_response
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extracted JSON: {e}")
            logger.error(f"Extracted JSON string that failed to parse: {json_str}")
            return {}
            
    except Exception as e:
        logger.error(f"Error calling DeepSeek API: {e}")
        logger.error(traceback.format_exc())
        return {}

def clean_ingredient_line(line: str) -> str:
    """
    Tar bort vanliga beredningsfraser från slutet av en ingrediensrad.
    Exempel: "1 onion, chopped" -> "1 onion"
    """
    if not line:
        return line
    # Lista av vanliga fraser att ta bort (lägg till fler vid behov)
    patterns = [
        r",?\s*cut into [^,]+", r",?\s*sliced", r",?\s*chopped", r",?\s*diced", r",?\s*minced",
        r",?\s*grated", r",?\s*peeled", r",?\s*beaten", r",?\s*softened", r",?\s*at room temperature",
        r",?\s*crushed", r",?\s*shredded", r",?\s*halved", r",?\s*quartered", r",?\s*thinly sliced",
        r",?\s*roughly chopped", r",?\s*freshly ground", r",?\s*finely chopped", r",?\s*coarsely chopped",
        r",?\s*mashed", r",?\s*drained", r",?\s*rinsed", r",?\s*washed", r",?\s*trimmed", r",?\s*deveined",
        r",?\s*seeded", r",?\s*with skin", r",?\s*without skin", r",?\s*with seeds", r",?\s*without seeds",
        r",?\s*julienned", r",?\s*zested", r",?\s*scrubbed", r",?\s*blanched", r",?\s*steamed",
        r",?\s*boiled", r",?\s*roasted", r",?\s*to taste", r",?\s*for garnish", r",?\s*for serving"
    ]
    result = line
    for pat in patterns:
        result = re.sub(pat + r"$", "", result, flags=re.IGNORECASE)
    return result.strip()

def group_ingredients(ingredients: List[str]) -> Union[List[Dict[str, List[str]]], List[str]]:
    """
    Gruppera ingredienser baserat på parenteskommentarer.
    
    Args:
        ingredients: Lista av ingrediensrader (strängar)
    
    Returns:
        Om grupper finns: Lista av grupper [{title, items}, ...]
        Om inga grupper: Platt lista av ingredienser
    """
    if not ingredients:
        return []
    
    group_dict = defaultdict(list)
    main_list = []
    seen = set()
    
    for item in ingredients:
        if not item or not item.strip():
            continue
            
        # Rensa beredningsfraser
        cleaned = clean_ingredient_line(item.strip())
        # Normalisera för dubblettkontroll (mängd + namn)
        norm = cleaned.lower()
        if norm in seen:
            continue
        seen.add(norm)
        
        # Matcha parentes i slutet av raden
        # Regex: (.*?) - ingrediens, (?:\\s*\\(([^)]+)\\))? - valfri parentes
        m = re.match(r"^(.*?)(?:\\s*\\(([^)]+)\\))?$", cleaned)
        if m:
            ingredient = m.group(1).strip()
            group = m.group(2)
            
            if group and group.strip():
                # Capitalize varje ord i gruppnamnet
                group_title = " ".join([w.capitalize() for w in group.strip().split()])
                group_dict[group_title].append(ingredient)
            else:
                main_list.append(ingredient)
        else:
            main_list.append(cleaned)
    
    # Slå ihop små grupper (1 ingrediens) med huvudlistan, om inte specialgrupp
    special_groups = {"sauce", "marinade", "dressing", "seasoning", "spice", "herb", "garnish"}
    for group, items in list(group_dict.items()):
        if len(items) == 1 and group.lower() not in special_groups:
            main_list.append(items[0])
            del group_dict[group]
    
    # Skapa resultat
    result = []
    
    # Lägg till huvudlistan först om den finns
    if main_list:
        if group_dict:
            result.append({"title": "Ingredients", "items": main_list})
        else:
            return main_list  # Platt lista om inga grupper
    
    # Lägg till grupperna
    for group, items in group_dict.items():
        result.append({"title": group, "items": items})
    
    return result

def analyze_video_content(text: str, language: str = "en", description: str = "", is_recipe_description: bool = False, ocr_text: str = "") -> Optional[Recipe]:
    """
    Analyze video content and extract recipe information.
    """
    try:
        if description and is_recipe_description:
            logger.info("Starting video content analysis with description as recipe source")
        else:
            logger.info("Starting video content analysis (transcript only)")
        
        # Define prompts
        prompts = {
            "en": ("You are an expert at analyzing video transcripts for COOKING RECIPES ONLY. Your task is to extract structured recipe data. "
                   "Format your response as a JSON object with the following keys: 'title', 'description', "
                   "'servings', 'prep_time', 'cook_time', 'materials_or_ingredients', and 'steps'.\n\n"
                   "CRITICAL SAFETY RULES:\n"
                   "- ONLY include safe, edible cooking ingredients\n"
                   "- NEVER include drugs, chemicals, or harmful substances\n"
                   "- If you see unusual words, interpret them as the closest NORMAL food ingredient\n"
                   "- When in doubt, use common cooking ingredients like salt, pepper, herbs, spices\n"
                   "- NO psychoactive substances, drugs, or chemicals of any kind\n\n"
                   "For each ingredient, ALWAYS include a specific amount (e.g. '2 tbsp soy sauce', '1 green bell pepper', '300g beef').\n"
                   "- If the amount is mentioned in the transcript or description, use that.\n"
                   "- If not, you MUST estimate a realistic amount based on the recipe and common sense.\n"
                   "- Never leave any ingredient without an amount.\n\n"
                   "Follow these specific instructions:\n"
                   "1. 'title': The full, official name of the recipe.\n"
                   "2. 'description': A brief, engaging summary of the dish. If not mentioned, create a suitable one.\n"
                   "3. 'servings', 'prep_time', 'cook_time': Extract these values. If they are not mentioned, YOU MUST ESTIMATE them based on the ingredients and cooking process. Provide them as strings (e.g., '2-3 people', '15 minutes').\n"
                   "4. 'materials_or_ingredients': A list of SAFE FOOD ingredients only as an array of strings, each with a specific amount.\n"
                   "5. 'steps': A step-by-step guide as an array of objects, each with 'step_number' (integer), 'description' (string), and 'timestamp' (string, 'MM:SS').\n\n"
                   "Ensure your entire response is a single, valid JSON object with ONLY safe cooking ingredients."),
            "sv": ("Du är en expert på att analysera videotranskriptioner för MATLAGNINGSRECEPT ENDAST. Din uppgift är att extrahera strukturerad receptdata. "
                   "Formatera ditt svar som ett JSON-objekt med följande nycklar: 'title', 'description', "
                   "'servings', 'prep_time', 'cook_time', 'materials_or_ingredients', och 'steps'.\n\n"
                   "KRITISKA SÄKERHETSREGLER:\n"
                   "- Inkludera ENDAST säkra, ätbara matingredienser\n"
                   "- Inkludera ALDRIG droger, kemikalier eller skadliga ämnen\n"
                   "- Om du ser ovanliga ord, tolka dem som närmaste NORMALA matingredienser\n"
                   "- Vid tvivel, använd vanliga matingredienser som salt, peppar, örter, kryddor\n"
                   "- INGA psykoaktiva ämnen, droger eller kemikalier av något slag\n\n"
                   "För varje ingrediens, ange ALLTID en specifik mängd (t.ex. '2 msk soja', '1 grön paprika', '300g nötkött').\n"
                   "- Om mängden nämns i transkriberingen eller beskrivningen, använd den.\n"
                   "- Om inte, MÅSTE du uppskatta en rimlig mängd utifrån receptet och sunt förnuft.\n"
                   "- Lämna aldrig någon ingrediens utan mängd.\n\n"
                   "Följ dessa specifika instruktioner:\n"
                   "1. 'title': Det fullständiga, officiella namnet på receptet.\n"
                   "2. 'description': En kort, engagerande sammanfattning av rätten. Om den inte nämns, skapa en passande.\n"
                   "3. 'servings', 'prep_time', 'cook_time': Extrahera dessa värden. Om de inte nämns, MÅSTE DU UPPSKATTA dem baserat på ingredienserna och tillagningsprocessen. Ange dem som strängar (t.ex. '2-3 personer', '15 minuter').\n"
                   "4. 'materials_or_ingredients': En lista över SÄKRA MATINGREDIENSER endast som en array av strängar, där varje ingrediens har en specifik mängd.\n"
                   "5. 'steps': En steg-för-steg-guide som en array av objekt, var och en med 'step_number' (heltal), 'description' (sträng), och 'timestamp' (sträng, 'MM:SS').\n\n"
                   "Se till att hela ditt svar är ett enda, giltigt JSON-objekt med ENDAST säkra matingredienser.")
        }
        
        base_prompt = prompts.get(language, prompts["en"])
        
        # Add description to prompt if it exists and appears to be a recipe
        if description and is_recipe_description:
            if language == "sv":
                base_prompt += "\n\nVIKTIGT: Denna video har en beskrivning som innehåller receptinformation. Använd både transkriptionen OCH beskrivningen för att skapa det bästa receptet."
                base_prompt += f"\n\nVideo beskrivning (recept):\n{description}"
            else:
                base_prompt += "\n\nIMPORTANT: This video has a description that contains recipe information. Use BOTH the transcript AND the description to create the best recipe."
                base_prompt += f"\n\nVideo description (recipe):\n{description}"
        
        # Add OCR text if available and transcript is poor
        if ocr_text and not contains_ingredients(text):
            if language == "sv":
                base_prompt += "\n\nVIKTIGT: Transkriptionen saknar receptinformation, men text har extraherats från bilderna. Använd denna text också."
                base_prompt += f"\n\nText från bilder:\n{ocr_text}"
            else:
                base_prompt += "\n\nIMPORTANT: The transcript lacks recipe information, but text has been extracted from images. Use this text as well."
                base_prompt += f"\n\nText from images:\n{ocr_text}"
        
        prompt = base_prompt + f"\n\nTranscript:\n{text}"
        
        response_data = call_deepseek_api(prompt)
        
        if not response_data:
            logger.error("No response from DeepSeek API")
            return None
        
        # Parse the response
        try:
            recipe_data = response_data  # response_data is already a dict from call_deepseek_api
            
            # Robust ingredients extraction
            ingredients_raw = recipe_data.get('ingredients')
            if not ingredients_raw:
                ingredients_raw = recipe_data.get('materials_or_ingredients')
            if not ingredients_raw:
                logger.warning("No ingredients or materials_or_ingredients found in recipe_data! Defaulting to empty list.")
                ingredients_raw = []
            # Convert to list of strings
            ingredients = []
            for ing in ingredients_raw:
                if isinstance(ing, dict):
                    # Try to extract 'name' or first value
                    if 'name' in ing:
                        ingredients.append(ing['name'])
                    else:
                        # Fallback: join all values as string
                        ingredients.append(' '.join(str(v) for v in ing.values()))
                else:
                    ingredients.append(str(ing))
            # Gruppindela ingredienser om möjligt
            grouped_ingredients = group_ingredients(ingredients)
            logger.info(f"Grouped ingredients structure: {grouped_ingredients}")
            # Create Recipe object
            recipe = Recipe(
                title=recipe_data.get('title', 'Unknown Recipe'),
                description=recipe_data.get('description', ''),
                serves=recipe_data.get('servings', None),
                prep_time=recipe_data.get('prep_time', None),
                cook_time=recipe_data.get('cook_time', None),
                ingredients=ingredients,  # Use flat list of strings, not grouped
                steps=[Step(step_number=step.get('step_number', step.get('number', i+1)), 
                           description=step.get('description', str(step))) 
                       for i, step in enumerate(recipe_data.get('steps', []))],
                thumbnail_path=recipe_data.get('thumbnail_path', None)
            )
            
            logger.info(f"Successfully parsed recipe: {recipe.title}")
            return recipe
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response data: {response_data}")
            return None
            
    except Exception as e:
        logger.error(f"Error in analyze_video_content: {e}")
        logger.error(traceback.format_exc())
        return None 