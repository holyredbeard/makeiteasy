import requests
from bs4 import BeautifulSoup
import json
import uuid
import os
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict, Any, List
import logging
import time
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

from core.config import settings
from langchain_deepseek.chat_models import ChatDeepSeek

logger = logging.getLogger(__name__)

class ScraperException(Exception):
    pass

def generate_description_with_llm(title: str, ingredients: List[str]) -> Optional[str]:
    if not settings.deepseek_api_key:
        logger.warning("[LLM] DEEPSEEK_API_KEY not set.")
        return None
    try:
        llm = ChatDeepSeek(model="deepseek-chat", api_key=settings.deepseek_api_key, max_tokens=150, temperature=0.7)
        ingredient_list = ", ".join(ingredients)
        prompt = f"Please write a short, appealing, and mouth-watering description in Swedish for a recipe called '{title}'. The main ingredients are: {ingredient_list}. The description should be 2-3 sentences."
        response = llm.invoke(prompt)
        if response and response.content:
            logger.info("LLM description generated successfully.")
            return response.content.strip()
    except Exception as e:
        logger.error(f"[LLM] Error generating description: {e}")
    return None

def generate_nutrition_with_llm(title: str, ingredients: List[str]) -> Optional[Dict[str, str]]:
    if not settings.deepseek_api_key:
        logger.warning("[LLM] DEEPSEEK_API_KEY not set for nutrition generation.")
        return None
    try:
        llm = ChatDeepSeek(model="deepseek-chat", api_key=settings.deepseek_api_key, max_tokens=200, temperature=0.3)
        ingredient_list = ", ".join(ingredients)
        prompt = f"""Based on the recipe '{title}' with these ingredients: {ingredient_list}, estimate the nutritional information per serving.

Please respond with ONLY a JSON object in this exact format:
{{
    "calories": "estimated_calories",
    "protein": "estimated_protein_g",
    "fat": "estimated_fat_g", 
    "carbohydrates": "estimated_carbs_g"
}}

Make realistic estimates based on the ingredients. For example, if there are many vegetables and lean proteins, estimate lower calories and fat. If there are noodles, rice, or fatty ingredients, estimate higher calories and carbs/fat."""
        
        response = llm.invoke(prompt)
        if response and response.content:
            try:
                import json
                nutrition_data = json.loads(response.content.strip())
                logger.info("LLM nutrition generated successfully.")
                return nutrition_data
            except json.JSONDecodeError as e:
                logger.error(f"[LLM] Error parsing nutrition JSON: {e}")
                return None
    except Exception as e:
        logger.error(f"[LLM] Error generating nutrition: {e}")
    return None

def download_image(image_url: str, job_id: str) -> Optional[str]:
    if not image_url:
        return None
    
    try:
        import requests
        from pathlib import Path
        
        # Create downloads directory if it doesn't exist
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(exist_ok=True)
        
        # Download the image
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Determine file extension
        content_type = response.headers.get('content-type', '')
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.image'
        
        # Save the image
        image_path = downloads_dir / f"{job_id}{ext}"
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded image: {image_path}")
        # Return relative path for frontend
        return f"/downloads/{job_id}{ext}"
        
    except Exception as e:
        logger.warning(f"Failed to download image {image_url}: {e}")
        return image_url  # Return original URL as fallback

def get_html_with_selenium(url: str) -> str:
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    driver.get(url)
    time.sleep(5)
    html = driver.page_source
    driver.quit()
    return html

def _extract_recipe_from_json_ld(data: Any) -> Optional[Dict[str, Any]]:
    if isinstance(data, dict):
        if data.get('@type') == 'Recipe' or (isinstance(data.get('@type'), list) and 'Recipe' in data.get('@type')):
            return data
        for value in data.values():
            found = _extract_recipe_from_json_ld(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _extract_recipe_from_json_ld(item)
            if found:
                return found
    return None

def parse_iso_duration(duration_str: Optional[str]) -> Optional[str]:
    if not duration_str or not isinstance(duration_str, str) or not duration_str.startswith('PT'):
        return duration_str
    try:
        parts = re.findall(r'(\d+)([HMN])', duration_str)
        total_minutes = 0
        for value, unit in parts:
            if unit == 'H':
                total_minutes += int(value) * 60
            elif unit == 'M':
                total_minutes += int(value)
        if total_minutes > 0:
            return f"{total_minutes} min"
    except Exception:
        pass
    return duration_str

def normalize_nutrition_data(nutrition_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(nutrition_data, dict):
        return None
    key_map = {"fatContent": "fat", "proteinContent": "protein", "carbohydrateContent": "carbohydrates", "calories": "calories"}
    normalized_data = {}
    for key, value in nutrition_data.items():
        normalized_key = key_map.get(key, key)
        if isinstance(value, str):
            value = value.replace("calories", "").strip()
        normalized_data[normalized_key] = value
    return normalized_data

def find_image_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    # Try Open Graph image first
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        return urljoin(base_url, og_image['content'])
    
    # Try Twitter image
    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    if twitter_image and twitter_image.get('content'):
        return urljoin(base_url, twitter_image['content'])
    
    # Try to find recipe images with better selectors
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '').lower()
        classes = ' '.join(img.get('class', [])).lower()
        
        # Skip logos, icons, etc.
        if any(junk in src.lower() for junk in ['logo', 'avatar', 'icon', 'sprite', 'banner']):
            continue
            
        # Look for recipe-related images
        if (('recipe' in alt or 'food' in alt or 'matbild' in alt or 'recept' in alt) or
            ('recipe' in classes or 'food' in classes or 'image' in classes) or
            ('recipe' in src.lower() or 'food' in src.lower())):
            return urljoin(base_url, src)
    
    # Fallback: find any large image that might be a recipe image
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if (src and 
            not any(junk in src.lower() for junk in ['logo', 'avatar', 'icon', 'sprite', 'banner']) and
            ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower() or 'webp' in src.lower())):
            return urljoin(base_url, src)
    
    return None

