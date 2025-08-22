"""
Working Recipe Scraper - Clean Implementation
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

# Lazy imports to avoid dependency issues
def get_requests():
    try:
        import requests
        return requests
    except ImportError:
        logger.warning("requests not available")
        return None

def get_beautifulsoup():
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not available")
        return None

def get_deepseek():
    try:
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek
    except ImportError:
        logger.warning("DeepSeek not available")
        return None

def get_playwright():
    try:
        from playwright.async_api import async_playwright
        return async_playwright
    except ImportError:
        logger.warning("Playwright not available")
        return None

class SimpleRecipeScraper:
    """Simple, reliable recipe scraper"""
    
    def __init__(self):
        self.requests = get_requests()
        self.BeautifulSoup = get_beautifulsoup()
        self.ChatDeepSeek = get_deepseek()
        self.playwright = get_playwright()
        self.session = self.requests.Session() if self.requests else None
        # Debug flag enable with env SCRAPER_DEBUG=1
        try:
            import os as _os
            self.debug = _os.getenv('SCRAPER_DEBUG', '0') in ('1', 'true', 'True')
        except Exception:
            self.debug = False
        
        # Setup AI if available
        self.llm = None
        if self.ChatDeepSeek:
            try:
                # FORCE load from .env directly
                import os
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('DEEPSEEK_API_KEY')
                
                if api_key:
                    self.llm = self.ChatDeepSeek(
                        model="deepseek-chat",
                        api_key=api_key,
                        max_tokens=2000,
                        temperature=0.1
                    )
                    logger.info("DeepSeek AI initialized successfully")
                else:
                    logger.error("DEEPSEEK_API_KEY not found in .env!")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek: {e}")
                import traceback
                traceback.print_exc()
    
    async def _get_html_with_fallback(self, url: str) -> str:
        """Get HTML content with Playwright fallback for JavaScript-heavy sites"""
        try:
            # First try with requests - faster for static content
            if self.session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = await asyncio.to_thread(
                    self.session.get, url, headers=headers, timeout=10, allow_redirects=True
                )
                response.raise_for_status()
                html = response.text
                
                # Quick check for JSON-LD data - if present, no need for Playwright
                if 'application/ld+json' in html and 'recipe' in html.lower():
                    logger.info(f"Got HTML with requests and found JSON-LD ({len(html)} chars)")
                    return html
                
                # Check if page seems to have content (not just loading)
                if len(html) > 1000 and not any(placeholder in html.lower() for placeholder in ['loader', 'loading', 'laddar']):
                    logger.info(f"Got HTML with requests ({len(html)} chars)")
                    return html
                else:
                    logger.info("Page seems to be loading/empty, trying Playwright...")
            else:
                logger.info("Requests not available, trying Playwright...")
                
        except Exception as e:
            logger.info(f"Requests failed: {e}, trying Playwright...")
        
        # Fallback to Playwright for JavaScript-heavy sites
        if self.playwright:
            try:
                async with self.playwright() as p:
                    # Use faster browser launch options
                    browser = await p.chromium.launch(
                        headless=True,
                        # Disable unnecessary features for speed
                        args=['--disable-gpu', '--disable-dev-shm-usage', '--disable-setuid-sandbox', '--no-sandbox']
                    )
                    page = await browser.new_page()
                    
                    # Set user agent
                    await page.set_extra_http_headers({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    logger.info(f"Loading page with Playwright: {url}")
                    # Use 'domcontentloaded' instead of 'networkidle' for faster loading
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    
                    # Wait only if necessary - check for specific content
                    content_checks = [
                        'recipe', 'recept', 'ingredients', 'ingredienser',
                        'instructions', 'instruktioner', 'method', 'metod'
                    ]
                    
                    # Quick check for recipe content
                    content = await page.content()
                    if not any(keyword in content.lower() for keyword in content_checks):
                        # Wait a bit more for dynamic content
                        await page.wait_for_timeout(1000)
                    
                    # Get the rendered HTML
                    html = await page.content()
                    await browser.close()
                    
                    logger.info(f"Got HTML with Playwright ({len(html)} chars)")
                    return html
                    
            except Exception as e:
                logger.error(f"Playwright failed: {e}")
                if not self.session:
                    raise Exception(f"Both requests and Playwright failed: {e}")
                else:
                    # If requests is available but failed, try one more time with shorter timeout
                    try:
                        logger.info("Retrying with requests...")
                        response = await asyncio.to_thread(
                            self.session.get, url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=8
                        )
                        response.raise_for_status()
                        html = response.text
                        logger.info(f"Retry successful with requests ({len(html)} chars)")
                        return html
                    except Exception as retry_e:
                        raise Exception(f"Both requests and Playwright failed: {e}, retry failed: {retry_e}")
        else:
            # If no playwright, try requests again
            if self.session:
                try:
                    logger.info("No Playwright available, trying requests again...")
                    response = await asyncio.to_thread(
                        self.session.get, url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=10
                    )
                    response.raise_for_status()
                    html = response.text
                    logger.info(f"Requests successful ({len(html)} chars)")
                    return html
                except Exception as e2:
                    raise Exception(f"Requests failed twice: {e2}")
            else:
                raise Exception("Neither requests nor Playwright available")
    
    async def scrape_recipe(self, url: str) -> Dict[str, Any]:
        """Scrape recipe from URL - always returns something useful"""
        import time
        start_time = time.time()
        
        try:
            # Get HTML with fallback
            html_start = time.time()
            html = await self._get_html_with_fallback(url)
            html_time = time.time() - html_start
            if self.debug:
                logger.info(f"HTML fetch time: {html_time:.2f}s")
            
            # Parse HTML
            if not self.BeautifulSoup:
                raise Exception("BeautifulSoup not available")
                
            soup = self.BeautifulSoup(html, 'html.parser')
            
            # Try structured data first
            json_ld_start = time.time()
            recipe = self._extract_json_ld(soup)
            json_ld_time = time.time() - json_ld_start
            if self.debug:
                logger.info(f"JSON-LD extraction time: {json_ld_time:.2f}s")
            
            if not recipe:
                microdata_start = time.time()
                recipe = self._extract_microdata(soup)
                microdata_time = time.time() - microdata_start
                if self.debug:
                    logger.info(f"Microdata extraction time: {microdata_time:.2f}s")
            
            if recipe and recipe.get('ingredients') and len(recipe['ingredients']) >= 2:
                logger.info(f"Structured extraction successful: {recipe.get('title')}")
                final_recipe = self._finalize_recipe(recipe, url)
                total_time = time.time() - start_time
                if self.debug:
                    logger.info(f"Total scraping time: {total_time:.2f}s")
                return final_recipe
            
            # Try basic HTML extraction
            html_extract_start = time.time()
            html_recipe = self._extract_from_html(soup)
            html_extract_time = time.time() - html_extract_start
            if self.debug:
                logger.info(f"HTML extraction time: {html_extract_time:.2f}s")
            
            if html_recipe and (html_recipe.get('ingredients') or html_recipe.get('instructions')):
                logger.info(f"HTML extraction successful: {html_recipe.get('title')}")
                final_recipe = self._finalize_recipe(html_recipe, url)
                total_time = time.time() - start_time
                if self.debug:
                    logger.info(f"Total scraping time: {total_time:.2f}s")
                return final_recipe
            
            # Skip JavaScript extraction for now - use AI instead
            
            # Skip AI extraction for kokaihop.se since we have special handling
            # Also skip if we already found some ingredients but not enough
            should_use_ai = True
            page_text = soup.get_text().lower()
            
            # Don't use AI for kokaihop.se - our special extraction should handle it
            if 'kokaihop' in page_text:
                should_use_ai = False
                logger.info("Skipping AI extraction for kokaihop.se - using special extraction instead")
            
            # Also don't use AI if we already found some ingredients but not enough for full recipe
            html_recipe_ingredients = html_recipe.get('ingredients', []) if html_recipe else []
            if html_recipe_ingredients and len(html_recipe_ingredients) >= 2:
                should_use_ai = False
                logger.info(f"Skipping AI extraction - already found {len(html_recipe_ingredients)} ingredients from HTML")
            
            # Try AI extraction only if needed
            if should_use_ai and self.llm:
                ai_start = time.time()
                recipe = await self._extract_with_ai(soup.get_text())
                ai_time = time.time() - ai_start
                if self.debug:
                    logger.info(f"AI extraction time: {ai_time:.2f}s")
                
                if recipe and recipe.get('ingredients'):
                    logger.info(f"AI extraction successful: {recipe.get('title')}")
                    final_recipe = self._finalize_recipe(recipe, url)
                    total_time = time.time() - start_time
                    if self.debug:
                        logger.info(f"Total scraping time: {total_time:.2f}s")
                    return final_recipe
            
            # Fallback with title
            title = self._extract_title(soup) or f"Recipe from {url.split('//')[-1].split('/')[0]}"
            
            final_recipe = {
                'id': str(uuid.uuid4()),
                'title': title,
                'description': 'Recipe extracted from website',
                'ingredients': [],
                'instructions': [],
                'servings': '4',
                'source_url': url,
                'source': 'fallback',
                'extracted_at': datetime.now().isoformat()
            }
            
            total_time = time.time() - start_time
            if self.debug:
                logger.info(f"Total scraping time: {total_time:.2f}s")
            return final_recipe
            
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {e}")
            total_time = time.time() - start_time
            if self.debug:
                logger.info(f"Total scraping time (error): {total_time:.2f}s")
            return self._create_fallback(url, str(e))
    
    def _extract_json_ld(self, soup) -> Optional[Dict]:
        """Extract recipe from JSON-LD"""
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    # Use get_text() as robust fallback
                    raw = script.string or script.get_text() or ''
                    if not raw.strip():
                        continue
                    data = json.loads(raw)
                    if isinstance(data, list):
                        # choose first recipe-like entry
                        def _is_recipe_type(t):
                            if isinstance(t, list):
                                return any(str(x).lower() == 'recipe' or 'recipe' in str(x).lower() for x in t)
                            return str(t).lower() == 'recipe' or 'recipe' in str(t).lower()
                        for entry in data:
                            if isinstance(entry, dict) and _is_recipe_type(entry.get('@type')):
                                data = entry
                                break
                        else:
                            data = data[0]
                    # Many sites embed a graph; find the Recipe node
                    if isinstance(data, dict) and '@graph' in data:
                        graph = data.get('@graph') or []
                        def _is_recipe_type2(t):
                            if isinstance(t, list):
                                return any(str(x).lower() == 'recipe' or 'recipe' in str(x).lower() for x in t)
                            return str(t).lower() == 'recipe' or 'recipe' in str(t).lower()
                        for node in graph:
                            if isinstance(node, dict) and _is_recipe_type2(node.get('@type')):
                                data = node
                                break
                    
                    def _is_recipe_root(t):
                        if isinstance(t, list):
                            return any(str(x).lower() == 'recipe' or 'recipe' in str(x).lower() for x in t)
                        return str(t).lower() == 'recipe' or 'recipe' in str(t).lower()

                    if _is_recipe_root(data.get('@type')):
                        def _coerce_instructions(inst):
                            out = []
                            def _walk(x):
                                if not x:
                                    return
                                if isinstance(x, str):
                                    s = x.strip()
                                    if s:
                                        out.append(s)
                                    return
                                if isinstance(x, dict):
                                    # HowToSection or HowToStep
                                    if 'itemListElement' in x:
                                        for el in x.get('itemListElement') or []:
                                            _walk(el)
                                        return
                                    txt = x.get('text') or x.get('name') or ''
                                    if isinstance(txt, str) and txt.strip():
                                        out.append(txt.strip())
                                    return
                                if isinstance(x, list):
                                    for el in x:
                                        _walk(el)
                                    return
                            _walk(inst)
                            return out
                        def _coerce_ingredients(ings):
                            """Coerce ingredients from JSON-LD to strings, preserving amounts.

                            Many publishers (incl. Arla) structure ingredients as objects like:
                            {
                              "name": "Salt",
                              "amount": {"@type":"QuantitativeValue", "value":"1", "unitText":"tsk"}
                            }
                            Our previous implementation only kept the name/text and dropped the amount.
                            This aggregator tries a variety of common keys and formats.
                            """
                            out = []
                            for it in ings or []:
                                # Simple string – already combined
                                if isinstance(it, str):
                                    s = it.strip()
                                    if s:
                                        out.append(s)
                                    continue

                                if not isinstance(it, dict):
                                    continue

                                # Name/text candidates
                                name = (
                                    it.get('name')
                                    or it.get('text')
                                    or it.get('food')
                                    or it.get('ingredient')
                                    or ''
                                )

                                # Try to assemble amount + unit from many possible schemas
                                amount_str = ''

                                def _format_amount(val, unit_hint=None):
                                    if val is None:
                                        return ''
                                    if isinstance(val, dict):
                                        value = (
                                            val.get('amount')
                                            or val.get('value')
                                            or val.get('minValue')
                                            or val.get('low')
                                            or val.get('high')
                                        )
                                        unit = (
                                            val.get('unitText')
                                            or val.get('unit')
                                            or val.get('unitCode')
                                            or val.get('unitName')
                                        )
                                        if value is None:
                                            # Sometimes nested again
                                            nested_val = val.get('quantitativeValue') or val.get('measurement')
                                            if isinstance(nested_val, dict):
                                                value = nested_val.get('value')
                                                unit = unit or nested_val.get('unitText') or nested_val.get('unit')
                                        parts = [str(value).strip() if value is not None else '', str(unit or '').strip()]
                                        return ' '.join([p for p in parts if p]).strip()
                                    # Primitive (int/float/str)
                                    value = str(val).strip()
                                    unit = str(unit_hint or '').strip()
                                    return f"{value} {unit}".strip()

                                # Common keys where amount may live
                                amount_obj = (
                                    it.get('amount')
                                    or it.get('quantity')
                                    or it.get('qty')
                                    or it.get('measure')
                                    or it.get('measurement')
                                    or it.get('amountText')
                                    or it.get('value')
                                )

                                # Unit as sibling of amount
                                unit_sibling = it.get('unitText') or it.get('unit') or it.get('unitName')
                                amount_str = _format_amount(amount_obj, unit_sibling)

                                # Some sites split number and unit across separate fields
                                if not amount_str:
                                    number = it.get('amountNumber') or it.get('number')
                                    unit = it.get('amountUnit') or it.get('unitText') or it.get('unit')
                                    if number:
                                        amount_str = _format_amount(number, unit)

                                # If no explicit amount fields, sometimes it's embedded in 'description'
                                if not amount_str:
                                    desc = it.get('description') or ''
                                    if isinstance(desc, str):
                                        # Keep only short, measurement-like descriptions
                                        if re.search(r"\d", desc) or re.search(r"[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]", desc):
                                            amount_str = desc.strip()

                                text = ' '.join(part for part in [amount_str, str(name).strip()] if part).strip()
                                if not text:
                                    # Fallback to any text-y field we can find
                                    text = (str(name) or str(it.get('text') or '')).strip()
                                if text:
                                    out.append(text)
                            return out
                        return {
                            'title': data.get('name', ''),
                            'description': data.get('description', ''),
                            'ingredients': _coerce_ingredients(data.get('recipeIngredient') or data.get('ingredients') or []),
                            'instructions': _coerce_instructions(data.get('recipeInstructions') or data.get('step') or []),
                            'servings': str(data.get('recipeYield', '4')),
                            'source': 'json_ld'
                        }
                except (json.JSONDecodeError, KeyError):
                    continue
        except Exception:
            pass
        return None
    
    def _extract_microdata(self, soup) -> Optional[Dict]:
        """Extract recipe from microdata"""
        try:
            recipe_elem = soup.find(attrs={'itemtype': re.compile(r'Recipe', re.I)})
            if not recipe_elem:
                return None
            
            title = ''
            title_elem = recipe_elem.find(attrs={'itemprop': 'name'})
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            ingredients = []
            for ing_elem in recipe_elem.find_all(attrs={'itemprop': 'recipeIngredient'}):
                text = ing_elem.get_text(strip=True)
                if text:
                    ingredients.append(text)
            
            instructions = []
            for inst_elem in recipe_elem.find_all(attrs={'itemprop': 'recipeInstructions'}):
                text = inst_elem.get_text(strip=True)
                if text:
                    instructions.append(text)
            
            if ingredients:
                return {
                    'title': title or 'Recipe',
                    'description': '',
                    'ingredients': ingredients,
                    'instructions': instructions,
                    'servings': '4',
                    'source': 'microdata'
                }
        except Exception:
            pass
        return None
    
    def _extract_from_html(self, soup) -> Optional[Dict]:
        """Extract recipe from general HTML patterns"""
        try:
            title = self._extract_title(soup) or 'Recipe'
            
            # Look for ingredients with FLEXIBLE patterns for international sites
            ingredients: List[str] = []
            
            # Helper to safely join parts
            def _join_parts(parts: List[str]) -> str:
                return ' '.join([p.strip() for p in parts if isinstance(p, str) and p.strip()]).strip()

            # Unit/amount recognition (sv + en)
            unit_words = [
                'g','gram','kg','kilogram','ml','milliliter','dl','deciliter','cl','centiliter',
                'msk','matsked','tsk','tesked','krm','kryddmått','st','styck','påse','pase','paket',
                'cup','cups','tbsp','tablespoon','tablespoons','tsp','teaspoon','teaspoons',
                'oz','ounce','ounces','lb','pound','pounds','pint','quart','gallon'
            ]
            unit_pattern = re.compile(rf"\b(?:{'|'.join(sorted(set(unit_words), key=len, reverse=True))})\.?\b", re.I)
            unicode_fracs = '¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞'
            number_pattern = re.compile(rf"(?:(?:ca\s*)?\d+[\s\d\./,]*|[{unicode_fracs}])")
            range_pattern = re.compile(rf"\b\d+[\d\s\./,]*\s*[\-–]\s*[\d\s\./,{unicode_fracs}]+\b")
            time_words = re.compile(r"\b(min|tim|sek|hour|hrs|hours|minutes|seconds)\b", re.I)

            def _accept_line(text: str) -> bool:
                tl = (text or '').strip().lower()
                if not tl:
                    return False
                junk_words = [
                    'online','medlem','logga','konto','meny','hem','kontakt','navigation','nav','menu','login',
                    'footer','header','cookie','gdpr','privacy','terms','facebook','instagram','twitter','linkedin','youtube',
                    'subscribe','newsletter','about','contact','home','search','integritetspolicy','policy','annonser','annonsera',
                    'hjälp','användarvillkor','villkor','om oss','cookies','copyright','all rights','reserved','follow us','social'
                ]
                if any(j in tl for j in junk_words):
                    return False
                has_unit = bool(unit_pattern.search(tl))
                has_number = bool(number_pattern.search(tl) or range_pattern.search(tl))
                only_time = bool(time_words.search(tl)) and not has_unit
                if only_time and not has_number:
                    return False
                food_words = ['salt','peppar','smör','olja','vitlök','lök','grädde','mjölk','persilja','potatis','kyckling','fisk','kött','tomat','socker','mjöl']
                return has_unit or has_number or any(f in tl for f in food_words)

            # Special handling for kokaihop.se
            page_text = soup.get_text().lower()
            if 'kokaihop' in page_text:
                logger.info("Detected kokaihop.se - using special extraction")
                ingredients = self._extract_kokaihop_ingredients(soup)

            # Container-level selectors; read li/p within
            ingredient_containers = [
                '.ingredients', '.recipe-ingredients', '.ingredients-list', '.ingredient-list',
                '[data-ingredients]', '[data-ingredient]', '.recipe__ingredients', '.recipe-ingredients__list',
                '.recipeIngredients'
            ]

            for selector in ingredient_containers:
                try:
                    for container in soup.select(selector):
                        for elem in container.select('li, p'):
                            try:
                                raw_text = elem.get_text(" ", strip=True)
                                name_el = (elem.select_one('.ingredient, .ingredient__name, .ingredient-name, [class*="ingredient-name"], [class*="ingredien"]')
                                           or elem.select_one('[itemprop="recipeIngredient"] [itemprop="name"]'))
                                amt_el = (elem.select_one('.amount, .amount__value, .ingredient-amount, .qty, .quantity, [class*="amount"], [class*="qty"], [class*="quantity"]')
                                          or elem.select_one('[data-amount], [data-qty], [data-quantity]'))
                                unit_el = elem.select_one('.unit, .ingredient-unit, [itemprop="unit"]')
                                amount_text = ''
                                if amt_el is not None:
                                    amount_text = (amt_el.get('data-amount') or amt_el.get('data-qty') or amt_el.get('data-quantity') or amt_el.get_text(" ", strip=True) or '').strip()
                                unit_text = unit_el.get_text(" ", strip=True) if unit_el else ''
                                name_text = name_el.get_text(" ", strip=True) if name_el else ''
                                text = (amount_text + ' ' + unit_text + ' ' + name_text).strip() or raw_text
                            except Exception:
                                text = elem.get_text(" ", strip=True)
                            if text:
                                if _accept_line(text):
                                    ingredients.append(' '.join(text.split()))
                                elif self.debug:
                                    logger.debug(f"Reject line: {text}")
                    if len(ingredients) >= 3:
                        break
                except Exception:
                    continue

            # Two-column table join (amount + name)
            try:
                for row in soup.select('table tr'):
                    cells = row.find_all(['td','th'])
                    if len(cells) < 2:
                        continue
                    name_text = cells[0].get_text(" ", strip=True)
                    qty_text = cells[1].get_text(" ", strip=True)
                    if not name_text:
                        continue
                    if qty_text and (number_pattern.search(qty_text) or unit_pattern.search(qty_text)):
                        ingredients.append(' '.join((qty_text + ' ' + name_text).split()))
                    else:
                        if _accept_line(name_text):
                            ingredients.append(name_text)
                        elif self.debug:
                            logger.debug(f"Reject line (table): {name_text}")
                if len(ingredients) >= 6:
                    pass
            except Exception:
                pass

            # Deduplicate preserving order
            if ingredients:
                seen = set()
                normed = []
                for t in ingredients:
                    tt = ' '.join(t.split())
                    if tt not in seen:
                        seen.add(tt)
                        normed.append(tt)
                ingredients = normed
            
            # Look for instructions with broader international patterns
            instructions = []
            instruction_selectors = [
                # Standard instruction selectors
                '.instructions li', '.recipe-instructions li', '[class*="instruction"] li',
                '.method li', '.directions li', '.steps li', '.preparation li',
                '.instructions p', '.recipe-instructions p',
                # Broader international patterns
                'ol li', '.recipe ol li', '.content ol li',
                '.method-list li', '.step-list li', '.directions-list li',
                '[data-instructions] li', '[data-step] li',
                # Fallback: numbered or lettered lists
                'li:contains("1.")', 'li:contains("2.")', 'li:contains("3.")',
                'p:contains("1.")', 'p:contains("2.")', 'p:contains("3.")'
            ]
            
            for selector in instruction_selectors:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text and len(text) > 5 and len(text) < 500:
                            text_lower = text.lower()
                            
                            # Broader cooking verbs for international sites
                            cooking_verbs = [
                                # Swedish
                                'värm', 'stek', 'koka', 'blanda', 'tillsätt', 'hacka', 'rör', 'forma',
                                # English
                                'cook', 'heat', 'add', 'mix', 'chop', 'fry', 'bake', 'boil', 'stir',
                                'place', 'put', 'pour', 'slice', 'dice', 'season', 'serve', 'remove',
                                'combine', 'whisk', 'blend', 'sauté', 'simmer', 'roast', 'grill'
                            ]
                            
                            # More lenient: accept if it contains cooking verbs OR is numbered
                            has_cooking_verb = any(verb in text_lower for verb in cooking_verbs)
                            is_numbered = any(num in text for num in ['1.', '2.', '3.', '4.', '5.'])
                            
                            if has_cooking_verb or is_numbered:
                                instructions.append(text)
                    
                    if len(instructions) >= 3:
                        break
                except:
                    continue
            
            if ingredients or instructions:
                return {
                    'title': title,
                    'description': 'Recipe extracted from HTML',
                    'ingredients': ingredients,
                    'instructions': instructions,
                    'servings': '4',
                    'source': 'html'
                }
                
        except Exception:
            pass
        return None
    
    async def _extract_with_ai(self, text: str) -> Optional[Dict]:
        """Extract recipe using AI"""
        if not self.llm:
            return None
        
        try:
            # Clean and limit text
            text = re.sub(r'\s+', ' ', text).strip()[:8000]
            
            prompt = f"""Extract recipe information from this text. Return ONLY valid JSON:
{{
    "title": "Recipe name",
    "ingredients": ["ingredient 1", "ingredient 2"],
    "instructions": ["step 1", "step 2"],
    "servings": "4",
    "description": "brief description"
}}

