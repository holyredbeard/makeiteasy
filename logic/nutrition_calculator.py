import re
import logging
import httpx
import json
import asyncio
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
import os
from logic.translator import translate_ingredient_name, GLOSSARY
from core.database import db
from logic.rules_loader import load_rules, load_portion_rules
from logic.portion_resolver import resolve_grams

logger = logging.getLogger(__name__)

@dataclass
class ParsedIngredient:
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    grams: Optional[float]
    optional: bool = False
    negligible: bool = False
    raw: Optional[str] = None

@dataclass
class FdcMatch:
    fdc_id: int
    description: str
    match_score: float
    data_type: str

@dataclass
class NutrientData:
    calories: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    saturated_fat: Optional[float] = None
    carbs: Optional[float] = None
    sugar: Optional[float] = None
    fiber: Optional[float] = None
    sodium: Optional[float] = None
    cholesterol: Optional[float] = None

@dataclass
class IngredientExplanation:
    parsed: Dict[str, Any]
    fdc_id: Optional[int]
    data_type: Optional[str]
    portion_source: str
    rules_applied: List[str]
    name_en: Optional[str] = None
    translation_source: Optional[str] = None
    translation_confidence: Optional[float] = None
    fdc_match_score: Optional[float] = None

class NutritionCalculator:
    def __init__(self):
        self.base_url = "https://api.nal.usda.gov/fdc/v1"
        self.fdc_api_key = os.getenv("FDC_API_KEY", "DEMO_KEY")
        
        # Density table for volume to weight conversion (g/ml)
        self.densities = {
            'water': 1.0,
            'vatten': 1.0,
            'milk': 1.03,
            'mjölk': 1.03,
            'soy milk': 1.03,
            'sojamjölk': 1.03,
            'cream': 0.98,
            'grädde': 0.98,
            'oil': 0.92,
            'olja': 0.92,
            'rice': 0.85,
            'ris': 0.85,
            'flour': 0.53,
            'vetemjöl': 0.53,
            'sugar': 0.85,
            'socker': 0.85,
            'honey': 1.42,
            'honung': 1.42,
            'tomatoes': 1.05,
            'tomater': 1.05,
            'crushed tomatoes': 1.05,
            'krossade tomater': 1.05,
        }
        
        # Unit conversion factors
        self.unit_factors = {
            # Weight
            'g': 1.0, 'gram': 1.0, 'grams': 1.0, 'gramm': 1.0,
            'kg': 1000.0, 'kilo': 1000.0,
            # Volume
            'ml': 1.0, 'milliliter': 1.0, 'milliliters': 1.0,
            'l': 1000.0, 'liter': 1000.0, 'liters': 1000.0,
            'dl': 100.0, 'deciliter': 100.0, 'deciliters': 100.0,
            # Household measures
            'tsk': 5.0, 'teaspoon': 5.0, 'teaspoons': 5.0, 'tsp': 5.0,
            'msk': 15.0, 'tablespoon': 15.0, 'tablespoons': 15.0, 'tbsp': 15.0,
            'krm': 1.0, 'kryddmått': 1.0,
            # Pieces
            'st': 1.0, 'stycken': 1.0, 'piece': 1.0, 'pieces': 1.0,
            'burk': 1.0, 'burkar': 1.0, 'can': 1.0, 'cans': 1.0,
            'paket': 1.0, 'package': 1.0, 'packages': 1.0,
            'klyfta': 1.0, 'klyftor': 1.0, 'clove': 1.0, 'cloves': 1.0,
            'cup': 240.0, 'cups': 240.0,
        }
        
        # Swedish to English ingredient mapping
        self.swedish_to_english = {
            'rökt tofu': 'smoked tofu',
            'veganska korvar': 'vegan sausages',
            'vegansk ost': 'vegan cheese',
            'sojamjölk': 'soy milk',
            'linfrö': 'flaxseed',
            'linfröägg': 'flax egg',
            'gammaldags idealmakaroner': 'traditional macaroni',
            'makaroner': 'macaroni',
            'makaronipudding': 'macaroni pudding',
            'långpanna': 'baking pan',
            'svartpeppar': 'black pepper',
            'salt': 'salt',
            'vatten': 'water',
            'peppar': 'pepper',
            'korvar': 'sausages',
            'ost': 'cheese',
            'mjölk': 'milk',
            'linfröägg': 'flax egg',
            'gammaldags': 'traditional',
            'idealmakaroner': 'macaroni',
            'svartpeppar': 'black pepper',
            # Additional mappings for better coverage
            'gammaldags idealmakaroner': 'macaroni pasta',
            'idealmakaroner': 'macaroni pasta',
            'makaroner': 'macaroni pasta',
            'pasta': 'pasta',
            'spaghetti': 'spaghetti',
            'penne': 'penne pasta',
            'farfalle': 'bow tie pasta',
            'sojamjölk': 'soy milk',
            'soja mjölk': 'soy milk',
            'veganska korvar': 'vegan sausage',
            'vegansk korv': 'vegan sausage',
            'vegansk ost': 'vegan cheese',
            'vegansk feta': 'vegan feta cheese',
            'linfröägg': 'flax egg',
            'linfrö ägg': 'flax egg',
            'linfrö': 'flaxseed',
            'linfrön': 'flaxseeds',
            'svartpeppar': 'black pepper',
            'svart peppar': 'black pepper',
            'vitpeppar': 'white pepper',
            'vit peppar': 'white pepper',
            'peppar': 'black pepper',
            'salt': 'salt',
            'havssalt': 'sea salt',
            'havs salt': 'sea salt',
            'vatten': 'water',
            'kranvatten': 'tap water',
            'kran vatten': 'tap water',
            # Specific problematic ingredients from recipe 49
            'gammaldags idealmakaroner': 'macaroni pasta',
            'idealmakaroner': 'macaroni pasta',
            'veganska korvar': 'vegan sausage',
            'vegansk korv': 'vegan sausage',
            'sojamjölk': 'soy milk',
            'linfröägg (5 msk linfrö + 15 msk vatten)': 'flaxseed',
            'linfröägg': 'flaxseed',
            'peppar': 'black pepper',
            'svartpeppar': 'black pepper',
        }
        
        # Vegan/plant-based keywords for cholesterol rule
        self.vegan_keywords = [
            'vegansk', 'vegan', 'tofu', 'soja', 'soy', 'växtbaserad', 'plant-based',
            'vegetabilisk', 'vegetable', 'olja', 'oil', 'nötter', 'nuts', 'frön', 'seeds',
            'grönsaker', 'vegetables', 'frukt', 'fruit', 'linfrö', 'flaxseed'
        ]

    def _extract_quantity_unit_name(self, text: str) -> Tuple[Optional[float], Optional[str], str, bool]:
        """Extract quantity, unit, name, and optional flag from ingredient text"""
        text = text.strip()
        
        # Check for optional ingredients
        optional = text.lower().startswith('valfritt')
        if optional:
            text = text[8:].strip()  # Remove "valfritt"
        
        # Handle Unicode fractions
        text = self._normalize_fractions(text)
        
        # Patterns for different formats
        patterns = [
            # Parenthesized weight: "1 burk (400 g) krossade tomater"
            r'^(\d+(?:[.,]\d+)?)\s*(\w+)\s*\((\d+(?:[.,]\d+)?)\s*(g|gram|kg)\s*\)\s+(.+)$',
            # Standard format: "300 gram rökt tofu"
            r'^(\d+(?:[.,]\d+)?)\s*(g|gram|grams|gramm|kg|kilo|ml|milliliter|milliliters|l|liter|liters|dl|deciliter|deciliters|tsk|teaspoon|teaspoons|tsp|msk|tablespoon|tablespoons|tbsp|krm|kryddmått|st|stycken|burk|burkar|can|cans|paket|package|packages|klyfta|klyftor|clove|cloves|cup|cups|piece|pieces)\s+(.+)$',
            # Fraction format: "1/2 tsk salt"
            r'^(\d+/\d+)\s*(g|gram|grams|gramm|kg|kilo|ml|milliliter|milliliters|l|liter|liters|dl|deciliter|deciliters|tsk|teaspoon|teaspoons|tsp|msk|tablespoon|tablespoons|tbsp|krm|kryddmått|st|stycken|burk|burkar|can|cans|paket|package|packages|klyfta|klyftor|clove|cloves|cup|cups|piece|pieces)\s+(.+)$',
            # Generic number + text: "300 rökt tofu"
            r'^(\d+(?:[.,]\d+)?)\s+(.+)$',
            # Fraction + text: "1/2 salt"
            r'^(\d+/\d+)\s+(.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 5:  # Parenthesized weight
                    quantity_str = groups[0]
                    unit = groups[1]
                    weight_str = groups[2]
                    weight_unit = groups[3]
                    name = groups[4]
                    
                    # Convert quantity and weight
                    quantity = self._parse_number(quantity_str)
                    weight = self._parse_number(weight_str)
                    
                    # Use parenthesized weight for grams calculation
                    grams = self._convert_to_grams(weight, weight_unit)
                    return quantity, unit, name, optional
                    
                elif len(groups) == 3:  # Standard format
                    quantity_str = groups[0]
                    unit = groups[1]
                    name = groups[2]
                    
                    quantity = self._parse_number(quantity_str)
                    return quantity, unit, name, optional
                    
                elif len(groups) == 2:  # Generic format
                    quantity_str = groups[0]
                    name = groups[1]
                    
                    quantity = self._parse_number(quantity_str)
                    return quantity, None, name, optional
        
        # No quantity found, return the whole text as name
        return None, None, text, optional

    def _normalize_fractions(self, text: str) -> str:
        """Convert Unicode fractions to standard format"""
        fraction_map = {
            '½': '1/2', '¼': '1/4', '¾': '3/4', '⅓': '1/3', '⅔': '2/3',
            '⅕': '1/5', '⅖': '2/5', '⅗': '3/5', '⅘': '4/5',
            '⅙': '1/6', '⅚': '5/6', '⅐': '1/7', '⅛': '1/8', '⅜': '3/8', '⅝': '5/8', '⅞': '7/8'
        }
        
        for unicode_frac, standard_frac in fraction_map.items():
            text = text.replace(unicode_frac, standard_frac)
        
        # Handle mixed numbers like "1½" -> "1 1/2"
        text = re.sub(r'(\d+)(½|¼|¾)', r'\1 \2', text)
        
        return text

    def _parse_number(self, number_str: str) -> float:
        """Parse number with Swedish or English decimal separator"""
        # Handle fractions
        if '/' in number_str:
            num, denom = number_str.split('/')
            return float(num) / float(denom)
        
        # Handle Swedish decimal comma
        number_str = number_str.replace(',', '.')
        return float(number_str)

    def _convert_to_grams(self, quantity: float, unit: str) -> float:
        """Convert quantity and unit to grams"""
        if not unit:
            return quantity  # Assume grams if no unit
        
        unit_lower = unit.lower()
        
        if unit_lower in self.unit_factors:
            return quantity * self.unit_factors[unit_lower]
        
        # Default: assume grams
        return quantity

    def _estimate_density(self, ingredient_name: str) -> float:
        """Estimate density for volume to weight conversion"""
        name_lower = ingredient_name.lower()
        
        for keyword, density in self.densities.items():
            if keyword in name_lower:
                return density
        
        # Default density for unknown ingredients
        return 1.0

    def _is_vegan_ingredient(self, ingredient_name: str) -> bool:
        """Check if ingredient is vegan/plant-based for cholesterol rule"""
        name_lower = ingredient_name.lower()
        return any(keyword in name_lower for keyword in self.vegan_keywords)

    def _translate_to_english(self, ingredient_name: str) -> str:
        """Translate Swedish ingredient names to English for FDC search"""
        name_lower = ingredient_name.lower()
        
        # Handle complex descriptions like "linfröägg (5 msk linfrö + 15 msk vatten)"
        # Extract the main ingredient name before parentheses
        if '(' in ingredient_name:
            main_part = ingredient_name.split('(')[0].strip()
            name_lower = main_part.lower()
        
        # Try exact matches first
        for swedish, english in self.swedish_to_english.items():
            if name_lower == swedish.lower():
                if '(' in ingredient_name:
                    return main_part.replace(swedish, english)
                else:
                    return ingredient_name.replace(swedish, english)
        
        # Try partial matches
        for swedish, english in self.swedish_to_english.items():
            if swedish.lower() in name_lower:
                if '(' in ingredient_name:
                    return main_part.replace(swedish, english)
                else:
                    return ingredient_name.replace(swedish, english)
        
        return ingredient_name

    def parse_ingredients(self, ingredients: List[Dict[str, str]]) -> List[ParsedIngredient]:
        """Parse raw ingredient strings into structured data"""
        parsed = []
        
        for ingredient in ingredients:
            raw = ingredient['raw']
            # Special split for flax egg: two ingredients (flaxseed + water)
            if re.search(r"linfröägg", raw, re.I) and re.search(r"\(.*msk\s*linfrö\s*\+\s*.*msk\s*vatten.*\)", raw, re.I):
                try:
                    m = re.search(r"(\d+[\.,]?\d*)\s*msk\s*linfrö\s*\+\s*(\d+[\.,]?\d*)\s*msk\s*vatten", raw, re.I)
                    flax_tbsp = float(m.group(1).replace(',', '.'))
                    water_tbsp = float(m.group(2).replace(',', '.'))
                    flax_grams = flax_tbsp * 15.0 * 0.52  # 0.52 g/ml
                    water_grams = water_tbsp * 15.0 * 1.0
                    parsed.append(ParsedIngredient(name='linfrö', quantity=flax_tbsp, unit='msk', grams=flax_grams, optional=False, negligible=flax_grams < 1.0, raw=f"{raw} [split: linfrö]"))
                    parsed.append(ParsedIngredient(name='vatten', quantity=water_tbsp, unit='msk', grams=water_grams, optional=False, negligible=False, raw=f"{raw} [split: vatten]"))
                    # mark original as explained composite (no direct add)
                    continue
                except Exception:
                    pass
            quantity, unit, name, optional = self._extract_quantity_unit_name(raw)
            
            # Calculate grams using portion rules + FDC portions + density
            grams = None
            try:
                rules = load_portion_rules()
                fdc_json = None
                # If we already identified an FDC match later, we will recompute; here first pass without
                resolved = resolve_grams(quantity, unit, name, fdc_json, rules)
                grams = float(resolved.get('grams')) if resolved else None
            except Exception:
                # Fallback to legacy heuristic
                if quantity and unit:
                    if unit.lower() in ['g', 'gram', 'grams', 'gramm', 'kg', 'kilo']:
                        grams = self._convert_to_grams(quantity, unit)
                    else:
                        volume_ml = self._convert_to_grams(quantity, unit)
                        density = self._estimate_density(name)
                        grams = volume_ml * density
            
            # Check if negligible (small amounts of spices)
            negligible = grams is not None and grams < 1.0
            
            parsed_ingredient = ParsedIngredient(
                name=name.strip(),
                quantity=quantity,
                unit=unit,
                grams=grams,
                optional=optional,
                negligible=negligible,
                raw=raw
            )
            parsed.append(parsed_ingredient)
        
        return parsed

    def normalize_to_grams(self, ingredient: ParsedIngredient) -> float:
        """Convert ingredient quantity to grams"""
        if ingredient.grams is not None:
            return ingredient.grams
        
        if ingredient.quantity:
            # Assume 100g if no unit specified
            return 100.0
        
        # Default fallback
        return 100.0

    async def find_fdc_match(self, ingredient_name: str) -> Optional[FdcMatch]:
        """Find best FDC match for ingredient name"""
        try:
            # Normalize to main name before parentheses
            name_main = ingredient_name.split('(')[0].strip()
            # Detect language: allow Swedish even without å/ä/ö if it matches known Swedish aliases
            lowered = name_main.lower()
            has_swedish_chars = bool(re.search(r"[åäöÅÄÖ]", ingredient_name))
            matches_sv_alias = any(alias in lowered for alias in GLOSSARY.keys())
            lang = 'sv' if (has_swedish_chars or matches_sv_alias) else 'en'
            t = translate_ingredient_name(name_main, lang, parsed_name=name_main)
            english_name = t.get('name_en') or name_main
            confidence = t.get('confidence', 0.0)
            source = t.get('source', 'none')
            t_class = t.get('class', 'NOMATCH')
            logger.info(f"Translate '{name_main}' -> '{english_name}' via {source} (conf={confidence}, class={t_class})")
            # Fallback: if looks untranslated and we assumed EN, try Swedish path once
            if (source == 'fallback' and lang == 'en' and (not re.search(r"[a-z]", english_name.lower()) or english_name.strip().lower() == lowered)):
                t = translate_ingredient_name(name_main, 'sv', parsed_name=name_main)
                english_name = t.get('name_en') or name_main
                confidence = t.get('confidence', 0.0)
                source = t.get('source', 'none')
                t_class = t.get('class', 'NOMATCH')
                logger.info(f"Retry translate as 'sv': '{name_main}' -> '{english_name}' via {source} (conf={confidence}, class={t_class})")
            
            # Search FDC API with retry logic
            async def _search(query: str, max_retries: int = 2):
                for attempt in range(max_retries + 1):
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"{self.base_url}/foods/search",
                                params={
                                    'api_key': self.fdc_api_key,
                                    'query': query,
                                    'dataType': ['Foundation', 'SR Legacy', 'Survey (FNDDS)', 'Branded'],
                                    'pageSize': 10
                                },
                                timeout=10.0
                            )
                            if response.status_code == 429:
                                if attempt < max_retries:
                                    await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
                                    continue
                                else:
                                    logger.warning(f"FDC API rate limited after {max_retries} retries for query: {query}")
                                    return None
                            response.raise_for_status()
                            return response.json()
                    except httpx.TimeoutException:
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        else:
                            logger.warning(f"FDC API timeout after {max_retries} retries for query: {query}")
                            return None
                    except Exception as e:
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        else:
                            logger.warning(f"FDC API error after {max_retries} retries for query: {query}: {e}")
                            return None
                return None

            # 1) Try canonical table first
            try:
                with db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT id, name_en, fdc_id, synonyms FROM canonical_ingredients WHERE LOWER(name_en) = LOWER(?) LIMIT 1", (english_name,))
                    row = c.fetchone()
                    if row:
                        _, canon_name, canon_fdc, synonyms = row
                        if canon_fdc:
                            return FdcMatch(fdc_id=int(canon_fdc), description=canon_name, match_score=1.0, data_type="Canonical")
            except Exception as e:
                logger.warning(f"Canonical lookup failed: {e}")

            # 2) Search FDC with full name
            # Skip FDC search for known non-nutritive items
            if english_name.strip().lower() in ("water", "tap water"):
                return None
            data = await _search(english_name)
            # If primary search has no foods, try simplified fallback query
            if not data.get('foods'):
                simple_map = {
                    'light soy sauce': 'soy sauce',
                    'smoked tofu': 'tofu',
                    'vegan sausage': 'meatless sausage',
                    'meatless sausage': 'sausage',
                    'vegan cheese': 'cheese',
                    'black pepper': 'pepper',
                    'pepper': 'black pepper',
                }
                fallback_query = simple_map.get(english_name.lower())
                if not fallback_query:
                    fallback_query = re.sub(r"\b(light|smoked|vegan|traditional|old\s*style)\b", "", english_name, flags=re.I).strip()
                data = await _search(fallback_query)
                if not data.get('foods'):
                    return None

            # Score best match across whatever foods we have
            best_match = None
            best_score = 0.0
            for food in data.get('foods', []):
                description = food.get('description', '').lower()
                name_lower = english_name.lower()
                name_words = set(name_lower.split())
                desc_words = set(description.split())
                score = 0.0
                if name_words and desc_words:
                    overlap = len(name_words.intersection(desc_words))
                    total = len(name_words.union(desc_words))
                    score = overlap / total if total > 0 else 0.0
                if description.startswith(name_lower) or name_lower in description:
                    score += 0.3
                if score > best_score:
                    best_score = score
                    best_match = FdcMatch(
                        fdc_id=food['fdcId'],
                        description=food['description'],
                        match_score=score,
                        data_type=food.get('dataType', 'Unknown')
                    )

            if best_match and best_score >= 0.25:
                try:
                    with db.get_connection() as conn:
                        c = conn.cursor()
                        c.execute("SELECT id, fdc_id FROM canonical_ingredients WHERE LOWER(name_en) = LOWER(?)", (english_name,))
                        row = c.fetchone()
                        if row and not row[1]:
                            c.execute("UPDATE canonical_ingredients SET fdc_id = ? WHERE id = ?", (str(best_match.fdc_id), row[0]))
                            conn.commit()
                except Exception as e:
                    logger.warning(f"Persisting FDC id on canonical failed: {e}")
                try:
                    with db.get_connection() as conn:
                        c = conn.cursor()
                        c.execute("SELECT id FROM canonical_ingredients WHERE LOWER(name_en) = LOWER(?)", (english_name,))
                        canon = c.fetchone()
                        if canon:
                            c.execute(
                                "INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence) VALUES (?, 'sv', ?, 0.9)",
                                (ingredient_name.lower(), canon[0])
                            )
                            conn.commit()
                except Exception as e:
                    logger.warning(f"Persisting alias failed: {e}")
                return best_match
            return None
                
        except Exception as e:
            logger.error(f"Error searching FDC for {ingredient_name}: {e}")
            return None

    async def fetch_fdc_nutrients(self, fdc_id: int) -> Optional[NutrientData]:
        """Fetch nutrient data for FDC ID"""
        try:
            # Use DB cache first (14 days freshness)
            cached = db.get_fdc_food(int(fdc_id))
            data = None
            if cached and cached.get('json'):
                from datetime import datetime, timedelta
                try:
                    ts = cached.get('updated_at')
                    fresh = True
                    if ts:
                        dt = datetime.fromisoformat(ts) if isinstance(ts, str) else None
                        if dt and (datetime.now() - dt) > timedelta(days=14):
                            fresh = False
                    if fresh:
                        data = cached.get('json')
                except Exception:
                    pass
            if data is None:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/food/{fdc_id}",
                        params={'api_key': self.fdc_api_key},
                        timeout=10.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    # persist cache
                    try:
                        db.upsert_fdc_food(int(fdc_id), data)
                    except Exception:
                        pass
                
                nutrients = NutrientData()
                
                # Extract nutrients from foodNutrients
                for nutrient in data.get('foodNutrients', []):
                    nutrient_id = nutrient.get('nutrient', {}).get('id')
                    value = nutrient.get('amount', 0)
                    
                    # Map FDC nutrient IDs to our fields
                    if nutrient_id == 1008:  # Energy (kcal)
                        nutrients.calories = value
                    elif nutrient_id == 1003:  # Protein
                        nutrients.protein = value
                    elif nutrient_id == 1004:  # Total lipid (fat)
                        nutrients.fat = value
                    elif nutrient_id == 1258:  # Fatty acids, total saturated
                        nutrients.saturated_fat = value
                    elif nutrient_id == 1005:  # Carbohydrate, by difference
                        nutrients.carbs = value
                    elif nutrient_id == 2000:  # Sugars, total including NLEA
                        nutrients.sugar = value
                    elif nutrient_id == 1079:  # Fiber, total dietary
                        nutrients.fiber = value
                    elif nutrient_id == 1093:  # Sodium, Na
                        nutrients.sodium = value
                    elif nutrient_id == 1253:  # Cholesterol
                        nutrients.cholesterol = value
                
                return nutrients
                
        except Exception as e:
            logger.error(f"Error fetching FDC nutrients for {fdc_id}: {e}")
            return None

    async def fetch_fdc_foods_batch(self, ids: List[int]) -> Dict[int, dict]:
        """Batch fetch foods (best-effort): use cache, then POST /v1/foods for misses."""
        result: Dict[int, dict] = {}
        misses: List[int] = []
        # 1) Try cache
        for fid in ids:
            cached = db.get_fdc_food(int(fid))
            if cached and cached.get('json'):
                result[int(fid)] = cached['json']
            else:
                misses.append(int(fid))
        # 2) Batch fetch
        if misses:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/foods",
                        params={'api_key': self.fdc_api_key},
                        json={"fdcIds": misses},
                        timeout=15.0
                    )
                    response.raise_for_status()
                    arr = response.json() or []
                    for item in arr:
                        fid = int(item.get('fdcId'))
                        result[fid] = item
                        try:
                            db.upsert_fdc_food(fid, item)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Batch foods fetch failed: {e}")
        return result

    def _apply_special_rules(self, ingredient: ParsedIngredient, nutrients: NutrientData) -> List[str]:
        """Apply special rules and return list of applied rules"""
        rules_applied = []
        
        # Exclude water from nutrition (keep grams in explain only)
        if ingredient.name.lower() in ['water', 'tap water', 'vatten']:
            # zero-out nutrients explicitly for water
            nutrients.calories = nutrients.protein = nutrients.fat = nutrients.saturated_fat = 0.0
            nutrients.carbs = nutrients.sugar = nutrients.fiber = nutrients.sodium = nutrients.cholesterol = 0.0
            rules_applied.append("water_excluded")
            return rules_applied

        # Salt to sodium conversion (no FDC for salt)
        if ingredient.name.lower() in ['salt', 'havssalt', 'sea salt']:
            salt_g = 0.0
            if ingredient.quantity and ingredient.unit:
                unit = ingredient.unit.lower()
                if unit in ['g', 'gram', 'grams']:
                    salt_g = float(ingredient.quantity)
                elif unit in ['msk', 'tbsp', 'tsk', 'tsp']:
                    # density for salt ≈ 1.2 g/ml, msk=15ml, tsk=5ml
                    ml = ingredient.quantity * (15.0 if unit in ['msk','tbsp'] else 5.0)
                    salt_g = ml * 1.2
            # Convert to sodium
            nutrients.calories = nutrients.protein = nutrients.fat = nutrients.saturated_fat = 0.0
            nutrients.carbs = nutrients.sugar = nutrients.fiber = 0.0
            nutrients.cholesterol = 0.0
            sodium_total_mg = salt_g * 1000.0 / 2.5
            # store as per-100g value so multiplication by grams/100 yields correct total
            if ingredient.grams and ingredient.grams > 0:
                nutrients.sodium = sodium_total_mg / ingredient.grams * 100.0
            else:
                nutrients.sodium = sodium_total_mg
            rules_applied.append("salt_to_sodium")
        
        # Cholesterol rule for vegan ingredients
        if self._is_vegan_ingredient(ingredient.name):
            nutrients.cholesterol = 0.0
            rules_applied.append("cholesterol_zero")
        
        return rules_applied

    def compute_totals(self, ingredients_with_data: List[Tuple[ParsedIngredient, Optional[NutrientData], IngredientExplanation]], servings: int) -> Dict:
        """Compute total nutrition values with special handling"""
        total_grams = 0
        total_nutrients = {
            'calories': 0,
            'protein': 0,
            'fat': 0,
            'saturatedFat': 0,
            'carbs': 0,
            'sugar': 0,
            'fiber': 0,
            'sodium': 0,
            'cholesterol': 0
        }
        
        explanations = []
        debug_entries: List[Dict[str, Any]] = []
        implausible_items: List[str] = []
        
        for ingredient, nutrients, explanation in ingredients_with_data:
            logger.info(f"Processing {ingredient.name} ({ingredient.grams}g): nutrients={nutrients}")
            
            # Skip optional ingredients
            if ingredient.optional:
                explanation.rules_applied.append("optional_excluded")
                explanations.append(explanation)
                continue
            
            if ingredient.grams is not None:
                # ensure nutrients object exists so special rules can apply
                if nutrients is None:
                    nutrients = NutrientData()
                # Apply special rules
                rules = self._apply_special_rules(ingredient, nutrients)
                explanation.rules_applied.extend(rules)
                
                # Calculate nutrients based on grams
                factor = ingredient.grams / 100.0  # FDC data is per 100g
                logger.info(f"  Factor: {factor}")
                
                total_nutrients['calories'] += (nutrients.calories or 0) * factor
                total_nutrients['protein'] += (nutrients.protein or 0) * factor
                total_nutrients['fat'] += (nutrients.fat or 0) * factor
                total_nutrients['saturatedFat'] += (nutrients.saturated_fat or 0) * factor
                total_nutrients['carbs'] += (nutrients.carbs or 0) * factor
                total_nutrients['sugar'] += (nutrients.sugar or 0) * factor
                total_nutrients['fiber'] += (nutrients.fiber or 0) * factor
                total_nutrients['sodium'] += (nutrients.sodium or 0) * factor
                total_nutrients['cholesterol'] += (nutrients.cholesterol or 0) * factor
                
                total_grams += ingredient.grams

                # Build per-ingredient debug entry
                unit_used = ingredient.unit or ''
                calc_formula = ''
                try:
                    if unit_used.lower() in ['g', 'gram', 'grams', 'gramm', 'kg', 'kilo'] and ingredient.quantity is not None:
                        per_unit = self.unit_factors.get(unit_used.lower(), 1.0)
                        calc_formula = f"{ingredient.quantity} {unit_used} × {per_unit} g/{unit_used} = {round(ingredient.grams,2)} g"
                    elif unit_used and ingredient.quantity is not None:
                        ml = self.unit_factors.get(unit_used.lower(), 1.0)
                        dens = self._estimate_density(ingredient.name)
                        calc_formula = f"{ingredient.quantity} {unit_used} × {ml} ml/{unit_used} × {dens} g/ml = {round(ingredient.grams,2)} g"
                    else:
                        calc_formula = f"assumed default 100 g"
                except Exception:
                    calc_formula = "calculation unavailable"

                # Per-ingredient contributions
                contrib = {
                    'calories': round((nutrients.calories or 0) * factor, 3),
                    'protein': round((nutrients.protein or 0) * factor, 3),
                    'fat': round((nutrients.fat or 0) * factor, 3),
                    'saturatedFat': round((nutrients.saturated_fat or 0) * factor, 3),
                    'carbs': round((nutrients.carbs or 0) * factor, 3),
                    'sugar': round((nutrients.sugar or 0) * factor, 3),
                    'fiber': round((nutrients.fiber or 0) * factor, 3),
                    'sodium': round((nutrients.sodium or 0) * factor, 3),
                    'cholesterol': round((nutrients.cholesterol or 0) * factor, 3),
                    'salt': round(((nutrients.sodium or 0) * factor) * 2.5 / 1000.0, 3),
                }

                # Determine source hit
                source_hit = 'none'
                if 'salt_to_sodium' in explanation.rules_applied:
                    source_hit = 'rule:salt'
                elif 'water_excluded' in explanation.rules_applied:
                    source_hit = 'rule:water'
                elif explanation.fdc_id:
                    source_hit = 'FDC'
                elif explanation.translation_source == 'deepseek':
                    source_hit = 'deepseek'

                # Implausibility guards per ingredient
                flags = []
                if contrib['salt'] > 200:
                    flags.append('implausible_salt')
                if contrib['carbs'] > 100:
                    flags.append('implausible_carbs')
                if flags and ingredient.name not in implausible_items:
                    implausible_items.append(ingredient.name)

                debug_entries.append({
                    'original': ingredient.raw or ingredient.name,
                    'normalized': explanation.name_en or ingredient.name,
                    'alias': explanation.translation_source if (explanation.translation_source == 'alias') else None,
                    'source_hit': source_hit,
                    'confidence': explanation.translation_confidence,
                    'fdc_id': explanation.fdc_id,
                    'fdc_match_score': explanation.fdc_match_score,
                    'raw_nutrients_per_100g': asdict(nutrients),
                    'grams': ingredient.grams,
                    'calc': calc_formula,
                    'contribution': contrib,
                    'rules': list(explanation.rules_applied),
                    'flags': flags,
                })
            
            explanations.append(explanation)
        
        # Convert sodium back to salt for display
        salt_g = total_nutrients['sodium'] * 2.5 / 1000
        total_nutrients['salt'] = salt_g
        
        # Calculate per-serving values
        per_serving = {}
        for key, value in total_nutrients.items():
            per_serving[key] = round(value / servings, 1) if servings > 0 else 0
        
        # Round totals
        total = {key: round(value, 1) for key, value in total_nutrients.items()}
        
        # Reasonableness checks
        warnings = []
        if per_serving.get('calories', 0) > 2000:
            warnings.append("calories_implausible")
        if per_serving.get('salt', 0) > 10:
            warnings.append("salt_implausible")
        
        # Ensure explanations are plain dicts for JSON serialization
        explanations_serialized = []
        for e in explanations:
            try:
                explanations_serialized.append(asdict(e))
            except Exception:
                # fallback: best-effort manual mapping
                explanations_serialized.append({
                    'parsed': getattr(e, 'parsed', {}),
                    'fdc_id': getattr(e, 'fdc_id', None),
                    'data_type': getattr(e, 'data_type', None),
                    'portion_source': getattr(e, 'portion_source', ''),
                    'rules_applied': getattr(e, 'rules_applied', []),
                    'name_en': getattr(e, 'name_en', None),
                    'translation_source': getattr(e, 'translation_source', None),
                    'translation_confidence': getattr(e, 'translation_confidence', None),
                })

        return {
            'perServing': per_serving,
            'total': total,
            'explanations': explanations_serialized,
            'warnings': warnings,
            'debugEntries': debug_entries,
            'implausibleItems': implausible_items,
        }

    async def calculate_nutrition(self, ingredients: List[Dict[str, str]], servings: int, recipe_id: Optional[str] = None) -> Dict:
        """Main method to calculate nutrition from ingredients"""
        try:
            logger.info(f"Starting nutrition calculation for {len(ingredients)} ingredients, {servings} servings")
            
            # Parse ingredients
            parsed_ingredients = self.parse_ingredients(ingredients)
            logger.info(f"Parsed {len(parsed_ingredients)} ingredients")
            for ing in parsed_ingredients:
                logger.info(f"Parsed ingredient: {ing}")
            
            # Normalize to grams and find FDC matches
            ingredients_with_data = []
            needs_review = []
            translation_stats = { 'SAFE': 0, 'OK': 0, 'LOW': 0, 'NOMATCH': 0 }
            
            for ingredient in parsed_ingredients:
                ingredient.grams = self.normalize_to_grams(ingredient)
                logger.info(f"Processing ingredient: {ingredient.name} ({ingredient.grams}g)")
                
                # Create explanation object
                explanation = IngredientExplanation(
                    parsed={
                        'quantity': ingredient.quantity,
                        'unit': ingredient.unit,
                        'grams': ingredient.grams,
                        'optional': ingredient.optional,
                        'negligible': ingredient.negligible
                    },
                    fdc_id=None,
                    data_type=None,
                    portion_source="density",
                    rules_applied=[]
                )
                # Store translation info on explanation for transparency
                lowered = ingredient.name.lower()
                has_swedish_chars = bool(re.search(r"[åäöÅÄÖ]", ingredient.name))
                matches_sv_alias = any(alias in lowered for alias in GLOSSARY.keys())
                lang = 'sv' if (has_swedish_chars or matches_sv_alias) else 'en'
                t = translate_ingredient_name(ingredient.name, lang, parsed_name=ingredient.name, quantity=ingredient.quantity, unit=ingredient.unit)
                explanation.name_en = t.get('name_en') or ingredient.name
                explanation.translation_source = t.get('source')
                explanation.translation_confidence = t.get('confidence')
                t_class = t.get('class', 'NOMATCH')
                translation_stats[t_class] = translation_stats.get(t_class, 0) + 1
                if t_class in ('LOW','NOMATCH') and ingredient.name not in needs_review:
                    needs_review.append(ingredient.name)
                
                # Find FDC match
                fdc_match = await self.find_fdc_match(ingredient.name)
                
                if fdc_match:
                    logger.info(f"Found FDC match for {ingredient.name}: {fdc_match.description} (score: {fdc_match.match_score})")
                    nutrients = await self.fetch_fdc_nutrients(fdc_match.fdc_id)
                    logger.info(f"Nutrients for {ingredient.name}: {nutrients}")
                    
                    if nutrients is None:
                        logger.error(f"Failed to fetch nutrients for {ingredient.name}")
                        ingredients_with_data.append((ingredient, None, explanation))
                        needs_review.append(ingredient.name)
                    else:
                        explanation.fdc_id = fdc_match.fdc_id
                        explanation.data_type = fdc_match.data_type
                        try:
                            explanation.fdc_match_score = getattr(fdc_match, 'match_score', None)
                        except Exception:
                            pass
                        explanation.portion_source = "fdc"
                        ingredients_with_data.append((ingredient, nutrients, explanation))
                else:
                    logger.warning(f"No FDC match found for {ingredient.name}")
                    ingredients_with_data.append((ingredient, None, explanation))
                    needs_review.append(ingredient.name)
            
            # Compute totals
            result = self.compute_totals(ingredients_with_data, servings)
            result['needsReview'] = needs_review
            result['translationStats'] = translation_stats
            # meta warning if low confidence share > 0.3
            total_items = max(1, sum(translation_stats.values()))
            low_share = (translation_stats.get('LOW',0) + translation_stats.get('NOMATCH',0)) / total_items
            if low_share > 0.3:
                result['meta'] = { 'warning': 'nutrition_low_confidence' }

            # Merge implausible per-ingredient flags into needsReview
            for name in result.get('implausibleItems', []):
                if name not in result['needsReview']:
                    result['needsReview'].append(name)

            # Write debug markdown report regardless of success/failure
            try:
                rid = str(recipe_id) if recipe_id else 'unknown'
                os.makedirs('tmp', exist_ok=True)
                path = os.path.join('tmp', f'nutrition_debug_{rid}.md')
                lines = []
                lines.append(f"# Nutrition Debug Report — recipe {rid}\n")
                lines.append(f"Servings: {servings}\n")
                lines.append(f"Total per serving: {json.dumps(result.get('perServing', {}), ensure_ascii=False)}\n")
                lines.append(f"Total batch: {json.dumps(result.get('total', {}), ensure_ascii=False)}\n")
                lines.append("\n## Ingredients\n")
                for entry in result.get('debugEntries', []):
                    warn = ' ⚠️' if entry.get('flags') else ''
                    lines.append(f"### {entry.get('normalized')}{warn}\n")
                    lines.append(f"- original: {entry.get('original')}\n")
                    lines.append(f"- alias: {entry.get('alias') or '—'}\n")
                    lines.append(f"- source_hit: {entry.get('source_hit')}\n")
                    lines.append(f"- confidence: {entry.get('confidence')}\n")
                    lines.append(f"- fdc_id: {entry.get('fdc_id')} (score={entry.get('fdc_match_score')})\n")
                    lines.append(f"- raw_nutrients_per_100g: {json.dumps(entry.get('raw_nutrients_per_100g'), default=str, ensure_ascii=False)}\n")
                    lines.append(f"- amount: {entry.get('grams')} g\n")
                    lines.append(f"- calculation: {entry.get('calc')}\n")
                    lines.append(f"- contribution: {json.dumps(entry.get('contribution'), ensure_ascii=False)}\n")
                    lines.append(f"- rules: {', '.join(entry.get('rules') or [])}\n")
                    if entry.get('flags'):
                        lines.append(f"- flags: {', '.join(entry.get('flags'))}\n")
                    lines.append("\n")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            except Exception as e:
                logger.warning(f"Failed to write debug report: {e}")
            
            logger.info(f"Nutrition calculation completed. Needs review: {needs_review}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating nutrition: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return placeholder data on error
            return {
                'perServing': {
                    'calories': 250,
                    'protein': 12.5,
                    'fat': 8.0,
                    'carbs': 35.0,
                    'saturatedFat': 2.5,
                    'sugar': 5.0,
                    'fiber': 3.0,
                    'sodium': 400,
                    'cholesterol': 25
                },
                'total': {
                    'calories': 250 * servings,
                    'protein': 12.5 * servings,
                    'fat': 8.0 * servings,
                    'carbs': 35.0 * servings,
                    'saturatedFat': 2.5 * servings,
                    'sugar': 5.0 * servings,
                    'fiber': 3.0 * servings,
                    'sodium': 400 * servings,
                    'cholesterol': 25 * servings
                },
                'needsReview': []
            }
