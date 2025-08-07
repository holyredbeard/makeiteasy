"""
Flexibel webcrawler för dynamisk receptextraktion enligt kravspecifikation.
Syftet är att bygga en webcrawler som möjliggör för användare att klistra in 
valfria länkar till webbsidor och automatiskt extrahera receptinnehåll.
"""

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
import logging
import hashlib
import sqlite3
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright
from langchain_deepseek.chat_models import ChatDeepSeek

from core.config import settings

logger = logging.getLogger(__name__)

def download_image(image_url: str, job_id: str) -> Optional[str]:
    """Laddar ner bild från URL och sparar lokalt"""
    if not image_url:
        return None
    
    try:
        # Skapa downloads-katalog om den inte finns
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(exist_ok=True)
        
        # Ladda ner bilden
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Bestäm filändelse
        content_type = response.headers.get('content-type', '')
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.image'
        
        # Spara bilden
        image_path = downloads_dir / f"{job_id}{ext}"
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded image: {image_path}")
        # Returnera relativ sökväg för frontend
        return f"/downloads/{job_id}{ext}"
        
    except Exception as e:
        logger.warning(f"Failed to download image {image_url}: {e}")
        return image_url  # Returnera original URL som fallback

class CrawlerException(Exception):
    """Anpassat undantag för crawler-fel"""
    pass

