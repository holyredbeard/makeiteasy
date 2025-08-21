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
try:
    from playwright.async_api import async_playwright  # heavy; may be missing
except Exception:  # pragma: no cover
    async_playwright = None
try:
    from langchain_deepseek.chat_models import ChatDeepSeek  # optional; only needed when LLM fallback is used
except Exception:  # pragma: no cover
    ChatDeepSeek = None

from core.config import settings
from core.http_client import AsyncHTTPClient
from core.database import db

logger = logging.getLogger(__name__)
_http_client = AsyncHTTPClient()

def download_image(image_url: str, job_id: str) -> Optional[str]:
    """Laddar ner bild från URL och sparar lokalt"""
    if not image_url:
        return None
    
    try:
        # Skapa downloads-katalog om den inte finns
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(exist_ok=True)
        
        # Normalisera schemalös URL (//host/path)
        if isinstance(image_url, str) and image_url.startswith('//'):
            image_url = 'https:' + image_url
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

async def download_image_async(image_url: str, job_id: str) -> Optional[str]:
    """Asynkron wrapper som kör bildnedladdning i bakgrundstråd för att inte blockera event-loopen."""
    return await asyncio.to_thread(download_image, image_url, job_id)

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
        
        # Hämta från cache: 7 dagar för lyckade, 24h för misslyckade
        cursor.execute("""
            SELECT content, success, timestamp FROM crawl_cache 
            WHERE url_hash = ?
        """, (url_hash,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            content, success, ts = result
            try:
                ts_dt = datetime.fromisoformat(ts)
            except Exception:
                ts_dt = datetime.now() - timedelta(days=10)
            ttl = timedelta(days=7) if success else timedelta(hours=24)
            if datetime.now() - ts_dt <= ttl:
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
        basic_noise_tags = ['script', 'style', 'noscript', 'nav', 'header', 'footer', 'aside']
        for tag_name in basic_noise_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Ta bort element med tydliga noise-selektorer (mer selektiv)
        critical_noise_selectors = [
            '[class*="advertisement"]', '[class*="banner"]',
            '[class*="popup"]', '[class*="modal"]', '[class*="cookie"]',
            '[class*="consent"]', '[class*="gdpr"]', '[class*="newsletter"]',
            '[class*="subscribe"]', '[class*="promo"]', '[class*="promotion"]',
            '[class*="breadcrumb"]', '[class*="related"]', '[class*="widget"]',
            '[class*="sidebar"]', '[class*="share"]', '[class*="social"]',
            '[class*="rating"]', '[class*="review"]', '[class*="comment"]',
            '[class*="menu"]', '[class*="toggle"]', '[class*="toolbar"]',
            '[class*="search"]', '[class*="site-nav"]',
            '[id*="advertisement"]', '[id*="banner"]', '[id*="cookie"]',
            '[id*="menu"]', '[id*="social"]', '[id*="sidebar"]'
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
        """Hittar bästa bild-URL via flera källor (OG/Twitter, img data-attrs, srcset, picture)."""
        def _norm(u: Optional[str]) -> Optional[str]:
            if not u or not isinstance(u, str):
                return None
            u = u.strip()
            if u.startswith('data:'):
                return None
            if u.startswith('//'):
                u = 'https:' + u
            try:
                return urljoin(base_url, u)
            except Exception:
                return u

        def _parse_srcset(val: Optional[str]) -> List[tuple[str, int]]:
            out: List[tuple[str, int]] = []
            if not val or not isinstance(val, str):
                return out
            for part in val.split(','):
                p = part.strip()
                if not p:
                    continue
                bits = p.split()
                url = _norm(bits[0]) if bits else None
                w = 0
                if len(bits) > 1:
                    try:
                        if bits[1].endswith('w'):
                            w = int(bits[1][:-1])
                        elif bits[1].endswith('x'):
                            w = int(float(bits[1][:-1]) * 1000)
                    except Exception:
                        w = 0
                if url:
                    out.append((url, w))
            out.sort(key=lambda x: x[1], reverse=True)
            return out

        # 1) Meta-taggar
        og_image = soup.find('meta', attrs={'property': 'og:image'}) or soup.find('meta', attrs={'property': 'og:image:secure_url'})
        if og_image and og_image.get('content'):
            u = _norm(og_image.get('content'))
            if u:
                return u
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'}) or soup.find('meta', attrs={'name': 'twitter:image:src'})
        if twitter_image and twitter_image.get('content'):
            u = _norm(twitter_image.get('content'))
            if u:
                return u

        # 2) picture>source srcset
        best_url = None
        best_w = -1
        try:
            for src in soup.select('picture source[srcset]'):
                for url, w in _parse_srcset(src.get('srcset')):
                    if w > best_w:
                        best_w, best_url = w, url
        except Exception:
            pass

        # 3) Receptrelaterade containrar: img med olika lazy attribut
        def _harvest_from(node: Tag):
            nonlocal best_url, best_w
            if not isinstance(node, Tag):
                return
            for img in node.find_all('img'):
                cand = _norm(img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy'))
                if not cand:
                    for attr in ('data-srcset', 'srcset'):
                        if img.get(attr):
                            sset = _parse_srcset(img.get(attr))
                            if sset:
                                url, w = sset[0]
                                if w > best_w:
                                    best_w, best_url = w, url
                    continue
                w = 0
                try:
                    wi = int(img.get('width', 0) or 0)
                    hi = int(img.get('height', 0) or 0)
                    w = wi * hi
                except Exception:
                    w = 0
                if w > best_w:
                    best_w, best_url = w, cand

        for selector in self.recipe_selectors:
            try:
                recipe_element = soup.select_one(selector)
                if recipe_element:
                    _harvest_from(recipe_element)
            except Exception:
                continue

        # 4) Fallback: alla img på sidan
        if best_url is None:
            try:
                for img in soup.find_all('img'):
                    if img.get('src') and not img.get('src', '').startswith('data:'):
                        u = _norm(img.get('src'))
                        if u:
                            return u
            except Exception:
                pass

        return best_url
# --- Helpers for post-processing ---
_RE_STEP_START = re.compile(r"^(?:\d+\.|\d+\)|steg\s*\d+|värm|hacka|skala|vispa|blanda|stek|koka|rör|sätt|lägg|häll|grädda|bryn|skär|smält|tillsätt)", re.I)

def _filter_and_trim_instructions(steps: List[str]) -> List[str]:
    cleaned: List[str] = []
    for s in steps or []:
        try:
            t = re.sub(r"\s+", " ", s or "").strip()
            if not t:
                continue
            tl = t.lower()
            if tl.startswith('gör så här') or tl.startswith('instruktion') or tl.startswith('instructions'):
                continue
            cleaned.append(t)
        except Exception:
            continue
    # Trim everything before first real step
    start_idx = 0
    for i, t in enumerate(cleaned):
        if _RE_STEP_START.match(t):
            start_idx = i
            break
    return cleaned[start_idx:]
    def find_image_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Hittar bästa bild-URL via flera källor (OG/Twitter, img data-attrs, srcset, picture)."""
        def _norm(u: Optional[str]) -> Optional[str]:
            if not u or not isinstance(u, str):
                return None
            u = u.strip()
            if u.startswith('data:'):
                return None
            # Protokoll-relativt
            if u.startswith('//'):
                u = 'https:' + u
            try:
                return urljoin(base_url, u)
            except Exception:
                return u

        def _parse_srcset(val: Optional[str]) -> List[tuple[str, int]]:
            """Returnerar [(url, width)] sorterad efter width desc."""
            out: List[tuple[str, int]] = []
            if not val or not isinstance(val, str):
                return out
            for part in val.split(','):
                p = part.strip()
                if not p:
                    continue
                bits = p.split()
                url = _norm(bits[0]) if bits else None
                w = 0
                if len(bits) > 1:
                    try:
                        if bits[1].endswith('w'):
                            w = int(bits[1][:-1])
                        elif bits[1].endswith('x'):
                            # Densitet – approximera med 1000*w för prioritering
                            w = int(float(bits[1][:-1]) * 1000)
                    except Exception:
                        w = 0
                if url:
                    out.append((url, w))
            out.sort(key=lambda x: x[1], reverse=True)
            return out

        # 1) Meta-taggar
        og_image = soup.find('meta', attrs={'property': 'og:image'}) or soup.find('meta', attrs={'property': 'og:image:secure_url'})
        if og_image and og_image.get('content'):
            u = _norm(og_image.get('content'))
            if u:
                return u
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'}) or soup.find('meta', attrs={'name': 'twitter:image:src'})
        if twitter_image and twitter_image.get('content'):
            u = _norm(twitter_image.get('content'))
            if u:
                return u

        # 2) picture>source srcset
        best_url = None
        best_w = -1
        try:
            for src in soup.select('picture source[srcset]'):
                for url, w in _parse_srcset(src.get('srcset')):
                    if w > best_w:
                        best_w, best_url = w, url
        except Exception:
            pass

        # 3) Receptrelaterade containrar: img med olika lazy attribut
        def _harvest_from(node: Tag):
            nonlocal best_url, best_w
            if not isinstance(node, Tag):
                return
            for img in node.find_all('img'):
                cand = _norm(img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy'))
                if not cand:
                    # srcset-varianter
                    for attr in ('data-srcset', 'srcset'):
                        if img.get(attr):
                            sset = _parse_srcset(img.get(attr))
                            if sset:
                                url, w = sset[0]
                                if w > best_w:
                                    best_w, best_url = w, url
                    continue
                # Försök uppskatta storlek
                w = 0
                try:
                    wi = int(img.get('width', 0) or 0)
                    hi = int(img.get('height', 0) or 0)
                    w = wi * hi
                except Exception:
                    w = 0
                if w > best_w:
                    best_w, best_url = w, cand

        for selector in self.recipe_selectors:
            try:
                recipe_element = soup.select_one(selector)
                if recipe_element:
                    _harvest_from(recipe_element)
            except Exception:
                continue

        # 4) Fallback: alla img på sidan
        if best_url is None:
            try:
                for img in soup.find_all('img'):
                    if img.get('src') and not img.get('src', '').startswith('data:'):
                        u = _norm(img.get('src'))
                        if u:
                            return u
            except Exception:
                pass

        return best_url

    def find_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Implementerar Readability-liknande heuristik för att hitta huvudinnehåll
        Förbättrad för att bättre hantera svenska receptsajter
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
        
        # Ny: Försök med svenska-specifika selectors
        swedish_selectors = [
            '[class*="recipe"]', '[class*="recept"]', '[class*="ingred"]', 
            '[class*="instruc"]', '[class*="portion"]', '[class*="tid"]',
            '[id*="recipe"]', '[id*="recept"]', '[id*="ingred"]', 
            '[id*="instruc"]', '[id*="portion"]', '[id*="tid"]',
            'article', 'main', '.content', '.main-content',
            '.post-content', '.entry-content', '.recipe-content'
        ]
        
        for selector in swedish_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    best_element = None
                    best_score = 0
                    
                    for element in elements:
                        text = element.get_text(strip=True)
                        score = self._calculate_content_score(element, text)
                        
                        if score > best_score and score > 50:  # Lägre tröskel för svenska selectors
                            best_score = score
                            best_element = element
                    
                    if best_element:
                        logger.info(f"Found Swedish recipe content with selector {selector}, score: {best_score}")
                        return best_element
            except Exception:
                continue
        
        # Fallback: Använd textdensitetsanalys
        content = self._find_content_by_density(soup)
        
        # Ytterligare validering: kontrollera att innehållet faktiskt ser ut som ett recept
        text = content.get_text(strip=True)
        if not self._looks_like_recipe(text):
            logger.warning("Content doesn't look like a recipe, trying broader search")
            # Sista utväg: leta efter listor som kan vara ingredienser/instruktioner
            list_containers = soup.find_all(['div', 'section', 'article'])
            for container in list_containers:
                lists = container.find_all(['ul', 'ol'])
                if len(lists) >= 2:  # Minst två listor (ingredienser + instruktioner)
                    text = container.get_text(strip=True)
                    if len(text) > 200 and self._looks_like_recipe(text):
                        logger.info(f"Found recipe-like content with multiple lists")
                        return container
        
        return content

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

    def _looks_like_recipe(self, text: str) -> bool:
        """
        Bestämmer om texten ser ut som ett recept baserat på nyckelord och mönster
        """
        if not text or len(text) < 100:
            return False
        
        text_lower = text.lower()
        
        # Svenska receptnyckelord
        recipe_keywords = [
            'ingrediens', 'ingredients', 'recept', 'recipe', 'instruktion', 
            'instructions', 'tillbehör', 'tillgång', 'tillagning', 'gör så här',
            'method', 'preparation', 'cooking', 'baking', 'portion', 'serveringar',
            'tid', 'time', 'minuter', 'minutes', 'timmar', 'hours', 'grad', 'degree',
            'stek', 'koka', 'baka', 'grilla', 'vispa', 'blanda', 'hacka', 'skala',
            'tillsätt', 'lägg', 'häll', 'servera', 'smaka av', 'krydda', 'salt', 'peppar'
        ]
        
        # Kontrollera förekomst av receptrelaterade ord
        keyword_count = sum(1 for keyword in recipe_keywords if keyword in text_lower)
        
        # Kolla efter kvantiteter och mått
        has_quantities = bool(re.search(r'\d+\s*(?:g|kg|dl|ml|l|msk|tsk|krm|st|klyfta|cm)', text_lower))
        
        # Kolla efter stegvisa instruktioner
        has_steps = bool(re.search(r'(?:\d+\.|\d+\)|steg\s*\d+)', text_lower))
        
        # Om vi har tillräckligt med receptrelaterade indikatorer
        return (keyword_count >= 3) or (has_quantities and has_steps) or (keyword_count >= 2 and has_quantities)

class AIProcessor:
    """Hanterar AI-baserad receptextraktion"""
    
    def __init__(self):
        if ChatDeepSeek is None:
            raise CrawlerException("DeepSeek client not installed; required for AI-processing")
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

        prompt = f"""DU ÄR EN EXPERT PÅ SVENSKA MATRECEPT! Analysera texten och extrahera receptinformation.

VIKTIGT: Texten kan innehålla webbsidans navigation, reklam eller annat icke-receptinnehåll. 
Fokusera ENDAST på den del som faktiskt beskriver receptet.

OM TEXTEN INTE INNEHÅLLER ETT RECEPT: Returnera tomt JSON med title="", ingredients=[], instructions=[]

OM TEXTEN INNEHÅLLER ETT RECEPT: Fyll i alla fält baserat på det du hittar.

SPECIELLA INSTRUKTIONER FÖR SVENSKA RECEPT:
- Identifiera svenska ingredienser och mått (g, dl, msk, tsk, krm, st, klyfta)
- Behåll svenska termer men se till att de är korrekt formaterade
- Översätt INTE svenska ingrediensnamn till engelska
- Svenska tidsangivelser: "minuter", "timmar"
- Svenska portioner: "portioner", "serveringar"

JSON-FORMAT (returnera ALLTID denna exakta struktur):
{{
    "title": "Receptets titel (lämna tom om ingen titel hittas)",
    {image_part}
    "description": "Kort beskrivning (max 2 meningar) eller tom sträng",
    "servings": "Antal portioner (t.ex. '4' eller '6-8') eller tom sträng",
    "prep_time_minutes": "Förberedelsetid i minuter (endast siffra) eller null",
    "cook_time_minutes": "Tillagningstid i minuter (endast siffra) eller null",
    "ingredients": [
        "Ingrediens 1 i korrekt format",
        "Ingrediens 2 i korrekt format"
    ],
    "instructions": [
        "Steg 1 i tydlig svenska",
        "Steg 2 i tydlig svenska"
    ],
    "nutrition": {{
        "kcal": "Kalorier per portion eller tom sträng",
        "protein_g": "Protein i gram eller tom sträng", 
        "fat_g": "Fett i gram eller tom sträng",
        "carbs_g": "Kolhydrater i gram eller tom sträng"
    }}
}}

EXTRA VIKTIGT:
- Returnera ENDAST JSON, inget annat text
- Om texten är webbsidans footer/navigation (t.ex. "Kokaihop är Sverige största community"), returnera tomt JSON
- Om du ser text som "ingredienser", "instruktioner", "portioner" - det är ett recept!
- Föredrag svenska termer: "dl" istället för "deciliter", "msk" istället för "matsked"

TEXT ATT ANALYSERA (kan innehålla webbsideelement):
---
{content_text}
---

SVARA ENDAST MED JSON:"""

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


# --- Deterministisk snabbparser för ingrediensrader ---
_FRACTIONS = {
    '¼': 0.25, '½': 0.5, '¾': 0.75,
    '⅐': 1/7, '⅑': 1/9, '⅒': 0.1, '⅓': 1/3, '⅔': 2/3, '⅕': 0.2, '⅖': 0.4, '⅗': 0.6, '⅘': 0.8,
    '⅙': 1/6, '⅚': 5/6, '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875
}
_RE_FRACTION = re.compile(r"(?:(\d+)\s+)?([¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])")
_RE_ASCII_FRAC = re.compile(r"(?:(?P<whole>\d+)\s+)?(?P<num>\d+)/(?P<den>\d+)")
_RE_MIXED = re.compile(r"^(?P<amt>\d+[\,\.]?\d*)\s*(?:(?:–|-|to|till)\s*(?P<amt2>\d+[\,\.]?\d*))?\s*(?P<unit>[a-zA-ZåäöÅÄÖ\.]+)?\b", re.I)
_RE_LENGTH = re.compile(r"\b(?P<amt>\d+[\,\.]?\d*)\s*(?P<unit>cm|centimeter|centimeters)\b", re.I)
_RE_TIME_META = re.compile(r"^(?:förberedelse|förberedelsetid|tillagning|tillagningstid|klart på|klar på|total tid|tid|prep(?:aration)?|cook(?:ing)?|ready in|total time)\s*[:\-]?\s*\d+\s*(?:min|minutes|minute|minuter|h|hr|hour|hours)\b", re.I)
_RE_TIME_CLOCK = re.compile(r"^\s*\d{1,2}:\d{2}(?::\d{2})?\s*$")
_TEMP_WORDS = re.compile(r"(?i)(varm|het|hot|warm|room temp|temperatur)")
_STOP_WORDS = re.compile(r"(?i)(to taste|for serving|att servera|smaka av|efter smak)")
_UNIT_ALIASES = {
    # Spoons
    'tsp': {'tsp', 'teaspoon', 'teaspoons', 'tsk', 'tesked', 'teskedar'},
    'tbsp': {'tbsp', 'tablespoon', 'tablespoons', 'msk', 'matsked', 'matskedar'},
    # Volume
    'cup': {'cup', 'cups'},
    'dl': {'dl'},
    'l': {'l', 'liter', 'litre', 'liters'},
    'ml': {'ml', 'milliliter', 'milliliters'},
    'cl': {'cl', 'centiliter', 'centiliters'},
    'pint': {'pint', 'pints', 'pt'},
    'quart': {'quart', 'quarts', 'qt'},
    # Weight
    'g': {'g', 'gram', 'grams', 'gramm'},
    'kg': {'kg', 'kilogram', 'kilo'},
    'mg': {'mg', 'milligram', 'milligrams'},
    'oz': {'oz', 'ounce', 'ounces'},
    'lb': {'lb', 'lbs', 'pound', 'pounds'},
    # Small Swedish measure (kryddmått ≈ 1 ml). Keep as its own unit for display.
    'krm': {'krm', 'kryddmått'},
    # Pieces and common package nouns (kept as display units)
    'st': {'st', 'styck', 'stycken', 'piece', 'pieces'},
    'klyfta': {'klyfta', 'klyftor', 'clove', 'cloves'},
    'burk': {'burk', 'burkar', 'can', 'cans', 'jar', 'jars'},
    'paket': {'paket', 'pkt', 'package', 'packages', 'förp', 'förpackning', 'förpackningar'},
    'påse': {'påse', 'påsar', 'bag', 'bags'},
    'stick': {'stick', 'sticks'},
    'sheet': {'sheet', 'sheets'},
    'slice': {'slice', 'slices'},
    'bunch': {'bunch', 'bunches'},
    'head': {'head', 'heads'},
    'fillet': {'fillet', 'fillets', 'filet', 'filets'},
    # Length
    'cm': {'cm', 'centimeter', 'centimeters'},
}

_UNIT_PRINT = {
    'tsp': 'tsk',
    'tbsp': 'msk',
    'cup': 'cup',
    'dl': 'dl',
    'l': 'l',
    'ml': 'ml',
    'cl': 'cl',
    'pint': 'pint',
    'quart': 'quart',
    'g': 'g',
    'kg': 'kg',
    'mg': 'mg',
    'oz': 'oz',
    'lb': 'lb',
    'krm': 'krm',
    'st': 'st',
    'klyfta': 'klyfta',
    'burk': 'burk',
    'paket': 'paket',
    'påse': 'påse',
    'stick': 'stick',
    'sheet': 'sheet',
    'slice': 'slice',
    'bunch': 'bunch',
    'head': 'head',
    'fillet': 'fillet',
    'cm': 'cm',
}

def _normalize_fraction(text: str) -> str:
    def repl(m):
        whole = float(m.group(1) or 0)
        frac = _FRACTIONS.get(m.group(2), 0)
        return str(whole + frac)
    s = _RE_FRACTION.sub(repl, text)
    # ASCII fraction like "2 1/2" or "1/4"
    def repl2(m):
        try:
            whole = float(m.group('whole') or 0)
            num = float(m.group('num'))
            den = float(m.group('den'))
            return str(whole + (num/den))
        except Exception:
            return m.group(0)
    try:
        s = re.sub(r"(?:(\d+)\s+)?(\d+)/(\d+)", lambda m: str((float(m.group(1) or 0)) + float(m.group(2))/float(m.group(3))), s)
    except Exception:
        pass
    return s

def _parse_amount_unit(line: str) -> tuple[Optional[float], Optional[str], str]:
    s = line.strip()
    # Utöka stopwords inkl. optional/valfritt
    global _STOP_WORDS
    _STOP_WORDS = re.compile(r"(?i)(optional|valfritt|to taste|for serving|to serve|att servera|smaka av|efter smak|as needed)")
    s = _STOP_WORDS.sub('', s)
    if _TEMP_WORDS.search(s):
        s = _TEMP_WORDS.sub('', s)
    s = _normalize_fraction(s)
    # Längdmått (t.ex. 3 cm ingefära)
    m_len = _RE_LENGTH.search(s)
    if m_len:
        try:
            amount = float(m_len.group('amt').replace(',', '.'))
        except Exception:
            amount = None
        unit_norm = 'cm'
        rest = _RE_LENGTH.sub('', s).strip()
        rest = re.sub(r'^[\s,.;:•\-–—]+', '', rest)
        return amount, unit_norm, rest
    m = _RE_MIXED.search(s)
    if not m:
        return None, None, s.strip()
    amt = m.group('amt')
    amt2 = m.group('amt2')
    unit_raw = (m.group('unit') or '').lower().strip('.')
    amount: Optional[float] = None
    try:
        if amt and amt2:
            amount = (float(amt.replace(',', '.')) + float(amt2.replace(',', '.'))) / 2.0
        elif amt:
            amount = float(amt.replace(',', '.'))
    except Exception:
        amount = None
    unit_norm = None
    if unit_raw:
        for key, vals in _UNIT_ALIASES.items():
            if unit_raw in vals:
                unit_norm = key
                break
        # If not a recognized unit, push it back into the item text
        if unit_norm is None:
            rest = (unit_raw + ' ' + s[m.end():].strip()).strip()
            rest = re.sub(r'^[\s,.;:•\-–—]+', '', rest)
            return amount, None, rest
    rest = s[m.end():].strip()
    rest = re.sub(r'^[\s,.;:•\-–—]+', '', rest)
    return amount, unit_norm, rest

def _format_quantity(amount: Optional[float], unit: Optional[str]) -> str:
    if amount is None and not unit:
        return ''
    if amount is None:
        return _UNIT_PRINT.get(unit, unit or '')
    # Render integers nicely
    if float(amount).is_integer():
        amt = str(int(amount))
    else:
        amt = ("%.2f" % float(amount)).rstrip('0').rstrip('.')
    if unit:
        return f"{amt} {_UNIT_PRINT.get(unit, unit)}"
    return amt

def _guess_unit(name: str, amount: Optional[float]) -> Optional[str]:
    n = (name or '').strip().lower()
    amt = float(amount) if amount is not None else None
    if not n:
        return None
    # piece-like → use 'st' (pieces)
    if any(w in n for w in ['lök', 'ägg']):
        return 'st'
    if any(w in n for w in ['klyfta', 'klyftor']):
        return 'klyfta'
    # clear liquids → dl
    if any(w in n for w in ['grädde', 'mjölk', 'vatten', 'buljong', 'sky']):
        return 'dl'
    # oils/sauces small amounts → msk, otherwise dl
    if any(w in n for w in ['olja', 'vinegar', 'vinäger', 'soja', 'sås', 'sauce', 'soy', 'soy sauce']):
        if amt is None or amt <= 5:
            return 'tbsp'
        return 'dl'
    # flour → msk for small, otherwise dl
    if 'mjöl' in n:
        if amt is not None and amt <= 5:
            return 'tbsp'
        return 'dl'
    # pasta/rice/noodles and meats/fish default to grams
    if any(w in n for w in ['pasta','spaghetti','penne','fusilli','ris','rice','bulgur','couscous','nudlar','noodle','lax','laxfilé','kyckling','kött','färs','filé','zucchini','gurka','beef','chicken','pork','salmon','tuna','shrimp','noodles']):
        return 'g'
    # citrus → pieces
    if any(w in n for w in ['citron','lime','apelsin','lemon','orange']):
        return 'st'
    # spices → tsk default
    if any(w in n for w in ['peppar', 'salt', 'krydda']):
        return 'tsp'
    return None

def _to_structured_ingredients(lines: List[str]) -> List[dict]:
    # Pre-merge split quantities like ["2", "1/2 dl vispgrädde"] => "2 1/2 dl vispgrädde"
    merged: List[str] = []
    i = 0
    while i < len(lines or []):
        row = str(lines[i]) if not isinstance(lines[i], str) else lines[i]
        nxt = str(lines[i+1]) if (i + 1 < len(lines or [])) else None
        if row and row.strip().isdigit() and nxt:
            nxt_s = nxt.strip()
            if re.match(r"^(?:\d+/\d+|[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]|[a-zA-ZåäöÅÄÖ]{1,3})\b", nxt_s):
                merged.append((row.strip() + ' ' + nxt_s).strip())
                i += 2
                continue
        merged.append(row)
        i += 1

    items: List[dict] = []
    for row in merged:
        if not isinstance(row, str):
            try:
                row = str(row)
            except Exception:
                continue
        if not row.strip():
            continue
        amount, unit, rest = _parse_amount_unit(row)
        if unit is None and amount is not None:
            unit = _guess_unit(rest, amount) or unit
        # Normalize "skal och saft" to citrus if fruit unspecified
        base_name = rest.strip() or row.strip()
        lname = base_name.lower()
        if ('skal' in lname and 'saft' in lname) and not any(x in lname for x in ['citron','lime','lemon','orange','apelsin']):
            base_name = 'citron'
            if amount is not None and (unit is None or unit == ''):
                unit = 'each'
        # Extrahera parenteser som notes
        notes = None
        try:
            m_note = re.search(r"\(([^\)]+)\)", base_name)
            if m_note:
                notes = m_note.group(1).strip()
                base_name = re.sub(r"\([^\)]*\)", "", base_name).strip()
        except Exception:
            pass
        quantity = _format_quantity(amount, unit)
        name = base_name
        is_range = bool(re.search(r"\b\d+\s*(?:–|-|to|till)\s*\d+\b", row))
        items.append({'name': name, 'quantity': quantity, 'amount': amount, 'unit': unit, 'notes': notes, 'range': True if is_range else False})
    return items

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

            # 6. Servings (obligatoriskt)
            servings = recipe_data.get('servings')
            if not servings or not isinstance(servings, (str, int)) or len(str(servings).strip()) < 1:
                logger.warning("Validation failed: Saknar 'servings'.")
                return False

            # 7. Tider (valfria men om någon finns, ska vara heltalsminuter)
            for k in ['prep_time_minutes', 'cook_time_minutes', 'total_time_minutes']:
                if k in recipe_data and recipe_data[k] is not None:
                    try:
                        _ = int(recipe_data[k])
                    except Exception:
                        logger.warning(f"Validation failed: {k} är inte heltal.")
                        return False

            # 8. Näringsinformation (valfri men måste vara en dict om den finns)
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
        # LLM init lazily to avoid hard dependency when not used
        self.ai_processor = None
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
                try:
                    normalized = await self._normalize_and_enrich(cached_result, url)
                    if normalized != cached_result:
                        self.cache_manager.cache_result(url, normalized, True)
                    logger.info("Returning cached result")
                    return normalized
                except Exception:
                    logger.info("Returning cached result")
                    return cached_result
            
            # 2. Försök hämta HTML med snabb HTTP-klient först (HTTP/2 + cache)
            html_content = None
            try:
                t0 = time.perf_counter()
                html_content = await self._fetch_html_simple(url)
                t_fetch = int((time.perf_counter() - t0) * 1000)
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Kör parallell, deterministisk extraktion först med early-exit
                t1 = time.perf_counter()
                recipe_data = await self._extract_quick_sources(soup, url)
                t_quick = int((time.perf_counter() - t1) * 1000)
                if recipe_data:
                    logger.info(f"Quick extraction success (fetch={t_fetch} ms, quick={t_quick} ms)")
                    recipe_data = await self._normalize_and_enrich(recipe_data, url, soup)
                    self.cache_manager.cache_result(url, recipe_data, True)
                    return recipe_data

                # Fallback till AI-baserad extraktion på samma HTML
                recipe_data = await self._extract_recipe_from_soup(soup, url)
                if recipe_data:
                    logger.info(f"AI extraction after quick fallback (fetch={t_fetch} ms)")
                    recipe_data = await self._normalize_and_enrich(recipe_data, url, soup)
                    self.cache_manager.cache_result(url, recipe_data, True)
                    return recipe_data
                    
            except Exception as e:
                logger.warning(f"Simple HTML fetch failed: {e}")
            
            # 3. Fallback: Använd Playwright för JS-rendering
            logger.info("Using Playwright fallback for JS-rendered content")
            html_content = await self._fetch_html_with_playwright(url)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Försök snabb-källor först även här
            recipe_data = await self._extract_quick_sources(soup, url)
            if not recipe_data:
                recipe_data = await self._extract_recipe_from_soup(soup, url)
            if recipe_data:
                # Save domain fingerprint for faster next run
                try:
                    self._save_domain_fingerprint(url, soup, recipe_data)
                except Exception:
                    pass
                recipe_data = await self._normalize_and_enrich(recipe_data, url, soup)
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
        """Hämtar HTML via delad httpx-klient (HTTP/2, pooling, ETag)."""
        return await _http_client.get_html(url)
    
    async def _fetch_html_with_playwright(self, url: str) -> str:
        """Hämtar HTML med Playwright med resursblockering och tidig exit."""
        # Lazy import if module not available at import time
        global async_playwright
        if async_playwright is None:
            try:
                from playwright.async_api import async_playwright as _ap
                async_playwright = _ap
            except Exception as e:
                raise CrawlerException(f"Playwright not available: {e}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport=None)
            page = await context.new_page()

            # Blockera tunga resurser
            async def _route_handler(route, request):
                rtype = request.resource_type
                if rtype in ("image", "media", "font") or any(x in request.url for x in ("analytics", "googletagmanager", "doubleclick")):
                    return await route.abort()
                return await route.continue_()

            await page.route("**/*", _route_handler)
            page.set_default_timeout(self.playwright_timeout)

            try:
                await page.goto(url, wait_until='domcontentloaded')
                # Snabbt försök: om JSON-LD eller ingredient-list syns, ta content direkt
                try:
                    await page.wait_for_selector('script[type="application/ld+json"]', timeout=2000)
                except Exception:
                    try:
                        await page.wait_for_selector('.ingredients, [itemprop="recipeIngredient"]', timeout=2000)
                    except Exception:
                        pass
                html_content = await page.content()
                return html_content
            finally:
                await context.close()
                await browser.close()

    async def _extract_quick_sources(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Kör JSON-LD, Microdata och HTML-listor parallellt och returnerar första användbara resultatet."""
        # Try domain fingerprint first
        try:
            fp = self._get_domain_fingerprint(url)
            if fp:
                res = self._extract_using_fingerprint(soup, fp)
                if res and isinstance(res.get('ingredients'), list) and len(res['ingredients']) >= 2:
                    return res
        except Exception:
            pass
        
        async def _jsonld():
            try:
                result = self._extract_from_jsonld(soup)
                if result and self._validate_swedish_recipe(result):
                    return result
                return None
            except Exception:
                return None

        async def _micro():
            try:
                result = self._extract_from_microdata(soup)
                if result and self._validate_swedish_recipe(result):
                    return result
                return None
            except Exception:
                return None

        async def _htmll():
            try:
                result = self._extract_from_html_lists(soup)
                if result and self._validate_swedish_recipe(result):
                    return result
                return None
            except Exception:
                return None

        async def _swedish_fallback():
            """Extra fallback för svenska receptsajter utan strukturerad data"""
            try:
                # Försök hitta svenska recept via heuristik
                result = self._extract_swedish_recipe_heuristic(soup)
                if result and self._validate_swedish_recipe(result):
                    return result
                return None
            except Exception:
                return None

        tasks = [asyncio.create_task(coro()) for coro in (_jsonld, _micro, _htmll, _swedish_fallback)]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        winner: Optional[Dict[str, Any]] = None
        for d in done:
            try:
                res = d.result()
                if res and isinstance(res.get('ingredients'), list) and len(res['ingredients']) >= 2:
                    winner = res
                    break
            except Exception:
                continue
        # Avbryt övriga
        for p in pending:
            p.cancel()
        if winner:
            # Lägg till metadata
            winner['id'] = str(uuid.uuid4())
            winner['source_url'] = url
            winner['extracted_at'] = datetime.now().isoformat()
            # Bild: använd befintlig eller extrahera från sidan, ladda ner
            img_candidate = winner.get('image_url') or winner.get('img')
            if isinstance(img_candidate, list):
                img_candidate = next((i for i in img_candidate if isinstance(i, str)), None)
            if not img_candidate:
                try:
                    img_candidate = self.content_extractor.find_image_url(soup, url)
                except Exception:
                    img_candidate = None
            if img_candidate and isinstance(img_candidate, str):
                try:
                    job_id = str(uuid.uuid4())
                    downloaded_image_path = await download_image_async(img_candidate, job_id)
                    winner['image_url'] = downloaded_image_path
                except Exception:
                    winner['image_url'] = img_candidate
            else:
                winner['image_url'] = None
            if 'img' in winner:
                try:
                    del winner['img']
                except Exception:
                    pass
            return winner
        return None

    def _extract_swedish_recipe_heuristic(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Heuristisk extraktion för svenska receptsajter utan strukturerad data
        """
        try:
            # Hitta titel - försök med vanliga svenska mönster
            title = None
            title_selectors = [
                'h1', 'h2', '.recipe-title', '.recept-titel', '.post-title', 
                '.entry-title', '[class*="title"]', '[class*="rubrik"]'
            ]
            
            for selector in title_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) > 3 and len(text) < 100:
                            title = text
                            break
                except Exception:
                    continue
            
            # Hitta ingredienser - leta efter listor med svenska mått
            ingredients = []
            ingredient_lists = soup.find_all(['ul', 'ol'])
            
            for list_element in ingredient_lists:
                list_text = list_element.get_text().lower()
                # Kolla om detta ser ut som en ingredienslista
                if ('ingrediens' in list_text or any(unit in list_text for unit in ['g', 'dl', 'msk', 'tsk', 'krm'])) and len(list_text) > 20:
                    items = list_element.find_all('li')
                    for item in items:
                        text = item.get_text(strip=True)
                        if text and len(text) > 3:
                            ingredients.append(text)
                    if ingredients:
                        break
            
            # Hitta instruktioner - leta efter numrerade listor eller steg
            instructions = []
            instruction_containers = soup.find_all(['ol', 'div', 'section'])
            
            for container in instruction_containers:
                container_text = container.get_text().lower()
                if ('instruktion' in container_text or 'gör så här' in container_text or 
                    'steg' in container_text or any(str(i) in container_text for i in range(1, 10))):
                    
                    # Försök hitta listobjekt eller stycken med numrering
                    items = container.find_all(['li', 'p'])
                    for item in items:
                        text = item.get_text(strip=True)
                        if text and len(text) > 10 and not text.startswith(('©', 'Tid:', 'Portioner:')):
                            instructions.append(text)
                    if instructions:
                        break
            
            # Om vi har tillräckligt med data, returnera resultat
            if ingredients or instructions:
                return {
                    'title': title or 'Recept',
                    'ingredients': ingredients,
                    'instructions': instructions,
                    'source': 'swedish_heuristic'
                }
            
        except Exception as e:
            logger.debug(f"Swedish heuristic extraction failed: {e}")
        
        return None

    def _domain_from_url(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _get_domain_fingerprint(self, url: str) -> Optional[dict]:
        domain = self._domain_from_url(url)
        if not domain:
            return None
        return db.get_domain_fingerprint(domain)

    def _save_domain_fingerprint(self, url: str, soup: BeautifulSoup, data: Dict[str, Any]):
        domain = self._domain_from_url(url)
        if not domain:
            return
        # Record selectors that worked for ingredients
        selectors: List[str] = []
        for sel in ['.ingredients', '[class*="ingredient"]', '[itemprop="recipeIngredient"]']:
            try:
                if soup.select_one(sel):
                    selectors.append(sel)
            except Exception:
                continue
        # Record JSON-LD schema keys used
        schema_keys = ['name', 'description', 'recipeIngredient', 'recipeInstructions', 'image']
        schema = {k: True for k in schema_keys}
        db.upsert_domain_fingerprint(domain, selectors=selectors or None, schema=schema)

    def _extract_using_fingerprint(self, soup: BeautifulSoup, fp: dict) -> Optional[Dict[str, Any]]:
        selectors = (fp or {}).get('selectors') or []
        if selectors:
            for sel in selectors:
                try:
                    node = soup.select_one(sel)
                except Exception:
                    node = None
                if not node:
                    continue
                items: List[str] = []
                base = node
                if isinstance(base, Tag) and base.name in ('li', 'span') and base.parent:
                    base = base.parent
                for li in (base.find_all('li') if isinstance(base, Tag) else []):
                    text = li.get_text(separator=' ', strip=True)
                    if not text:
                        continue
                    tnorm = re.sub(r'\s+', ' ', text)
                    low = tnorm.lower()
                    if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(tnorm):
                        continue
                    items.append(tnorm)
                if not items and isinstance(node, Tag):
                    text = node.get_text(separator='\n', strip=True)
                    raw = [t.strip() for t in text.split('\n') if t.strip()]
                    items = []
                    for t in raw:
                        tnorm = re.sub(r'\s+', ' ', t)
                        low = tnorm.lower()
                        if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(tnorm):
                            continue
                        items.append(tnorm)
                if len(items) >= 2:
                    # Title heuristic
                    title = None
                    for h in soup.find_all(['h1','h2']):
                        t = h.get_text(strip=True)
                        if t and len(t) >= 3:
                            title = t
                            break
                    return {
                        'title': title or 'Recipe',
                        'description': '',
                        'ingredients': items,
                        'instructions': [],
                        'source': 'fingerprint'
                    }
        return None

    def _extract_from_jsonld(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
        for sc in scripts:
            try:
                # Rensa potentiella JavaScript-kommentarer och felformaterad JSON
                script_content = sc.string or sc.text or ''
                if not script_content:
                    continue
                
                # Ta bort JavaScript-kommentarer som kan orsaka JSON-fel
                script_content = re.sub(r'//.*?\n', '', script_content)
                script_content = re.sub(r'/\*.*?\*/', '', script_content, flags=re.DOTALL)
                
                data = json.loads(script_content)
            except json.JSONDecodeError as e:
                # Försök att hitta och extrahera JSON från potentiellt skadad markup
                try:
                    json_match = re.search(r'\{.*\}', script_content, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                    else:
                        continue
                except Exception:
                    continue
            except Exception:
                continue
            candidates = []
            if isinstance(data, dict):
                candidates.append(data)
                if '@graph' in data and isinstance(data['@graph'], list):
                    candidates.extend(data['@graph'])
            elif isinstance(data, list):
                candidates.extend(data)
            
            def _flatten_instructions(instr_obj) -> List[str]:
                out: List[str] = []
                if not instr_obj:
                    return out
                # String
                if isinstance(instr_obj, str):
                    t = instr_obj.strip()
                    if t:
                        out.append(t)
                    return out
                # List
                if isinstance(instr_obj, list):
                    for it in instr_obj:
                        out.extend(_flatten_instructions(it))
                    return out
                # Dict: HowToStep or HowToSection
                if isinstance(instr_obj, dict):
                    # HowToSection style
                    items = instr_obj.get('itemListElement') or instr_obj.get('steps')
                    if items:
                        out.extend(_flatten_instructions(items))
                    # Direct text/name fallback
                    txt = instr_obj.get('text') or instr_obj.get('name') or instr_obj.get('description')
                    if isinstance(txt, str) and txt.strip():
                        out.append(txt.strip())
                return out
            def _iso8601_to_minutes(val: Optional[str]) -> Optional[int]:
                if not val or not isinstance(val, str):
                    return None
                # Very simple ISO8601 duration parser for PT#H#M
                try:
                    h = 0
                    m = 0
                    m_h = re.search(r"(\d+)H", val)
                    m_m = re.search(r"(\d+)M", val)
                    if m_h:
                        h = int(m_h.group(1))
                    if m_m:
                        m = int(m_m.group(1))
                    if h == 0 and m == 0:
                        return None
                    return h*60 + m
                except Exception:
                    return None
            for obj in candidates:
                try:
                    t = obj.get('@type') if isinstance(obj, dict) else None
                    if isinstance(t, list):
                        is_recipe = any(isinstance(x, str) and x.lower() == 'recipe' for x in t)
                    else:
                        is_recipe = isinstance(t, str) and t.lower() == 'recipe'
                    if not is_recipe:
                        continue
                    title = (obj.get('name') or '').strip()
                    desc = (obj.get('description') or '').strip()
                    img = obj.get('image')
                    if isinstance(img, dict):
                        img = img.get('url') or img.get('@id')
                    ingredients = obj.get('recipeIngredient') or obj.get('ingredients') or []
                    if isinstance(ingredients, str):
                        ingredients = [ingredients]
                    instructions_raw = obj.get('recipeInstructions') or obj.get('instructions') or []
                    instructions: List[str] = _flatten_instructions(instructions_raw)
                    result = {
                        'title': title or 'Recipe',
                        'description': desc or '',
                        'ingredients': ingredients,
                        'instructions': instructions or [],
                        'img': img if isinstance(img, str) else None,
                        'source': 'jsonld'
                    }
                    # Servings and times
                    ry = obj.get('recipeYield')
                    if isinstance(ry, (str, int)):
                        result['servings'] = str(ry)
                    prep = _iso8601_to_minutes(obj.get('prepTime'))
                    cook = _iso8601_to_minutes(obj.get('cookTime'))
                    total = _iso8601_to_minutes(obj.get('totalTime'))
                    if prep is not None:
                        result['prep_time_minutes'] = prep
                    if cook is not None:
                        result['cook_time_minutes'] = cook
                    if total is not None:
                        result['total_time_minutes'] = total
                    if result['img']:
                        result['image_url'] = result['img']
                    
                    # Ytterligare validering för svenska recept
                    if self._validate_swedish_recipe(result):
                        return result
                    else:
                        logger.debug("JSON-LD found but doesn't look like a valid Swedish recipe")
                        continue
                except Exception:
                    continue
        return None

    def _validate_swedish_recipe(self, recipe_data: Dict[str, Any]) -> bool:
        """
        Validerar att extraherade receptdata ser ut som ett giltigt svenskt recept
        """
        # Grundläggande validering
        if not recipe_data:
            return False
        
        # Måste ha antingen ingredienser eller instruktioner
        ingredients = recipe_data.get('ingredients', [])
        instructions = recipe_data.get('instructions', [])
        
        if not ingredients and not instructions:
            return False
        
        # Kolla för svenska recept-indikatorer
        title = (recipe_data.get('title') or '').lower()
        description = (recipe_data.get('description') or '').lower()
        
        # Svenska nyckelord i titel/beskrivning
        swedish_keywords = ['recept', 'ingrediens', 'instruktion', 'portion', 'servering', 'mat', 'rätt']
        has_swedish_indicator = any(keyword in title or keyword in description for keyword in swedish_keywords)
        
        # Svenska mått i ingredienser
        has_swedish_measurements = False
        for ingredient in ingredients:
            if isinstance(ingredient, str):
                if any(unit in ingredient.lower() for unit in ['g', 'kg', 'dl', 'ml', 'l', 'msk', 'tsk', 'krm', 'st', 'klyfta']):
                    has_swedish_measurements = True
                    break
        
        # Antingen svenska indikatorer eller svenska mått
        return has_swedish_indicator or has_swedish_measurements or len(ingredients) >= 3

    def _extract_from_microdata(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        # Basic microdata parsing: look for itemtype containing Recipe
        node = soup.find(attrs={'itemtype': re.compile('Recipe', re.I)})
        if not node:
            return None
        def get_itemprop(name: str) -> Optional[str]:
            el = node.find(attrs={'itemprop': name})
            if not el:
                return None
            if el.get('content'):
                return el['content']
            return el.get_text(strip=True)
        title = get_itemprop('name') or 'Recipe'
        desc = get_itemprop('description') or ''
        img = None
        img_el = node.find(attrs={'itemprop': 'image'})
        if img_el:
            img = img_el.get('content') or img_el.get('src') or img_el.get('href')
        ingredients: List[str] = []
        for ing in node.find_all(attrs={'itemprop': re.compile('recipeIngredient|ingredients', re.I)}):
            text = ing.get('content') or ing.get_text(strip=True)
            if text:
                ingredients.append(text)
        instructions: List[str] = []
        for inst in node.find_all(attrs={'itemprop': re.compile('recipeInstructions|step', re.I)}):
            text = inst.get('content') or inst.get_text(strip=True)
            if text:
                instructions.append(text)
        if len(ingredients) < 1:
            return None
        # Servings and times
        def _iso8601_to_minutes(val: Optional[str]) -> Optional[int]:
            if not val or not isinstance(val, str):
                return None
            try:
                h = 0
                m = 0
                m_h = re.search(r"(\d+)H", val)
                m_m = re.search(r"(\d+)M", val)
                if m_h:
                    h = int(m_h.group(1))
                if m_m:
                    m = int(m_m.group(1))
                if h == 0 and m == 0:
                    return None
                return h*60 + m
            except Exception:
                return None
        servings = get_itemprop('recipeYield')
        prep = _iso8601_to_minutes(get_itemprop('prepTime'))
        cook = _iso8601_to_minutes(get_itemprop('cookTime'))
        total = _iso8601_to_minutes(get_itemprop('totalTime'))
        out = {
            'title': title,
            'description': desc,
            'ingredients': ingredients,
            'instructions': instructions,
            'img': img,
            'source': 'microdata'
        }
        if servings:
            out['servings'] = servings
        if prep is not None:
            out['prep_time_minutes'] = prep
        if cook is not None:
            out['cook_time_minutes'] = cook
        if total is not None:
            out['total_time_minutes'] = total
        if img:
            out['image_url'] = img
        return out

    def _extract_from_html_lists(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        # Look for common ingredient list containers
        container = None
        selectors = [
            '.ingredients',
            '[class*="ingredient"]',
            '[itemprop="recipeIngredient"]',
            'ul li:has(span[class*="ingredient"])'
        ]
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el:
                    container = el
                    break
            except Exception:
                continue
        if not container:
            return None
        # Gather list items within the container
        items: List[str] = []
        # If container is a list item, expand to its parent list
        base = container
        if isinstance(base, Tag) and base.name in ('li', 'span') and base.parent:
            base = base.parent
        for li in (base.find_all('li') if isinstance(base, Tag) else []):
            text = li.get_text(separator=' ', strip=True)
            if not text:
                continue
            text_norm = re.sub(r'\s+', ' ', text)
            # Drop pure time/meta rows frequently injected near ingredients
            lower = text_norm.lower()
            if _RE_TIME_META.search(lower) or _RE_TIME_CLOCK.match(text_norm):
                continue
            items.append(text_norm)
        if not items and isinstance(container, Tag):
            text = container.get_text(separator='\n', strip=True)
            raw = [t.strip() for t in text.split('\n') if t.strip()]
            items = []
            for t in raw:
                tnorm = re.sub(r'\s+', ' ', t)
                low = tnorm.lower()
                if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(tnorm):
                    continue
                items.append(tnorm)
        # Filtrera till ENDAST rader som har mängd + enhet
        filtered_items: List[str] = []
        for t in items:
            amt, unit, rest = _parse_amount_unit(t)
            if amt is not None and unit:
                filtered_items.append(f"{_format_quantity(amt, unit)} {rest}".strip())
        items = filtered_items

        if len(items) < 1:
            return None
        # Title/desc best-effort
        title = None
        for h in soup.find_all(['h1','h2']):
            t = h.get_text(strip=True)
            if t and len(t) >= 3:
                title = t
                break
        desc = ''
        return {
            'title': title or 'Recipe',
            'description': desc,
            'ingredients': items,
            'instructions': [],
            'source': 'html'
        }

    async def _normalize_and_enrich(self, data: Dict[str, Any], url: str, soup: Optional[BeautifulSoup] = None) -> Dict[str, Any]:
        """Ensure ingredients are structured and image_url is resolved/downloaded."""
        out = dict(data)
        # Language detection (simple heuristic sv/en)
        try:
            text_blob = ' '.join([
                str(out.get('title') or ''),
                str(out.get('description') or ''),
                ' '.join([i if isinstance(i, str) else (i.get('name') or '') for i in (out.get('ingredients') or [])])
            ]).lower()
            sv_hits = sum(1 for w in ['och','gör','så','här','portioner','tillagning','ingredienser'] if w in text_blob)
            en_hits = sum(1 for w in ['and','servings','method','directions','ingredients'] if w in text_blob)
            out['lang'] = 'sv' if sv_hits >= en_hits else 'en'
        except Exception:
            out['lang'] = 'sv'
        # Ingredients → remove time-only meta lines if leaked into ingredient container, then structure
        ings = out.get('ingredients')
        if isinstance(ings, list):
            filtered: List[Any] = []
            for it in ings:
                try:
                    if isinstance(it, str):
                        t = re.sub(r"\s+", " ", it).strip()
                        low = t.lower()
                        if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(t):
                            continue
                        filtered.append(t)
                    elif isinstance(it, dict):
                        nm = re.sub(r"\s+", " ", str(it.get('name') or it.get('raw') or '')).strip()
                        low = nm.lower()
                        if nm and (_RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(nm)):
                            continue
                        filtered.append(it)
                    else:
                        filtered.append(it)
                except Exception:
                    filtered.append(it)
            ings = filtered
            if len(ings) == 0 or (len(ings) > 0 and isinstance(ings[0], str)):
                out['ingredients'] = _to_structured_ingredients([str(x) for x in ings])
            else:
                out['ingredients'] = ings
            # Hård filtrering: behåll endast rader med både mängd och enhet
            try:
                out['ingredients'] = [i for i in out['ingredients'] if isinstance(i, dict) and i.get('amount') is not None and bool(i.get('unit'))]
            except Exception:
                pass
        # Instructions → if empty, try DOM extraction
        if not out.get('instructions') or not isinstance(out.get('instructions'), list) or len(out.get('instructions')) == 0:
            try:
                if soup is None:
                    html = await self._fetch_html_simple(url)
                    soup = BeautifulSoup(html, 'html.parser')
                steps = self._extract_instructions_from_dom(soup)
                if steps:
                    out['instructions'] = steps
            except Exception:
                pass
        # Servings & time fallback via regex if missing
        try:
            if soup is None:
                html = await self._fetch_html_simple(url)
                soup = BeautifulSoup(html, 'html.parser')
            text_all = soup.get_text(' ', strip=True).lower()
            if not out.get('servings'):
                m_serv = re.search(r"(\d+[–\-]\d+|\d+)\s*(portion|portioner|servings|people)", text_all)
                if m_serv:
                    out['servings'] = m_serv.group(1)
            def _mins(x: Optional[str]) -> Optional[int]:
                if not x:
                    return None
                try:
                    return int(x)
                except Exception:
                    return None
            if 'prep_time_minutes' not in out or out.get('prep_time_minutes') is None:
                m = re.search(r"(\d+)\s*(min|minutes|minute|minuter|tim|min|h)\s*(prep|förbered|preparation|förberedel)", text_all)
                if m:
                    out['prep_time_minutes'] = _mins(m.group(1))
            if 'cook_time_minutes' not in out or out.get('cook_time_minutes') is None:
                m = re.search(r"(\d+)\s*(min|minutes|minute|minuter|tim|min|h)\s*(cook|koka|tillagning|tillaga|stek|bak)", text_all)
                if m:
                    out['cook_time_minutes'] = _mins(m.group(1))
            if 'total_time_minutes' not in out or out.get('total_time_minutes') is None:
                m = re.search(r"klar\s*på\s*(\d+)\s*(min|minutes|minute|minuter|tim|min|h)", text_all)
                if m:
                    out['total_time_minutes'] = _mins(m.group(1))
        except Exception:
            pass
        # Resolve image
        img_candidate = out.get('image_url') or out.get('img')
        if isinstance(img_candidate, list):
            img_candidate = next((i for i in img_candidate if isinstance(i, str)), None)
        # If already a local downloads path, keep it
        if isinstance(img_candidate, str) and img_candidate.startswith('/downloads/'):
            pass
        elif not img_candidate:
            try:
                if soup is None:
                    html = await self._fetch_html_simple(url)
                    soup = BeautifulSoup(html, 'html.parser')
                img_candidate = self.content_extractor.find_image_url(soup, url)
                # ICA fallback: vissa sidor saknar OG, hämta första receptbild inom content
                if not img_candidate:
                    try:
                        el = soup.select_one('main img, article img, [class*="recipe"] img')
                        if el and el.get('src'):
                            img_candidate = urljoin(url, el['src'])
                    except Exception:
                        pass
            except Exception:
                img_candidate = None
        if img_candidate and isinstance(img_candidate, str) and not img_candidate.startswith('/downloads/'):
            try:
                job_id = str(uuid.uuid4())
                out['image_url'] = await download_image_async(img_candidate, job_id)
            except Exception:
                out['image_url'] = img_candidate
        else:
            out['image_url'] = out.get('image_url') or None
        if 'img' in out:
            try:
                del out['img']
            except Exception:
                pass
        return out
    
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
            
            # 5. Försök deterministisk parser först; gate LLM om <70% har amount+unit
            # Heuristic: try list extraction on cleaned main_content
            lines = []
            for li in main_content.find_all('li'):
                txt = li.get_text(' ', strip=True)
                if txt:
                    tnorm = re.sub(r'\s+', ' ', txt)
                    low = tnorm.lower()
                    if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(tnorm):
                        continue
                    lines.append(tnorm)
            if not lines:
                # fallback split by newline
                raw = [t.strip() for t in main_content.get_text('\n', strip=True).split('\n') if t.strip()]
                lines = []
                for t in raw:
                    tnorm = re.sub(r'\s+', ' ', t)
                    low = tnorm.lower()
                    if _RE_TIME_META.search(low) or _RE_TIME_CLOCK.match(tnorm):
                        continue
                    lines.append(tnorm)

            # Ingredienslinjer: filtrera hårt till mängd+enhet
            parsed_rows = []
            valid = 0
            strict_lines: List[str] = []
            for row in lines:
                if len(row) < 2:
                    continue
                key = hashlib.sha1(row.strip().lower().encode('utf-8')).hexdigest()
                cached = db.get_ingredient_parse_cache(key)
                if cached:
                    try:
                        parsed = json.loads(cached)
                        parsed_rows.append(parsed)
                        if parsed.get('amount') is not None and parsed.get('unit'):
                            valid += 1
                        continue
                    except Exception:
                        pass
                amount, unit, rest = _parse_amount_unit(row)
                parsed = {
                    'original': row,
                    'amount': amount,
                    'unit': unit,
                    'item': rest,
                    'note': None,
                    'amount_text': None,
                }
                if amount is not None and unit:
                    valid += 1
                    strict_lines.append(f"{_format_quantity(amount, unit)} {rest}".strip())
                parsed_rows.append(parsed)
                try:
                    db.upsert_ingredient_parse_cache(key, row, json.dumps(parsed))
                except Exception:
                    pass

            ready_ratio = (valid / max(1, len(parsed_rows))) if parsed_rows else 0.0
            use_llm = ready_ratio < 0.7

            if not use_llm and len(strict_lines) >= 2:
                structured = _to_structured_ingredients(strict_lines)
                recipe_data = {
                    'title': None,
                    'description': None,
                    'ingredients': structured,
                    'instructions': [],
                }
            else:
                # 5b. Använd AI som fallback
                if self.ai_processor is None:
                    try:
                        self.ai_processor = AIProcessor()
                    except Exception as e:
                        logger.warning(f"AI unavailable, skipping LLM fallback: {e}")
                        # Degrade: return minimal structured ingredients with DOM instructions best-effort
                        structured = _to_structured_ingredients(lines)
                        recipe_data = {
                            'title': None,
                            'description': None,
                            'ingredients': structured,
                            'instructions': self._extract_instructions_from_dom(cleaned_soup) or [],
                        }
                if self.ai_processor is not None:
                    recipe_data = self.ai_processor.extract_recipe_with_ai(content_text, image_url)
            
            # Sanera instruktioner och säkra servings
            try:
                if isinstance(recipe_data.get('instructions'), list):
                    recipe_data['instructions'] = _filter_and_trim_instructions(recipe_data['instructions'])
            except Exception:
                pass
            # fallback servings från text om saknas
            if not recipe_data.get('servings'):
                try:
                    m = _RE_SERVINGS.search(content_text)
                    if m:
                        recipe_data['servings'] = m.group(1)
                except Exception:
                    pass

            # 6. Validera resultatet (om instruktioner saknas försök DOM-extraktion)
            if not self.validator.validate_recipe(recipe_data):
                try:
                    fallback_instructions = self._extract_instructions_from_dom(cleaned_soup)
                    if fallback_instructions:
                        recipe_data['instructions'] = _filter_and_trim_instructions(fallback_instructions)
                except Exception:
                    pass
                if not self.validator.validate_recipe(recipe_data):
                    logger.warning("Recipe validation failed")
                    return None
            
            # 7. Ladda ner bild om den finns
            img_candidate = recipe_data.get('image_url') or recipe_data.get('img') or image_url
            if isinstance(img_candidate, list):
                img_candidate = next((i for i in img_candidate if isinstance(i, str)), None)
            if img_candidate and isinstance(img_candidate, str):
                job_id = str(uuid.uuid4())
                try:
                    downloaded_image_path = await download_image_async(img_candidate, job_id)
                    recipe_data['image_url'] = downloaded_image_path
                    if 'img' in recipe_data:
                        del recipe_data['img']
                    logger.info(f"Image downloaded: {downloaded_image_path}")
                except Exception:
                    # Fallback: behåll original-URL om nedladdning misslyckas
                    recipe_data['image_url'] = img_candidate
                    if 'img' in recipe_data:
                        try:
                            del recipe_data['img']
                        except Exception:
                            pass
            else:
                recipe_data['image_url'] = None
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

    def _extract_instructions_from_dom(self, soup: BeautifulSoup) -> List[str]:
        # 1) Direct structured lists (ordered and unordered)
        selectors = [
            '[class*="instruction"] li',
            '[itemprop="recipeInstructions"] li',
            'ol li',
            'ul li',
            '.steps li',
            '.method li',
            '.how-to-step',
            '.direction',
            '.directions__item',
            '.method__step',
            '[itemprop="step"]',
        ]
        steps: List[str] = []
        try:
            for sel in selectors:
                for li in soup.select(sel):
                    txt = li.get_text(' ', strip=True)
                    if not txt:
                        continue
                    t = txt.strip()
                    if len(t) <= 3 or t.lower().startswith('gör så här'):
                        continue
                    tl = t.lower()
                    # Starta vid första riktiga steget
                    if not steps:
                        if re.match(r'^(?:\d+\.|\d+\)|steg\s*\d+)', tl):
                            steps.append(t)
                        elif re.match(r'^(värm|hacka|skala|vispa|blanda|stek|koka|rör|sätt|lägg|häll|grädda|bryn|skär|smält|tillsätt)\b', tl):
                            steps.append(t)
                        else:
                            continue
                    else:
                        steps.append(t)
                if steps:
                    return steps
        except Exception:
            pass
        # 2) Find heading with "Gör så här" / "Tillagning" and collect following siblings paragraphs/lists
        try:
            heading = None
            for tag in soup.find_all(['h1','h2','h3','h4','h5','strong']):
                t = (tag.get_text(' ', strip=True) or '').lower()
                if 'gör så här' in t or 'instructions' in t or 'tillagning' in t or 'så här gör du' in t or 'method' in t or 'directions' in t:
                    heading = tag
                    break
            if heading:
                # walk next elements for a limited range
                nxt = heading.parent if heading.parent else heading
                # search within next siblings
                limit = 0
                node = nxt
                while node and limit < 8:
                    node = node.find_next_sibling()
                    limit += 1
                    if not node:
                        break
                    # list items
                    for li in node.find_all('li'):
                        txt = li.get_text(' ', strip=True)
                        if not txt:
                            continue
                        t = txt.strip()
                        if len(t) <= 3:
                            continue
                        tl = t.lower()
                        if not steps:
                            if re.match(r'^(?:\d+\.|\d+\)|steg\s*\d+)', tl):
                                steps.append(t)
                            elif re.match(r'^(värm|hacka|skala|vispa|blanda|stek|koka|rör|sätt|lägg|häll|grädda|bryn|skär|smält|tillsätt)\b', tl):
                                steps.append(t)
                            else:
                                continue
                        else:
                            steps.append(t)
                    # paragraph fallbacks
                    if not steps:
                        # prioritize paragraphs inside likely instruction containers
                        for p in node.find_all(['p', 'div']):
                            cls = ' '.join(p.get('class', [])).lower()
                            if any(k in cls for k in ['instruction', 'step', 'method']):
                                txt = p.get_text(' ', strip=True)
                                if txt and len(txt) > 10 and not txt.lower().startswith('gör så här'):
                                    steps.append(txt)
                        # generic paragraphs as a fallback
                        if not steps:
                            for p in node.find_all('p'):
                                txt = p.get_text(' ', strip=True)
                                if not txt:
                                    continue
                                t = txt.strip()
                                if len(t) <= 10 or t.lower().startswith('gör så här'):
                                    continue
                                tl = t.lower()
                                if not steps:
                                    if re.match(r'^(?:\d+\.|\d+\)|steg\s*\d+)', tl):
                                        steps.append(t)
                                    elif re.match(r'^(värm|hacka|skala|vispa|blanda|stek|koka|rör|sätt|lägg|häll|grädda|bryn|skär|smält|tillsätt)\b', tl):
                                        steps.append(t)
                                    else:
                                        continue
                                else:
                                    steps.append(t)
                    if steps:
                        return steps
        except Exception:
            pass
        return []

# Global, lazily initialized instance for API use
crawler_instance: Optional[FlexibleWebCrawler] = None

def _get_crawler_instance() -> FlexibleWebCrawler:
    global crawler_instance
    if crawler_instance is None:
        crawler_instance = FlexibleWebCrawler()
    return crawler_instance

async def scrape_recipe_from_url(url: str) -> Dict[str, Any]:
    """
    Public API för att crawla recept från URL
    Denna funktion exponeras via API-endpointen
    """
    return await _get_crawler_instance().crawl_recipe_from_url(url)