def find_best_content_block(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Finds the most likely content block for a recipe using advanced text density analysis.
    This is a far more robust method than simple keyword searching.
    """
    for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
        tag.decompose()

    candidates = soup.find_all(['div', 'article', 'section', 'main'])
    best_candidate = None
    max_score = -1

    for candidate in candidates:
        text = candidate.get_text(" ", strip=True)
        text_length = len(text)
        
        if text_length < 250:
            continue

        links = candidate.find_all('a')
        link_length = sum(len(link.get_text(" ", strip=True)) for link in links)
        
        # Calculate link density. A high density suggests it's not the main content.
        link_density = link_length / text_length if text_length > 0 else 0
        
        # Calculate the score. We want high text length and low link density.
        score = text_length * (1 - link_density)
        
        # Heavily penalize comment sections
        if 'kommentar' in str(candidate).lower() or 'comment' in str(candidate).lower():
            score *= 0.1

        # Boost sections that look like instructions or ingredients lists
        if ('instruktioner' in text.lower() or 'gör så här' in text.lower()) and 'ingredienser' in text.lower():
            score *= 3.0
            
        if score > max_score:
            max_score = score
            best_candidate = candidate
            
    if best_candidate:
        logger.info(f"Found best content block with text density score {max_score}.")
    else:
        logger.warning("Could not determine the best content block using text density analysis.")
        
    return best_candidate

def parse_with_ai(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Uses an AI model to parse the recipe from the page's best content block.
    """
    try:
        content_block = find_best_content_block(soup)
        if content_block:
            page_text = content_block.get_text(" ", strip=True)
            logger.info("Extracted text from best content block for AI parser.")
        else:
            page_text = soup.get_text(" ", strip=True)
            logger.warning("Could not find a best content block. Using full page text for AI parser.")

        page_text = re.sub(r'\s{2,}', ' ', page_text)
        
        if not page_text or len(page_text) < 100: # Check for minimal text length
            raise ScraperException("Could not extract sufficient text from the page.")
        
        # --- DEBUG: Save the input text for the AI ---
        with open("debug_ai_input.txt", "w", encoding="utf-8") as f:
            f.write(page_text)

        llm = ChatDeepSeek(model="deepseek-chat", api_key=settings.deepseek_api_key, max_tokens=2048, temperature=0.1)
        
        prompt = f"""
        Here is the text content from a recipe webpage. Please extract the recipe details and return them as a JSON object.
        The JSON object must have the following keys: "title", "ingredients", "instructions".
        
        - "title" must be a string.
        - "ingredients" must be an array of strings.
        - "instructions" must be an array of strings.
        
        Analyze the text carefully to identify the correct sections. Be very accurate.
        
        Webpage Text:
        ---
        {page_text[:8000]} 
        ---
        
        JSON Response:
        """

        response = llm.invoke(prompt)
        
        if response and response.content:
            # --- DEBUG: Save the raw response from the AI ---
            with open("debug_ai_response.txt", "w", encoding="utf-8") as f:
                f.write(response.content.strip())
                
            try:
                content = response.content.strip()
                json_str = content[content.find('{'):content.rfind('}')+1]
                recipe_data = json.loads(json_str)
                
                if 'title' in recipe_data and 'ingredients' in recipe_data and 'instructions' in recipe_data:
                    logger.info("AI parsing successful.")
                    return recipe_data
                else:
                    raise ScraperException("AI parsing failed to find all required recipe fields.")
            except json.JSONDecodeError as e:
                logger.error(f"[AI Parser] Failed to decode JSON from LLM response: {e}")
                raise ScraperException("AI parser returned invalid JSON.")
        else:
            raise ScraperException("AI parser returned an empty response.")
            
    except Exception as e:
        logger.error(f"[AI Parser] An unexpected error occurred: {e}")
        raise ScraperException(f"AI parsing failed: {e}")

def try_json_ld(soup: BeautifulSoup, download_images: bool, url: str) -> Optional[Dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            json_content = json.loads(script.string)
            recipe_graph = _extract_recipe_from_json_ld(json_content)
            if recipe_graph:
                job_id = str(uuid.uuid4())
                image_data = recipe_graph.get("image")
                image_url = None
                if isinstance(image_data, list) and image_data:
                    image_url = image_data[0].get("url") if isinstance(image_data[0], dict) else image_data[0]
                elif isinstance(image_data, dict):
                    image_url = image_data.get("url")
                elif isinstance(image_data, str):
                    image_url = image_data

                title = recipe_graph.get("name")
                ingredients = recipe_graph.get("recipeIngredient", [])
                description = recipe_graph.get("description") or generate_description_with_llm(title, ingredients)
                instructions = [step.get("text", step).strip() for step in recipe_graph.get("recipeInstructions", []) if step]
                servings = recipe_graph.get("recipeYield")
                if isinstance(servings, list): servings = servings[0]

                return {
                    "id": job_id, "title": title, "description": description,
                    "ingredients": ingredients, "instructions": instructions,
                    "image_url": download_image(image_url, job_id) if image_url and download_images else image_url,
                    "prep_time": parse_iso_duration(recipe_graph.get("prepTime") or recipe_graph.get("preparationTime")),
                    "cook_time": parse_iso_duration(recipe_graph.get("cookTime") or recipe_graph.get("totalTime")),
                    "servings": str(servings) if servings else None,
                    "nutritional_information": normalize_nutrition_data(recipe_graph.get("nutrition"))
                }
        except (json.JSONDecodeError, TypeError):
            continue
    return None

def try_selenium_fallback(url: str, download_images: bool) -> Optional[Dict[str, Any]]:
    try:
        html = get_html_with_selenium(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Use the new AI parser
        recipe_data = parse_with_ai(soup)
        
        job_id = str(uuid.uuid4())
        recipe_data['id'] = job_id
        
        # Find and download image
        image_url = find_image_url(soup, url)
        if image_url and download_images:
            downloaded_path = download_image(image_url, job_id)
            recipe_data['image_url'] = downloaded_path
            logger.info(f"Image downloaded to: {downloaded_path}")
        else:
            recipe_data['image_url'] = image_url
            logger.info(f"Image URL (not downloaded): {image_url}")
            
        # Generate nutritional info if ingredients were found
        if recipe_data.get('ingredients'):
            nutrition_data = generate_nutrition_with_llm(recipe_data['title'], recipe_data['ingredients'])
            if nutrition_data:
                recipe_data['nutritional_information'] = nutrition_data
        
        return recipe_data
    except ScraperException as e:
        logger.warning(f"[Fallback] {e}")
    except Exception as e:
        logger.error(f"[Fallback] Critical error during Selenium fallback: {e}")
    return None

def scrape_recipe_from_url(url: str, should_download_image: bool = True) -> Optional[Dict[str, Any]]:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Try JSON-LD first
        recipe = try_json_ld(soup, should_download_image, url)
        if recipe:
            logger.info(f"Successfully scraped '{recipe['title']}' using JSON-LD.")
            return recipe
        
        # 2. If JSON-LD fails, try AI parser on initial HTML
        logger.info("JSON-LD failed. Trying AI parser with initial HTML.")
        try:
            recipe = parse_with_ai(soup)
            if recipe:
                job_id = str(uuid.uuid4())
                recipe['id'] = job_id
                
                # Find image and generate nutrition
                image_url = find_image_url(soup, url)
                recipe['image_url'] = download_image(image_url, job_id) if image_url and should_download_image else image_url
                if recipe.get('ingredients'):
                    nutrition_data = generate_nutrition_with_llm(recipe['title'], recipe['ingredients'])
                    if nutrition_data:
                        recipe['nutritional_information'] = nutrition_data
                        
                logger.info(f"Successfully scraped '{recipe['title']}' using AI on initial HTML.")
                return recipe
        except ScraperException as e:
            logger.warning(f"AI parser failed on initial HTML: {e}. The page might require JavaScript rendering.")

    except requests.RequestException as e:
        logger.warning(f"Initial request failed: {e}. Proceeding to full Selenium fallback.")
    
    # 3. If everything else fails, use the full Selenium fallback
    logger.warning("All initial methods failed. Using full Selenium fallback with AI parser.")
    recipe = try_selenium_fallback(url, should_download_image)
    if recipe:
        logger.info(f"Successfully scraped '{recipe.get('title', 'Unknown Recipe')}' using Selenium fallback.")
        return recipe

    logger.error(f"All scraping methods failed for URL: {url}")
    return None
