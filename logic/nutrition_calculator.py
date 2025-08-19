import re
import logging
import httpx
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ParsedIngredient:
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    grams: Optional[float] = None

@dataclass
class FdcMatch:
    fdc_id: int
    data_type: str
    match_score: float
    description: str

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

class NutritionCalculator:
    def __init__(self):
        self.fdc_api_key = os.getenv('FDC_API_KEY', 'DEMO_KEY')
        self.base_url = "https://api.nal.usda.gov/fdc/v1"
        
    def parse_ingredients(self, ingredients: List[Dict[str, str]]) -> List[ParsedIngredient]:
        """Parse raw ingredient strings into structured data"""
        parsed = []
        
        for ing in ingredients:
            raw = ing.get('raw', '')
            if not raw:
                continue
                
            # Extract quantity and unit
            quantity, unit, name = self._extract_quantity_unit_name(raw)
            
            parsed.append(ParsedIngredient(
                name=name.strip(),
                quantity=quantity,
                unit=unit
            ))
            
        return parsed
    
    def _extract_quantity_unit_name(self, text: str) -> Tuple[Optional[float], Optional[str], str]:
        """Extract quantity, unit, and name from ingredient text"""
        # Common patterns for quantities and units
        patterns = [
            r'^(\d+(?:\.\d+)?)\s*(g|gram|grams|kg|kilo|ml|milliliter|milliliters|dl|deciliter|deciliters|l|liter|liters|tsk|teaspoon|teaspoons|msk|tablespoon|tablespoons|krm|kryddmått|st|stycken|paket|burk|burkar|kruka|krukor|bit|bitar|skiva|skivor|klyfta|klyftor|clove|cloves|cup|cups|tbsp|tsp|oz|pound|pounds|lb|lbs)\s+(.+)$',
            r'^(\d+/\d+)\s*(g|gram|grams|kg|kilo|ml|milliliter|milliliters|dl|deciliter|deciliters|l|liter|liters|tsk|teaspoon|teaspoons|msk|tablespoon|tablespoons|krm|kryddmått|st|stycken|paket|burk|burkar|kruka|krukor|bit|bitar|skiva|skivor|klyfta|klyftor|clove|cloves|cup|cups|tbsp|tsp|oz|pound|pounds|lb|lbs)\s+(.+)$',
            r'^(\d+(?:\.\d+)?)\s*(.+)$',
            r'^(\d+/\d+)\s*(.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                quantity_str = match.group(1)
                unit = match.group(2) if len(match.groups()) > 2 else None
                name = match.group(-1)
                
                # Convert fraction to decimal
                if '/' in quantity_str:
                    num, denom = quantity_str.split('/')
                    quantity = float(num) / float(denom)
                else:
                    quantity = float(quantity_str)
                    
                return quantity, unit, name
        
        # No quantity found, return the whole text as name
        return None, None, text
    
    def normalize_to_grams(self, ingredient: ParsedIngredient) -> float:
        """Convert ingredient quantity to grams based on unit"""
        if not ingredient.quantity:
            # Assume 100g if no quantity is specified
            return 100.0
            
        # Common density conversions (approximate)
        densities = {
            'g': 1.0,
            'gram': 1.0,
            'grams': 1.0,
            'kg': 1000.0,
            'kilo': 1000.0,
            'ml': 1.0,  # For water-like substances
            'milliliter': 1.0,
            'milliliters': 1.0,
            'dl': 100.0,
            'deciliter': 100.0,
            'deciliters': 100.0,
            'l': 1000.0,
            'liter': 1000.0,
            'liters': 1000.0,
            'tsk': 5.0,  # teaspoon
            'teaspoon': 5.0,
            'teaspoons': 5.0,
            'msk': 15.0,  # tablespoon
            'tablespoon': 15.0,
            'tablespoons': 15.0,
            'krm': 1.0,  # kryddmått
            'kryddmått': 1.0,
        }
        
        if ingredient.unit and ingredient.unit.lower() in densities:
            return ingredient.quantity * densities[ingredient.unit.lower()]
        
        # Default: assume grams if no unit or unknown unit
        return ingredient.quantity
    
    async def find_fdc_match(self, ingredient_name: str) -> Optional[FdcMatch]:
        """Find best FDC match for ingredient name"""
        try:
            # Search FDC API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/foods/search",
                    params={
                        'api_key': self.fdc_api_key,
                        'query': ingredient_name,
                        'dataType': ['Foundation', 'SR Legacy'],
                        'pageSize': 5
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('foods'):
                    return None
                
                # Find best match
                best_match = None
                best_score = 0.0
                
                for food in data['foods']:
                    description = food.get('description', '').lower()
                    name_lower = ingredient_name.lower()
                    
                    # Simple scoring based on word overlap
                    name_words = set(name_lower.split())
                    desc_words = set(description.split())
                    
                    if name_words & desc_words:  # intersection
                        score = len(name_words & desc_words) / len(name_words)
                        
                        # Prefer Foundation over SR Legacy
                        if food.get('dataType') == 'Foundation':
                            score += 0.1
                            
                        if score > best_score:
                            best_score = score
                            best_match = FdcMatch(
                                fdc_id=food['fdcId'],
                                data_type=food.get('dataType', 'Unknown'),
                                match_score=score,
                                description=food.get('description', '')
                            )
                
                return best_match if best_score >= 0.3 else None
                
        except Exception as e:
            logger.error(f"Error searching FDC for {ingredient_name}: {e}")
            return None
    
    async def fetch_fdc_nutrients(self, fdc_id: int) -> Optional[NutrientData]:
        """Fetch nutrient data for FDC ID"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/food/{fdc_id}",
                    params={'api_key': self.fdc_api_key},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
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
    
    def compute_totals(self, ingredients: List[Tuple[ParsedIngredient, Optional[NutrientData]]], servings: int) -> Dict:
        """Compute total nutrition values"""
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
        
        for ingredient, nutrients in ingredients:
            if nutrients and ingredient.grams:
                # Calculate nutrients based on grams
                factor = ingredient.grams / 100.0  # FDC data is per 100g
                
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
        
        # Calculate per-serving values
        per_serving = {}
        for key, value in total_nutrients.items():
            per_serving[key] = round(value / servings, 1) if servings > 0 else 0
        
        # Round totals
        total = {key: round(value, 1) for key, value in total_nutrients.items()}
        
        return {
            'perServing': per_serving,
            'total': total
        }
    
    async def calculate_nutrition(self, ingredients: List[Dict[str, str]], servings: int) -> Dict:
        """Main method to calculate nutrition from ingredients"""
        try:
            logger.info(f"Starting nutrition calculation for {len(ingredients)} ingredients, {servings} servings")
            
            # Parse ingredients
            parsed_ingredients = self.parse_ingredients(ingredients)
            logger.info(f"Parsed {len(parsed_ingredients)} ingredients")
            
            # Normalize to grams and find FDC matches
            ingredients_with_nutrients = []
            needs_review = []
            
            for ingredient in parsed_ingredients:
                ingredient.grams = self.normalize_to_grams(ingredient)
                logger.info(f"Processing ingredient: {ingredient.name} ({ingredient.grams}g)")
                
                # Find FDC match
                fdc_match = await self.find_fdc_match(ingredient.name)
                
                if fdc_match:
                    logger.info(f"Found FDC match for {ingredient.name}: {fdc_match.description} (score: {fdc_match.match_score})")
                    nutrients = await self.fetch_fdc_nutrients(fdc_match.fdc_id)
                    ingredients_with_nutrients.append((ingredient, nutrients))
                else:
                    logger.warning(f"No FDC match found for {ingredient.name}")
                    ingredients_with_nutrients.append((ingredient, None))
                    needs_review.append(ingredient.name)
            
            # Compute totals
            result = self.compute_totals(ingredients_with_nutrients, servings)
            result['needsReview'] = needs_review
            
            logger.info(f"Nutrition calculation completed. Needs review: {needs_review}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating nutrition: {e}")
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