class CacheManager:
    """Hanterar cache för crawlade URLs"""
    
    def __init__(self, cache_file: str = "crawler_cache.db"):
        self.cache_file = cache_file
        self._init_cache()
    
    def _init_cache(self):
        """Initialiserar cache-databasen"""
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success BOOLEAN NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    def _get_url_hash(self, url: str) -> str:
        """Skapar hash för URL för att använda som cache-nyckel"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def get_cached_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Hämtar cached resultat för URL om det finns och är fräscht"""
        url_hash = self._get_url_hash(url)
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        
        # Hämta från cache (giltigt i 24 timmar)
        cutoff_time = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor.execute("""
            SELECT content, success FROM crawl_cache 
            WHERE url_hash = ? AND timestamp > ?
        """, (url_hash, cutoff_time))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            content, success = result
            if success:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
            else:
                # Returnera cached fel
                raise CrawlerException(content)
        
        return None
    
    def cache_result(self, url: str, result: Dict[str, Any], success: bool = True):
        """Cachar resultatet för URL"""
        url_hash = self._get_url_hash(url)
        content = json.dumps(result) if success else str(result)
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.cache_file)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO crawl_cache 
            (url_hash, url, content, timestamp, success)
            VALUES (?, ?, ?, ?, ?)
        """, (url_hash, url, content, timestamp, success))
        conn.commit()
        conn.close()
        
        logger.info(f"Cached {'successful' if success else 'failed'} result for URL: {url}")

class ContentExtractor:
    """Hanterar innehållsextraktion och DOM-rensning"""
    
    def __init__(self):
        # Tags att ta bort för att rensa brus
        self.noise_tags = [
            'script', 'style', 'nav', 'footer', 'header', 'aside',
            'advertisement', 'banner', 'popup', 'modal'
        ]
        
        # Klasser och IDs som indikerar brus
        self.noise_selectors = [
            '[class*="ad"]', '[class*="advertisement"]', '[class*="banner"]',
            '[class*="popup"]', '[class*="modal"]', '[class*="cookie"]',
            '[class*="social"]', '[class*="share"]', '[class*="comment"]',
            '[class*="newsletter"]', '[class*="subscription"]',
            '[id*="ad"]', '[id*="advertisement"]', '[id*="banner"]'
        ]
        
        # Selektorer för receptinnehåll
        self.recipe_selectors = [
            '[class*="recipe"]', '[class*="ingredients"]', '[class*="instructions"]',
            '[class*="steps"]', '[class*="method"]', '[class*="directions"]',
            'article', 'main', '[itemtype*="Recipe"]', '.entry-content'
        ]
    
    def clean_dom(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Rensar DOM från brus enligt kravspecifikationen"""
        logger.info("Cleaning DOM from noise...")
        
        # Ta bort noise tags (mer selektiv)
        basic_noise_tags = ['script', 'style', 'noscript']
        for tag_name in basic_noise_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Ta bort element med tydliga noise-selektorer (mer selektiv)
        critical_noise_selectors = [
            '[class*="advertisement"]', '[class*="banner"]',
            '[class*="popup"]', '[class*="modal"]',
            '[id*="advertisement"]', '[id*="banner"]'
        ]
        for selector in critical_noise_selectors:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except Exception:
                continue
        
        logger.info("DOM cleaning completed")
        return soup
    def find_image_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Hittar den bästa bild-URLen från sidan"""
        # Prioritera Open Graph och Twitter-bilder
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image['content'])

        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return urljoin(base_url, twitter_image['content'])

        # Hitta bilder inom recept-relaterade element
        for selector in self.recipe_selectors:
            try:
                recipe_element = soup.select_one(selector)
                if recipe_element:
                    img = recipe_element.find('img', {'src': True})
                    if img:
                        return urljoin(base_url, img['src'])
            except Exception:
                continue
        
        # Sista fallback: hitta största bilden på sidan
        largest_image = None
        max_size = 0
        for img in soup.find_all('img', {'src': True}):
            src = img.get('src')
            if not src.startswith('data:'): # Ignorera inline-bilder
                try:
                    # Försök få bildstorlek från width/height attribut
                    width = int(img.get('width', 0))
                    height = int(img.get('height', 0))
                    size = width * height
                    if size > max_size:
                        max_size = size
                        largest_image = img['src']
                except (ValueError, TypeError):
                    continue
        
        if largest_image:
            return urljoin(base_url, largest_image)

        return None

    def find_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Implementerar Readability-liknande heuristik för att hitta huvudinnehåll
        """
        logger.info("Finding main content using readability heuristics...")
        
        # Först försök hitta receptspecifikt innehåll
        for selector in self.recipe_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    # Välj det element med mest text som ser ut som ett recept
                    best_element = None
                    best_score = 0
                    
                    for element in elements:
                        text = element.get_text(strip=True)
                        score = self._calculate_content_score(element, text)
                        
                        if score > best_score:
                            best_score = score
                            best_element = element
                    
                    if best_element and best_score > 100:
                        logger.info(f"Found recipe content with selector {selector}, score: {best_score}")
                        return best_element
            except Exception:
                continue
        
        # Fallback: Använd textdensitetsanalys
        return self._find_content_by_density(soup)

    def _calculate_content_score(self, element: Tag, text: str) -> int:
        """Beräknar innehållspoäng för ett element"""
        score = len(text)
        
        # Bonus för receptrelaterade ord
        recipe_keywords = [
            'ingrediens', 'ingredients', 'recept', 'recipe', 'instruktion', 
            'instructions', 'tillbehör', 'tillgång', 'tillagning', 'gör så här',
            'method', 'preparation', 'cooking', 'baking'
        ]
        
        text_lower = text.lower()
        for keyword in recipe_keywords:
            if keyword in text_lower:
                score += 50
        
        # Bonus för listor (ingredienser/instruktioner)
        lists = element.find_all(['ul', 'ol'])
        score += len(lists) * 30
        
        # Penalty för mycket länkar (indikerar navigation/ads)
        links = element.find_all('a')
        link_text = ''.join(link.get_text() for link in links)
        link_density = len(link_text) / len(text) if text else 0
        if link_density > 0.3:
            score *= 0.5
        
        return int(score)
    
    def _find_content_by_density(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Hitta innehåll baserat på textdensitet (Readability-algoritm)"""
        logger.info("Using text density analysis for content extraction...")
        
        candidates = soup.find_all(['div', 'article', 'section', 'main', 'body'])
        best_candidate = None
        max_score = 0
        
        for candidate in candidates:
            text = candidate.get_text(strip=True)
            if len(text) < 50:  # Lägre krav på minsta längd
                continue
            
            score = self._calculate_content_score(candidate, text)
            
            if score > max_score:
                max_score = score
                best_candidate = candidate
        
        if best_candidate:
            logger.info(f"Found best content candidate with score: {max_score}")
            return best_candidate
        
        # Sista utväg: returnera hela dokumentet
        logger.warning("Could not find good content candidate, using entire document")
        return soup

class AIProcessor:
    """Hanterar AI-baserad receptextraktion"""
    
    def __init__(self):
        if not settings.deepseek_api_key:
            raise CrawlerException("DEEPSEEK_API_KEY krävs för AI-processing")
        
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=settings.deepseek_api_key,
            max_tokens=3000,
            temperature=0.1
        )
    
    def extract_recipe_with_ai(self, content_text: str, image_url: Optional[str]) -> Dict[str, Any]:
        """
        Använder språkmodell för att extrahera receptinnehåll enligt kravspecifikation
        """
        if len(content_text) < 100:
            raise CrawlerException("Otillräckligt textinnehåll för AI-analys")
        
        # Begränsa text till rimlig storlek för AI
        content_text = content_text[:12000]
        
        image_part = f'"img": "{image_url}",' if image_url else """"img_fallback_category": "t.ex. 'pasta', 'soup', 'meat' etc.", """

        prompt = f"""Du är en expert på att extrahera och strukturera receptinformation från webbinnehåll.
Analysera texten och returnera ett komplett JSON-objekt i exakt denna ordning.
Fyll i alla fält. Om information saknas, gör en rimlig uppskattning baserat på innehållet.

JSON-format:
{{
    "title": "Receptets titel",
    {image_part}
    "description": "En kort, lockande beskrivning av rätten (max 3 meningar).",
    "servings": "Antal portioner (t.ex. '4' eller '6-8')",
    "prep_time_minutes": "Förberedelsetid i minuter (endast siffra)",
    "cook_time_minutes": "Tillagningstid i minuter (endast siffra)",
    "ingredients": [
        "Ingrediens 1",
        "Ingrediens 2"
    ],
    "instructions": [
        "Steg 1",
        "Steg 2"
    ],
    "nutrition": {{
        "kcal": "Uppskattat antal kalorier per portion",
        "protein_g": "Uppskattat protein i gram per portion",
        "fat_g": "Uppskattat fett i gram per portion",
        "carbs_g": "Uppskattade kolhydrater i gram per portion"
    }}
}}

VIKTIGA INSTRUKTIONER:
- Returnera ENDAST JSON.
- Om en bild-URL finns (`img`), använd den. Annars, ange en `img_fallback_category`.
- Alla tidsfält ska vara heltal (minuter).
- Näringsinformation ska vara en uppskattning per portion.
- Om texten är på ett annat språk, översätt titel och beskrivning till svenska.

TEXT ATT ANALYSERA:
---
{content_text}
---

JSON:"""

        try:
            response = self.llm.invoke(prompt)
            
            if not response or not response.content:
                raise CrawlerException("AI returnerade tomt svar")
            
            content = response.content.strip()
            
            # Extrahera JSON från svaret
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise CrawlerException("Kunde inte hitta JSON i AI-svar")
            
            json_str = content[json_start:json_end]
            recipe_data = json.loads(json_str)
            
            logger.info("AI successfully extracted recipe data")
            return recipe_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise CrawlerException("AI returnerade ogiltigt JSON")
        except Exception as e:
            logger.error(f"AI processing error: {e}")
            raise CrawlerException(f"AI-processing misslyckades: {str(e)}")

class RecipeValidator:
    """Validerar extraherat receptinnehåll enligt kravspecifikation"""
    
    @staticmethod
    def validate_recipe(recipe_data: Dict[str, Any]) -> bool:
        """Validerar att receptdatan uppfyller de nya, utökade kraven."""
        try:
            # 1. Titel
            title = recipe_data.get('title')
            if not title or not isinstance(title, str) or len(title.strip()) < 3:
                logger.warning("Validation failed: Ogiltig eller saknad titel.")
                return False

            # 2. Bild eller fallback-kategori
            has_img = 'img' in recipe_data and isinstance(recipe_data.get('img'), str)
            has_fallback = 'img_fallback_category' in recipe_data and isinstance(recipe_data.get('img_fallback_category'), str)
            if not has_img and not has_fallback:
                logger.warning("Validation failed: Varken 'img' eller 'img_fallback_category' hittades.")
                return False

            # 3. Beskrivning
            description = recipe_data.get('description')
            if not description or not isinstance(description, str) or len(description.strip()) < 10:
                logger.warning("Validation failed: Ogiltig eller saknad beskrivning.")
                return False

            # 4. Ingredienser
            ingredients = recipe_data.get('ingredients')
            if not ingredients or not isinstance(ingredients, list) or len(ingredients) < 2:
                logger.warning("Validation failed: Ogiltig eller saknad ingredienslista.")
                return False

            # 5. Instruktioner
            instructions = recipe_data.get('instructions')
            if not instructions or not isinstance(instructions, list) or len(instructions) < 1:
                logger.warning("Validation failed: Ogiltig eller saknad instruktionslista.")
                return False

            # 6. Näringsinformation (valfri men måste vara en dict om den finns)
            nutrition = recipe_data.get('nutrition')
            if nutrition and not isinstance(nutrition, dict):
                logger.warning("Validation failed: Näringsinformation är inte en dict.")
                return False
            
            if nutrition:
                required_keys = ['kcal', 'protein_g', 'fat_g', 'carbs_g']
                if not all(key in nutrition for key in required_keys):
                    logger.warning("Validation failed: Näringsinformation saknar nycklar.")
                    return False

            logger.info("Recipe validation successful")
            return True

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False

class FlexibleWebCrawler:
    """
    Huvudklass för flexibel webcrawler enligt kravspecifikation
    """
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.content_extractor = ContentExtractor()
        self.ai_processor = AIProcessor()
        self.validator = RecipeValidator()
        
        # Timeout-inställningar
        self.request_timeout = 10
        self.playwright_timeout = 10000  # 10 sekunder för playwright
    
    async def crawl_recipe_from_url(self, url: str) -> Dict[str, Any]:
        """
        Huvudmetod för att crawla recept från URL enligt kravspecifikation
        """
        logger.info(f"Starting crawl for URL: {url}")
        
        try:
            # 1. Kontrollera cache först
            cached_result = self.cache_manager.get_cached_result(url)
            if cached_result:
                logger.info("Returning cached result")
                return cached_result
            
            # 2. Försök hämta HTML med requests först
            html_content = None
            try:
                html_content = await self._fetch_html_simple(url)
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Försök extrahera med enkel HTML först
                recipe_data = await self._extract_recipe_from_soup(soup, url)
                if recipe_data:
                    self.cache_manager.cache_result(url, recipe_data, True)
                    return recipe_data
                    
            except Exception as e:
                logger.warning(f"Simple HTML fetch failed: {e}")
            
            # 3. Fallback: Använd Playwright för JS-rendering
            logger.info("Using Playwright fallback for JS-rendered content")
            html_content = await self._fetch_html_with_playwright(url)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            recipe_data = await self._extract_recipe_from_soup(soup, url)
            if recipe_data:
                self.cache_manager.cache_result(url, recipe_data, True)
                return recipe_data
            
            # Om allt misslyckas
            error_msg = "Kunde inte extrahera receptinformation från sidan"
            self.cache_manager.cache_result(url, error_msg, False)
            raise CrawlerException(error_msg)
            
        except CrawlerException:
            raise
        except Exception as e:
            error_msg = f"Oväntat fel vid crawling: {str(e)}"
            logger.error(error_msg)
            self.cache_manager.cache_result(url, error_msg, False)
            raise CrawlerException(error_msg)
    
    async def _fetch_html_simple(self, url: str) -> str:
        """Hämtar HTML med requests (för statiska sidor)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=self.request_timeout)
        response.raise_for_status()
        
        return response.text
    
    async def _fetch_html_with_playwright(self, url: str) -> str:
        """Hämtar HTML med Playwright (för JS-rendered sidor)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Sätt timeout
            page.set_default_timeout(self.playwright_timeout)
            
            try:
                await page.goto(url, wait_until='networkidle')
                html_content = await page.content()
                return html_content
            finally:
                await browser.close()
    
    async def _extract_recipe_from_soup(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extraherar recept från BeautifulSoup-objekt"""
        try:
            # 1. Rensa DOM från brus
            cleaned_soup = self.content_extractor.clean_dom(soup)
            
            # 2. Hitta bild-URL
            image_url = self.content_extractor.find_image_url(cleaned_soup, url)

            # 3. Hitta huvudinnehåll
            main_content = self.content_extractor.find_main_content(cleaned_soup)
            
            # 4. Extrahera text för AI-analys
            content_text = main_content.get_text(separator=' ', strip=True)
            content_text = re.sub(r'\s+', ' ', content_text)  # Normalisera whitespace
            
            logger.info(f"Extracted content length: {len(content_text)}")
            logger.info(f"Content preview: {content_text[:500]}...")
            
            if len(content_text) < 50:
                logger.warning("Otillräckligt textinnehåll efter extraktion")
                return None
            
            # 5. Använd AI för att extrahera receptdata
            recipe_data = self.ai_processor.extract_recipe_with_ai(content_text, image_url)
            
            # 6. Validera resultatet
            if not self.validator.validate_recipe(recipe_data):
                logger.warning("Recipe validation failed")
                return None
            
            # 7. Ladda ner bild om den finns
            if image_url:
                job_id = str(uuid.uuid4())
                downloaded_image_path = download_image(image_url, job_id)
                recipe_data['image_url'] = downloaded_image_path
                # Ta bort img fältet från AI-svaret eftersom vi använder image_url
                if 'img' in recipe_data:
                    del recipe_data['img']
                logger.info(f"Image downloaded: {downloaded_image_path}")
            else:
                recipe_data['image_url'] = None
                # Ta bort img fältet från AI-svaret
                if 'img' in recipe_data:
                    del recipe_data['img']
            
            # 8. Lägg till metadata
            recipe_data['id'] = str(uuid.uuid4())
            recipe_data['source_url'] = url
            recipe_data['extracted_at'] = datetime.now().isoformat()
            
            logger.info(f"Successfully extracted recipe: {recipe_data.get('title', 'Unknown')}")
            return recipe_data
            
        except Exception as e:
            logger.error(f"Recipe extraction failed: {e}")
            return None

# Globala instans för användning i API
crawler_instance = FlexibleWebCrawler()

async def scrape_recipe_from_url(url: str) -> Dict[str, Any]:
    """
    Public API för att crawla recept från URL
    Denna funktion exponeras via API-endpointen
    """
    return await crawler_instance.crawl_recipe_from_url(url)