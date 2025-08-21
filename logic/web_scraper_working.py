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

class SimpleRecipeScraper:
    """Simple, reliable recipe scraper"""
    
    def __init__(self):
        self.requests = get_requests()
        self.BeautifulSoup = get_beautifulsoup()
        self.ChatDeepSeek = get_deepseek()
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
    
    async def scrape_recipe(self, url: str) -> Dict[str, Any]:
        """Scrape recipe from URL - always returns something useful"""
        try:
            # Get HTML
            if not self.session:
                raise Exception("Requests not available")
                
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = await asyncio.to_thread(
                self.session.get, url, headers=headers, timeout=15, allow_redirects=True
            )
            response.raise_for_status()
            
            # Parse HTML
            if not self.BeautifulSoup:
                raise Exception("BeautifulSoup not available")
                
            soup = self.BeautifulSoup(response.text, 'html.parser')
            
            # Try structured data first
            recipe = self._extract_json_ld(soup) or self._extract_microdata(soup)
            
            if recipe and recipe.get('ingredients') and len(recipe['ingredients']) >= 2:
                logger.info(f"Structured extraction successful: {recipe.get('title')}")
                return self._finalize_recipe(recipe, url)
            
            # Try basic HTML extraction  
            html_recipe = self._extract_from_html(soup)
            if html_recipe and (html_recipe.get('ingredients') or html_recipe.get('instructions')):
                logger.info(f"HTML extraction successful: {html_recipe.get('title')}")
                return self._finalize_recipe(html_recipe, url)
            
            # Skip JavaScript extraction for now - use AI instead
            
            # Try AI extraction
            if self.llm:
                recipe = await self._extract_with_ai(soup.get_text())
                if recipe and recipe.get('ingredients'):
                    logger.info(f"AI extraction successful: {recipe.get('title')}")
                    return self._finalize_recipe(recipe, url)
            
            # Fallback with title
            title = self._extract_title(soup) or f"Recipe from {url.split('//')[-1].split('/')[0]}"
            
            return {
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
            
        except Exception as e:
            logger.error(f"Scraping failed for {url}: {e}")
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