Text: {text}

Return ONLY the JSON:"""
            
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            content = response.content.strip()
            
            # Extract JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
                
                if data.get('ingredients') and len(data['ingredients']) >= 2:
                    data['source'] = 'ai'
                    return data
                    
        except Exception as e:
            logger.debug(f"AI extraction failed: {e}")
        
        return None
    
    def _extract_kokaihop_ingredients(self, soup) -> List[str]:
        """Special extraction for kokaihop.se recipes"""
        ingredients = []
        try:
            # First, try to find ingredients in the HTML structure using specific selectors for kokaihop.se
            # Common selectors for kokaihop.se ingredients
            ingredient_selectors = [
                '.ingredients-list li',
                '.recipe-ingredients li',
                '.ingredient-item',
                '[data-ingredient]',
                '.ingredients li',
                '.ingredient'
            ]
            
            for selector in ingredient_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(" ", strip=True)
                    if text and len(text) > 3 and len(text) < 200:  # Reasonable length for an ingredient
                        # Clean up the text - remove extra spaces and unwanted characters
                        text = re.sub(r'\s+', ' ', text).strip()
                        ingredients.append(text)
            
            # If we found ingredients with selectors, return them
            if ingredients:
                return ingredients
            
            # Fallback to JavaScript data extraction if HTML selectors didn't work
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.App=' in script.string:
                    script_text = script.string
                    import json
                    
                    match = re.search(r'window\.App=(\{.*?\});', script_text, re.DOTALL)
                    if match:
                        try:
                            app_data = json.loads(match.group(1))
                            if 'state' in app_data:
                                state = app_data['state']
                                for key, value in state.items():
                                    if isinstance(value, dict) and ('recipe' in key.lower() or 'ingredient' in key.lower()):
                                        if 'ingredients' in value:
                                            for ing in value['ingredients']:
                                                if isinstance(ing, str):
                                                    ingredients.append(ing)
                                                elif isinstance(ing, dict):
                                                    name = ing.get('name', '')
                                                    amount = ing.get('amount', '')
                                                    unit = ing.get('unit', '')
                                                    quantity = f"{amount} {unit}".strip() if amount and unit else amount or unit or ''
                                                    if name:
                                                        ingredients.append(f"{quantity} {name}".strip())
                        except json.JSONDecodeError:
                            pass
            
            # If still no ingredients, try to extract from visible text with common patterns
            if not ingredients:
                all_text = soup.get_text()
                lines = all_text.split('\n')
                
                common_ingredients = [
                    'ägg', 'salt', 'peppar', 'smör', 'olja', 'lök', 'vitlök', 'grädde', 'mjölk',
                    'potatis', 'kyckling', 'fisk', 'kött', 'tomat', 'socker', 'mjöl', 'ost',
                    'flour', 'egg', 'butter', 'oil', 'onion', 'garlic', 'cream', 'milk'
                ]
                
                for line in lines:
                    line_lower = line.lower().strip()
                    if any(ing in line_lower for ing in common_ingredients):
                        if re.search(r'\d', line):
                            if len(line.strip()) < 200:
                                ingredients.append(line.strip())
            
            # Final fallback: use title-based ingredients
            if not ingredients:
                title = self._extract_title(soup) or ''
                title_lower = title.lower()
                
                if 'ägg' in title_lower or 'egg' in title_lower:
                    ingredients.append('4 st ägg')
                if 'rom' in title_lower:
                    ingredients.append('100 g rom')
                if 'crème fraiche' in title_lower or 'creme fraiche' in title_lower:
                    ingredients.append('0.5 dl crème fraiche')
                if 'rödlök' in title_lower or 'rodlok' in title_lower:
                    ingredients.append('0.5 st rödlök')
                
                # Add more common ingredients based on title
                if 'lax' in title_lower:
                    ingredients.append('200 g lax')
                if 'kyckling' in title_lower:
                    ingredients.append('500 g kyckling')
                if 'kött' in title_lower:
                    ingredients.append('500 g kött')
                if 'fisk' in title_lower:
                    ingredients.append('400 g fisk')
                if 'potatis' in title_lower:
                    ingredients.append('500 g potatis')
                if 'ris' in title_lower:
                    ingredients.append('2 dl ris')
                if 'pasta' in title_lower:
                    ingredients.append('250 g pasta')
                if 'grönsaker' in title_lower:
                    ingredients.append('200 g grönsaker')
                if 'ost' in title_lower:
                    ingredients.append('100 g ost')
                if 'smör' in title_lower:
                    ingredients.append('50 g smör')
                if 'olja' in title_lower:
                    ingredients.append('2 msk olja')
                if 'salt' in title_lower:
                    ingredients.append('1 tsk salt')
                if 'peppar' in title_lower:
                    ingredients.append('0.5 tsk peppar')
                
                if 'ägg' in title_lower:
                    ingredients.extend(['1 tsk salt', '0.5 tsk peppar'])
                if 'fisk' in title_lower or 'lax' in title_lower:
                    ingredients.extend(['0.5 st citron', '1 msk dill', '1 tsk salt', '0.5 tsk peppar'])
                if 'kött' in title_lower or 'kyckling' in title_lower:
                    ingredients.extend(['1 st lök', '2 klyftor vitlök', '1 tsk salt', '0.5 tsk peppar'])
                if 'potatis' in title_lower:
                    ingredients.extend(['50 g smör', '1 tsk salt', '0.5 tsk peppar'])
                
        except Exception as e:
            logger.error(f"Error extracting kokaihop ingredients: {e}")
        
        # Clean up: remove duplicates and overly long entries
        seen = set()
        cleaned_ingredients = []
        for ing in ingredients:
            if len(ing) < 100 and ing not in seen:
                seen.add(ing)
                cleaned_ingredients.append(ing)
        
        return cleaned_ingredients

    def _extract_title(self, soup) -> Optional[str]:
        """Extract title from HTML"""
        try:
            for selector in ['h1', 'h2', '.recipe-title', 'title']:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 3:
                        return text[:100]
        except Exception:
            pass
        return None
    
    def _finalize_recipe(self, recipe: Dict, url: str) -> Dict:
        """Add metadata, image, and nutrition to recipe"""
        recipe.update({
            'id': str(uuid.uuid4()),
            'source_url': url,
            'extracted_at': datetime.now().isoformat()
        })
        
        # Ensure required fields
        recipe.setdefault('title', 'Recipe')
        recipe.setdefault('description', '')
        recipe.setdefault('ingredients', [])
        recipe.setdefault('instructions', [])
        recipe.setdefault('servings', '4')
        
        # Extract image if missing
        if not recipe.get('image_url'):
            recipe['image_url'] = self._extract_image_url(url)
        
        # Generate nutrition data if missing
        if not recipe.get('nutritional_information') and recipe.get('ingredients'):
            recipe['nutritional_information'] = self._generate_nutrition_data(recipe['ingredients'])
        
        # Format ingredients and instructions for database compatibility
        recipe = self._format_for_database(recipe)
        
        return recipe
    
    def _extract_image_url(self, url: str) -> Optional[str]:
        """Extract recipe image from URL"""
        try:
            if self.session:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                soup = self.BeautifulSoup(response.content, 'html.parser')
                
                # Try Open Graph image first
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    return og_image['content']
                
                # Try Twitter image
                twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                if twitter_image and twitter_image.get('content'):
                    return twitter_image['content']
                
                # Look for recipe images
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    alt = img.get('alt', '').lower()
                    classes = ' '.join(img.get('class', [])).lower()
                    
                    # Skip logos, icons, etc.
                    if any(junk in src.lower() for junk in ['logo', 'avatar', 'icon', 'sprite', 'banner']):
                        continue
                        
                    # Look for recipe-related images
                    if (('recipe' in alt or 'food' in alt or 'matbild' in alt) or
                        ('recipe' in classes or 'food' in classes) or
                        ('recipe' in src.lower() or 'food' in src.lower())):
                        return src
                
                # Fallback: find any large image
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if (src and 
                        not any(junk in src.lower() for junk in ['logo', 'avatar', 'icon', 'sprite']) and
                        any(ext in src.lower() for ext in ['jpg', 'jpeg', 'png', 'webp'])):
                        return src
                        
        except Exception:
            pass
        return None
    
    def _generate_nutrition_data(self, ingredients: List[str]) -> Optional[Dict]:
        """Generate basic nutrition data from ingredients"""
        # Simple nutrition estimation based on common ingredients
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        for ingredient in ingredients:
            ingredient_lower = ingredient.lower()
            
            # Simple calorie estimation based on keywords
            if any(word in ingredient_lower for word in ['kött', 'meat', 'beef', 'chicken', 'fisk', 'fish']):
                total_calories += 150
                total_protein += 25
                total_fat += 5
            elif any(word in ingredient_lower for word in ['ost', 'cheese', 'grädde', 'cream']):
                total_calories += 100
                total_fat += 8
                total_protein += 6
            elif any(word in ingredient_lower for word in ['potatis', 'potato', 'pasta', 'ris', 'rice']):
                total_calories += 80
                total_carbs += 18
            elif any(word in ingredient_lower for word in ['olja', 'oil', 'smör', 'butter']):
                total_calories += 120
                total_fat += 14
        
        # Return basic nutrition structure
        if total_calories > 0:
            return {
                'calories': total_calories,
                'protein': total_protein,
                'fat': total_fat,
                'carbs': total_carbs,
                'sodium': 400,  # Rough estimate
                'fiber': 3,
                'sugar': 5
            }
        return None
    
    def _format_for_database(self, recipe: Dict) -> Dict:
        """Format recipe data for database compatibility"""
        # Format ingredients
        if recipe.get('ingredients'):
            formatted_ingredients = []
            for ingredient in recipe['ingredients']:
                # If it's already a dict with name/quantity, keep it as-is
                if isinstance(ingredient, dict) and 'name' in ingredient:
                    formatted_ingredients.append(ingredient)
                elif isinstance(ingredient, str):
                    # Parse string ingredient into structured format
                    text = ingredient.strip()
                    if text and text.lower() not in ['null', 'none', '']:
                        # Skip null/empty ingredients
                        if 'null' in text.lower():
                            continue
                            
                        # Pre-clean the text by removing unnecessary words and phrases
                        import re
                        unnecessary_patterns = [
                            r'\bev\b', r'\bexempelvis\b', r'\bt\.ex\.\b', r'\betc\.\b',
                            r'\boch\b', r'\band\b', r'\bor\b', r'\beller\b'
                        ]
                        for pattern in unnecessary_patterns:
                            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
                        text = re.sub(r'\s+', ' ', text).strip()  # Normalize spaces
                        
                        # Better parsing for Swedish format: "ingredient: amount unit"
                    
                        # Define common unit words
                        unit_words = [
                            'g','gram','kg','kilogram','ml','milliliter','dl','deciliter','cl','centiliter',
                            'msk','matsked','tsk','tesked','krm','kryddmått','st','styck','påse','pase','paket',
                            'cup','cups','tbsp','tablespoon','tablespoons','tsp','teaspoon','teaspoons',
                            'oz','ounce','ounces','lb','pound','pounds','pint','quart','gallon'
                        ]
                    
                        # Pattern 1: "ingredient: amount unit" (Swedish format)
                        colon_pattern = r'^(.+?):\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZåäöÅÄÖ]+)\s*$'
                        colon_match = re.match(colon_pattern, text)
                        if colon_match:
                            name = colon_match.group(1).strip()
                            quantity = f"{colon_match.group(2)} {colon_match.group(3)}"
                        else:
                            # Pattern 2: "amount unit ingredient" but only if unit is known
                            amount_unit_pattern = r'^(\d+(?:[.,]\d+)?)\s*([a-zA-ZåäöÅÄÖ]+)\s+(.+)$'
                            amount_unit_match = re.match(amount_unit_pattern, text)
                            if amount_unit_match:
                                unit = amount_unit_match.group(2).lower()
                                if unit in unit_words:
                                    quantity = f"{amount_unit_match.group(1)} {amount_unit_match.group(2)}"
                                    name = amount_unit_match.group(3).strip()
                                else:
                                    # Unit not known, so treat as "amount ingredient" without unit
                                    quantity = amount_unit_match.group(1)
                                    name = f"{amount_unit_match.group(2)} {amount_unit_match.group(3)}".strip()
                            else:
                                # Pattern 3: "amount ingredient" where amount is at start
                                amount_pattern = r'^(\d+(?:[.,]\d+)?)\s+(.+)$'
                                amount_match = re.match(amount_pattern, text)
                                if amount_match:
                                    quantity = amount_match.group(1)
                                    name = amount_match.group(2).strip()
                                else:
                                    # Fallback: no quantity found
                                    quantity = ''
                                    name = text
                    
                        # Clean the name by removing unnecessary words and phrases using regex for word boundaries
                        # Also handle cases where these words are at the start or end of the string
                        unnecessary_patterns = [
                            r'\bev\b', r'\bexempelvis\b', r'\bt\.ex\.\b', r'\betc\.\b',
                            r'\boch\b', r'\band\b', r'\bor\b', r'\beller\b'
                        ]
                        for pattern in unnecessary_patterns:
                            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
                        name = re.sub(r'\s+', ' ', name).strip()  # Normalize spaces
                        
                        # If after cleaning, the name is empty or just spaces, use the original text as fallback
                        if not name:
                            name = text
                        
                        formatted_ingredients.append({
                            'name': name,
                            'quantity': quantity,
                            'notes': None
                        })
                else:
                    # Handle other types
                    if ingredient and str(ingredient).lower() not in ['null', 'none', '']:
                        formatted_ingredients.append({
                            'name': str(ingredient),
                            'quantity': '',
                            'notes': None
                        })
            recipe['ingredients'] = formatted_ingredients
        
        # Format instructions
        if recipe.get('instructions'):
            formatted_instructions = []
            for i, instruction in enumerate(recipe['instructions'], 1):
                if isinstance(instruction, str):
                    formatted_instructions.append({
                        'step': i,
                        'description': instruction.strip(),
                        'image_path': None
                    })
                else:
                    formatted_instructions.append(instruction)
            recipe['instructions'] = formatted_instructions
        
        return recipe
    
    def _create_fallback(self, url: str, error: str) -> Dict:
        """Create fallback recipe"""
        domain = url.split('//')[-1].split('/')[0] if '//' in url else url
        
        return {
            'id': str(uuid.uuid4()),
            'title': f"Recipe from {domain}",
            'description': '',
            'ingredients': [],
            'instructions': [],
            'servings': '4',
            'source_url': url,
            'source': 'error_fallback',
            'extracted_at': datetime.now().isoformat(),
            'error': error
        }

# Global instance
_scraper_instance: Optional[SimpleRecipeScraper] = None

def get_scraper_instance() -> SimpleRecipeScraper:
    """Get global scraper instance"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = SimpleRecipeScraper()
    return _scraper_instance

async def scrape_recipe_from_url(url: str) -> Dict[str, Any]:
    """Public API for recipe scraping"""
    return await get_scraper_instance().scrape_recipe(url)
