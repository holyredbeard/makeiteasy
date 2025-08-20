import re
import logging
from typing import List, Dict, Optional, Tuple

from core.database import db
from logic.rules_loader import load_portion_rules

logger = logging.getLogger(__name__)


def _parse_qty_unit_name(text: str) -> Tuple[Optional[float], Optional[str], str]:
    t = (text or '').strip()
    # unicode fractions
    t = t.replace('½', '1/2').replace('¼', '1/4').replace('¾', '3/4')
    # decimal comma
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    # remove temperature parentheses entirely
    t = re.sub(r"\((?=[^)]*(?:°C|°F|temperatur|varmt))[^)]*\)", "", t, flags=re.I)
    # prefer parenthetical amounts like (355 ml), (490 g), (2 1/4 tsk)
    paren_match = re.search(r"\(([^)]*?)\)", t)
    if paren_match:
        inside = paren_match.group(1)
        inside = inside.replace('\u202f', ' ').replace('\u00a0', ' ')
        m2 = re.match(r"\s*(\d+(?:[\./]\d+)?(?:\s+\d+/\d+)?)\s*(\w+)\s*$", inside)
        if m2:
            q = m2.group(1)
            try:
                # support mixed fraction like 2 1/4
                if ' ' in q and '/' in q:
                    a, b = q.split(' ', 1)
                    num, den = b.split('/')
                    qty = float(a) + float(num) / float(den)
                elif '/' in q:
                    num, den = q.split('/')
                    qty = float(num) / float(den)
                else:
                    qty = float(q)
            except Exception:
                qty = None
            unit = m2.group(2)
            unit_map = {
                'tsk': 'tsp', 'tesked': 'tsp',
                'msk': 'tbsp', 'matsked': 'tbsp',
                'dl': 'dl', 'l': 'l', 'ml': 'ml',
                'g': 'g', 'gram': 'g',
                'kg': 'kg', 'kilogram': 'kg',
                'cup': 'cup',
                'krm': 'tsp',  # kryddmått (1 ml) ≈ 0.2 tsp
            }
            orig_unit = (unit or '').lower()
            unit = unit_map.get(orig_unit, unit)
            if orig_unit == 'krm' and qty is not None:
                qty = qty * 0.2
            # remove the parentheses used for qty from the name text
            name_out = (t[:paren_match.start()] + ' ' + t[paren_match.end():]).strip()
            return qty, unit, name_out
    # Handle range quantities like "1-2 avokador" or "2-3 cups"
    range_match = re.match(r"^(\d+)-(\d+)\s+(.+)$", t)
    if range_match:
        min_qty = float(range_match.group(1))
        max_qty = float(range_match.group(2))
        qty = (min_qty + max_qty) / 2.0  # Use average
        name = range_match.group(3)
        return qty, None, name  # No unit for range quantities
    
    # patterns
    m = re.match(r"^(\d+(?:[\./]\d+)?)\s*(\w+)\s+(.+)$", t)
    if m:
        q = m.group(1)
        try:
            qty = float(eval(q.replace('/', '/')))
        except Exception:
            qty = None
        unit = m.group(2)
        # unit synonyms sv→en
        unit_map = {
            'tsk': 'tsp', 'tesked': 'tsp',
            'msk': 'tbsp', 'matsked': 'tbsp',
            'dl': 'dl', 'l': 'l', 'ml': 'ml',
            'g': 'g', 'gram': 'g',
            'kg': 'kg', 'kilogram': 'kg',
            'cup': 'cup', 'kopp': 'cup',
            'recept': 'each',  # Handle "1 recept" as "1 each"
            'krm': 'tsp',      # 1 krm = 1 ml ≈ 0.2 tsp
        }
        orig_unit = (unit or '').lower()
        unit = unit_map.get(orig_unit, unit)
        if orig_unit == 'krm' and qty is not None:
            qty = qty * 0.2
        return qty, unit, m.group(3)
    m = re.match(r"^(\d+(?:[\./]\d+)?)\s+(.+)$", t)
    if m:
        try:
            qty = float(eval(m.group(1).replace('/', '/')))
        except Exception:
            qty = None
        return qty, None, m.group(2)
    return None, None, t


WL = {
    'butter_tbsp_g': 14.2,
    'brown_sugar_tbsp_g': 12.5,
    'cinnamon_tsp_g': 2.6,
    'pecans_cup_g': 100.0,
    'pasta_cup_g': 100.0,
    'milk_cup_g': 245.0,
}

ML = {'tsp': 5.0, 'tbsp': 15.0, 'cup': 240.0, 'dl': 100.0, 'l': 1000.0}


def _wl_grams(name: str, qty: float, unit: Optional[str]) -> Optional[float]:
    n = (name or '').lower()
    u = (unit or '').lower()
    if 'butter' in n and u in ('tbsp', 'tablespoon'):
        return qty * WL['butter_tbsp_g']
    if 'brown sugar' in n and u in ('tbsp', 'tablespoon'):
        return qty * WL['brown_sugar_tbsp_g']
    if 'cinnamon' in n and u in ('tsp', 'teaspoon'):
        return qty * WL['cinnamon_tsp_g']
    if 'pecan' in n and u in ('cup',):
        g = qty * WL['pecans_cup_g']
        # clamp
        if g < 80: g = 80
        if g > 130: g = 130
        return g
    if ('pasta' in n or 'macaroni' in n or 'spaghetti' in n) and u in ('cup',):
        return qty * WL['pasta_cup_g']
    if ('milk' in n or 'soy' in n) and u in ('cup',):
        return qty * WL['milk_cup_g']
    return None


def _spice_default(name: str) -> bool:
    return any(k in (name or '').lower() for k in ['pepper', 'cinnamon', 'spice', 'paprika', 'turmeric', 'ginger', 'chili'])


PIZZA_DEFAULTS_G = {
    'tomatsås': 125.0,
    'mozzarella': 85.0,
    'mozzarella riven': 100.0,
    'fontina': 80.0,
    'parmesan': 20.0,
    'feta': 30.0,
    'pepperoni': 30.0,
    'korv': 60.0,
    'skinka': 40.0,
    'svamp': 40.0,
    'oliver': 25.0,
    'lök': 30.0,
    'paprika': 30.0,
    'pepperoncini': 15.0,
    'basilika': 5.0,
    'rucola': 30.0,
    'pesto': 15.0,
}


def _load_yaml_overrides():
    """Load units/policy/categories from YAML and build helpers."""
    rules = load_portion_rules() or {}
    units = rules.get('units') or {}
    ml_map = {
        'tsp': float(units.get('tsp_ml', 5)),
        'tbsp': float(units.get('tbsp_ml', 15)),
        'cup': float(units.get('cup_ml', 240)),
        'dl': float(units.get('dl_ml', 100)),
        'l': float(units.get('l_ml', 1000)),
        'ml': 1.0,
    }
    categories = rules.get('categories') or {}
    policy = rules.get('policy') or {}
    return ml_map, categories, policy


def _match_yaml_category(name: str, categories: Dict) -> Optional[Dict]:
    lname = (name or '').lower()
    for key, cfg in (categories or {}).items():
        for m in (cfg or {}).get('match', []) or []:
            if str(m).lower() in lname:
                out = dict(cfg)
                out['__key'] = key
                return out
    return None


async def compute_safe_snapshot(ingredients: List[Dict[str, str]], servings: int) -> Dict:
    # Minimal per-100g tables for whitelist-kategorier (snabbt och lokalt)
    PER100G = {
        'butter':      dict(calories=717, protein=0.9, fat=81.1, saturatedFat=51.4, carbs=0.1, sugar=0.1, fiber=0.0, sodium=11, cholesterol=215),
        'brown_sugar': dict(calories=380, protein=0.0, fat=0.0, saturatedFat=0.0, carbs=98.0, sugar=97.0, fiber=0.0, sodium=28, cholesterol=0),
        'cinnamon':    dict(calories=247, protein=4.0, fat=1.2, saturatedFat=0.3, carbs=81.0, sugar=2.2, fiber=53.0, sodium=10, cholesterol=0),
        'pecans':      dict(calories=691, protein=9.2, fat=72.0, saturatedFat=6.2, carbs=14.0, sugar=4.0, fiber=10.0, sodium=0, cholesterol=0),
        'pasta_dry':   dict(calories=371, protein=13.0, fat=1.5, saturatedFat=0.3, carbs=74.0, sugar=2.7, fiber=3.2, sodium=6, cholesterol=0),
        'milk':        dict(calories=61,  protein=3.2, fat=3.2, saturatedFat=1.9, carbs=4.7, sugar=5.0, fiber=0.0, sodium=43, cholesterol=10),
        'soy_milk':    dict(calories=54,  protein=3.3, fat=1.8, saturatedFat=0.3, carbs=6.3, sugar=3.0, fiber=0.6, sodium=44, cholesterol=0),
        'oil':         dict(calories=884, protein=0.0, fat=100.0, saturatedFat=14.0, carbs=0.0, sugar=0.0, fiber=0.0, sodium=0.0, cholesterol=0.0),
        'nuts':        dict(calories=607, protein=18.0, fat=54.0, saturatedFat=10.0, carbs=30.0, sugar=6.0, fiber=3.0, sodium=12, cholesterol=0),
        'sugar':       dict(calories=387, protein=0.0, fat=0.0, saturatedFat=0.0, carbs=100.0, sugar=100.0, fiber=0.0, sodium=0, cholesterol=0),
        'flour':       dict(calories=364, protein=10.0, fat=1.0, saturatedFat=0.2, carbs=76.0, sugar=1.0, fiber=2.7, sodium=2, cholesterol=0),
        'rice_dry':    dict(calories=360, protein=7.0, fat=0.7, saturatedFat=0.2, carbs=79.0, sugar=0.1, fiber=1.3, sodium=0, cholesterol=0),
        'cabbage':     dict(calories=25, protein=1.3, fat=0.1, saturatedFat=0.0, carbs=6.0, sugar=3.2, fiber=2.5, sodium=18, cholesterol=0),
        'leafy':       dict(calories=23, protein=2.9, fat=0.4, saturatedFat=0.1, carbs=3.6, sugar=0.4, fiber=2.2, sodium=79, cholesterol=0),
        'tofu':        dict(calories=144, protein=14.0, fat=8.8, saturatedFat=1.2, carbs=3.3, sugar=1.0, fiber=1.0, sodium=14, cholesterol=0),
        'seitan':      dict(calories=370, protein=75.0, fat=1.9, saturatedFat=0.5, carbs=14.0, sugar=0.5, fiber=0.0, sodium=30, cholesterol=0),
        'coconut_milk':dict(calories=170, protein=2.0, fat=18.0, saturatedFat=15.0, carbs=3.0, sugar=2.0, fiber=0.0, sodium=15, cholesterol=0),
    }
    
    # Pre-load portion_resolver and rules once
    try:
        from logic.portion_resolver import resolve_grams
        from logic.rules_loader import load_portion_rules
        rules = load_portion_rules()
        portion_resolver_available = True
    except Exception:
        portion_resolver_available = False
        rules = None
    totals = {k: 0.0 for k in ['calories', 'protein', 'fat', 'saturatedFat', 'carbs', 'sugar', 'fiber', 'sodium', 'cholesterol']}
    skipped: List[str] = []
    flags: List[str] = []
    sodium_total_mg = 0.0
    debug_lines: List[str] = []

    def _get_per100(name: str) -> Optional[Dict[str, float]]:
        n = (name or '').lower()
        if 'butter' in n or 'smör' in n: return PER100G['butter']
        if 'brown sugar' in n: return PER100G['brown_sugar']
        if 'socker' in n or 'sugar' in n: return PER100G['sugar']
        if 'mjöl' in n or 'flour' in n: return PER100G['flour']
        if 'cinnamon' in n or 'kanel' in n: return PER100G['cinnamon']
        if 'pecan' in n: return PER100G['pecans']
        if 'pasta' in n or 'macaroni' in n or 'spaghetti' in n or 'nudel' in n or 'noodle' in n or 'makaroner' in n or 'idealmakaroner' in n: return PER100G['pasta_dry']
        if 'ris' in n or 'rice' in n: return PER100G['rice_dry']
        if 'soy' in n or 'soja' in n: return PER100G['soy_milk']
        if 'milk' in n or 'mjölk' in n: return PER100G['milk']
        if 'olja' in n or 'oil' in n or 'olive' in n: return PER100G['oil']
        if 'cashew' in n or 'cashewnöt' in n or 'cashewnötter' in n or 'nöt' in n or 'mandel' in n or 'almond' in n: return PER100G['nuts']
        if 'kål' in n or 'cabbage' in n: return PER100G['cabbage']
        if 'sallad' in n or 'spenat' in n or 'lettuce' in n or 'spinach' in n: return PER100G['leafy']
        if 'tofu' in n: return PER100G['tofu']
        if 'seitan' in n: return PER100G['seitan']
        if 'kokosmjölk' in n or 'coconut milk' in n: return PER100G['coconut_milk']
        # Add more Swedish ingredients
        if 'kyckling' in n or 'chicken' in n: return dict(calories=165, protein=31.0, fat=3.6, saturatedFat=1.1, carbs=0.0, sugar=0.0, fiber=0.0, sodium=74, cholesterol=85)
        # Beef and beef stewing cuts
        if any(k in n for k in ['nöt', 'notkott', 'nötkött', 'ox', 'beef', 'grytbit', 'grytbitar', 'högrev', 'biff']):
            return dict(calories=250, protein=26.0, fat=17.0, saturatedFat=7.0, carbs=0.0, sugar=0.0, fiber=0.0, sodium=72, cholesterol=90)
        # Bacon (cooked average)
        if 'bacon' in n:
            return dict(calories=541, protein=37.0, fat=42.0, saturatedFat=14.0, carbs=2.0, sugar=1.4, fiber=0.0, sodium=1717, cholesterol=110)
        # Potatoes
        if 'potatis' in n or 'potato' in n or 'potatoes' in n:
            return dict(calories=77, protein=2.0, fat=0.1, saturatedFat=0.0, carbs=17.0, sugar=0.8, fiber=2.2, sodium=6, cholesterol=0)
        # Mushrooms
        if 'svamp' in n or 'champinjon' in n or 'champinjoner' in n or 'mushroom' in n:
            return dict(calories=22, protein=3.1, fat=0.3, saturatedFat=0.0, carbs=3.3, sugar=2.0, fiber=1.0, sodium=5, cholesterol=0)
        # Wine (red/cooking)
        if 'vin' in n or 'wine' in n:
            return dict(calories=85, protein=0.1, fat=0.0, saturatedFat=0.0, carbs=2.6, sugar=0.6, fiber=0.0, sodium=5, cholesterol=0)
        # Vinegar (balsamic)
        if 'balsam' in n or 'balsamic' in n or 'vinegar' in n:
            return dict(calories=88, protein=0.5, fat=0.0, saturatedFat=0.0, carbs=17.0, sugar=15.0, fiber=0.0, sodium=23, cholesterol=0)
        if 'tomat' in n or 'tomato' in n: return dict(calories=18, protein=0.9, fat=0.2, saturatedFat=0.0, carbs=3.9, sugar=2.6, fiber=1.2, sodium=5, cholesterol=0)
        if 'lök' in n or 'onion' in n: return dict(calories=40, protein=1.1, fat=0.1, saturatedFat=0.0, carbs=9.3, sugar=4.7, fiber=1.7, sodium=4, cholesterol=0)
        if 'vitlök' in n or 'garlic' in n: return dict(calories=149, protein=6.4, fat=0.5, saturatedFat=0.1, carbs=33.1, sugar=1.0, fiber=2.1, sodium=17, cholesterol=0)
        if 'ägg' in n or 'egg' in n: return dict(calories=155, protein=12.6, fat=10.6, saturatedFat=3.3, carbs=1.1, sugar=1.1, fiber=0.0, sodium=124, cholesterol=373)
        if 'peppar' in n or 'pepper' in n: return dict(calories=251, protein=10.4, fat=3.3, saturatedFat=1.4, carbs=64.0, sugar=0.6, fiber=25.3, sodium=20, cholesterol=0)
        # Handle "recept" items
        if 'carne asada' in n: return dict(calories=300, protein=20.0, fat=0.0, saturatedFat=0.0, carbs=60.0, sugar=0.0, fiber=20.0, sodium=6200, cholesterol=0)
        if 'chicken tinga' in n: return dict(calories=93, protein=9.29, fat=3.57, saturatedFat=0.71, carbs=5.0, sugar=2.14, fiber=0.7, sodium=493, cholesterol=25)
        if 'avokado' in n or 'avocado' in n: return dict(calories=160, protein=2.0, fat=15.0, saturatedFat=2.1, carbs=9.0, sugar=0.7, fiber=6.7, sodium=7, cholesterol=0)
        if 'majstortillas' in n or 'corn tortillas' in n: return dict(calories=177, protein=21.2, fat=6.12, saturatedFat=0.877, carbs=7.46, sugar=0.0, fiber=0.0, sodium=574, cholesterol=106)
        if 'koriander' in n or 'cilantro' in n: return dict(calories=23, protein=2.1, fat=0.5, saturatedFat=0.0, carbs=3.7, sugar=0.9, fiber=2.8, sodium=46, cholesterol=0)
        if 'jalapeño' in n or 'jalapeno' in n: return dict(calories=29, protein=0.9, fat=0.4, saturatedFat=0.1, carbs=6.5, sugar=4.1, fiber=2.8, sodium=3, cholesterol=0)
        if 'cotijaost' in n or 'cotija cheese' in n: return dict(calories=366, protein=20.0, fat=30.0, saturatedFat=19.0, carbs=3.0, sugar=0.0, fiber=0.0, sodium=1400, cholesterol=95)
        if 'lime' in n: return dict(calories=30, protein=0.7, fat=0.2, saturatedFat=0.0, carbs=10.5, sugar=1.7, fiber=2.8, sodium=2, cholesterol=0)
        return None

    spice_acc = 0.0

    yaml_ML, yaml_categories, yaml_policy = _load_yaml_overrides()

    # Pre-parse all ingredients for better performance
    parsed_ingredients = []
    for ing in ingredients or []:
        raw = (ing.get('raw') or '').strip()
        if not raw:
            continue
        qty, unit, name = _parse_qty_unit_name(raw)
        lname = (name or '').lower()
        parsed_ingredients.append((raw, qty, unit, name, lname))

    for raw, qty, unit, name, lname in parsed_ingredients:

        # Exclude water/ice
        if lname in ('water', 'ice'):
            debug_lines.append(f"SKIP water/ice: {raw}")
            continue

        grams = None
        source = None
        
        # Try whitelist mappings first (with quantity)
        if qty is not None:
            grams = _wl_grams(lname, float(qty), unit)
            if grams is not None:
                source = 'wl'
        
        # Try per-100g nutrition matching (with or without quantity)
        if grams is None:
            nutrients = _get_per100(lname)
            if nutrients is not None and qty is not None:
                # We have nutritional data and quantity - estimate grams
                if unit and unit.lower() in ('each', 'st', 'styck', 'pcs', 'pc'):
                    # For "each" items, use reasonable defaults
                    if 'carne asada' in lname or 'chicken tinga' in lname:
                        grams = float(qty) * 200.0  # 200g per recipe portion
                    elif 'avokado' in lname or 'avocado' in lname:
                        grams = float(qty) * 150.0  # 150g per avocado
                    elif 'majstortillas' in lname or 'tortillas' in lname:
                        grams = float(qty) * 30.0   # 30g per tortilla
                    else:
                        grams = float(qty) * 100.0  # 100g default
                    source = 'nutrition_each'
                elif unit and unit.lower() in ('cup', 'kopp'):
                    grams = float(qty) * 120.0  # 120g per cup for most items
                    source = 'nutrition_cup'
                elif unit and unit.lower() in ('tbsp', 'msk'):
                    grams = float(qty) * 15.0   # 15g per tbsp
                    source = 'nutrition_tbsp'
                elif unit and unit.lower() in ('tsp', 'tsk'):
                    grams = float(qty) * 5.0    # 5g per tsp
                    source = 'nutrition_tsp'
                else:
                    # Avoid overriding explicit mass units; let general mass handling compute grams
                    if not unit or unit.lower() not in ('g', 'gram', 'grams', 'kg', 'kilo'):
                        grams = float(qty) * 100.0  # fallback for ambiguous units
                        source = 'nutrition_fallback'
            elif nutrients is not None and qty is None:
                # We have nutritional data but no quantity - use defaults
                if 'carne asada' in lname or 'chicken tinga' in lname:
                    grams = 200.0  # 200g per recipe portion
                elif 'avokado' in lname or 'avocado' in lname:
                    grams = 150.0  # 150g per avocado
                elif 'majstortillas' in lname or 'tortillas' in lname:
                    grams = 30.0   # 30g per tortilla
                else:
                    grams = 100.0  # 100g default
                source = 'nutrition_default'
        
        # Use improved portion_resolver for missing quantities (as fallback)
        if grams is None and qty is None:
            if portion_resolver_available and rules:
                try:
                    resolved = resolve_grams(None, None, name, None, rules)
                    if resolved and resolved.get('grams'):
                        grams = resolved['grams']
                        source = 'portion_resolver_default'
                        debug_lines.append(f"OK  default: {name} => {grams:.1f} g (via portion_resolver)")
                except Exception as e:
                    debug_lines.append(f"SKIP portion_resolver failed: {name} - {e}")
                    # Don't skip yet, continue to other logic
            else:
                debug_lines.append(f"SKIP no portion_resolver: {name}")
                # Don't skip yet, continue to other logic
        # Salt rule
        if lname == 'salt' or ' salt' in lname:
            if qty is None:
                # Use portion_resolver for salt without quantity
                if portion_resolver_available and rules:
                    try:
                        resolved = resolve_grams(None, None, name, None, rules)
                        if resolved and resolved.get('grams'):
                            grams = resolved['grams']
                            sodium_total_mg += grams * 0.393 * 1000.0
                            debug_lines.append(f"OK  salt default: {name} => {grams:.1f} g (sodium {grams*0.393*1000:.0f} mg)")
                            # all other nutrients zero for salt
                            continue
                        else:
                            skipped.append(raw)
                            debug_lines.append(f"SKIP salt no-qty: {raw}")
                            continue
                    except Exception as e:
                        skipped.append(raw)
                        debug_lines.append(f"SKIP salt portion_resolver failed: {raw} - {e}")
                        continue
                else:
                    skipped.append(raw)
                    debug_lines.append(f"SKIP salt no portion_resolver: {raw}")
                    continue
            # quantity+unit → grams via wl or ml density (assume 1.2 g/ml for tsp/tbsp)
            if unit and unit.lower() in ML:
                ml = ML[unit.lower()] * float(qty)
                grams = ml * 1.2
            elif unit and unit.lower() in ('g', 'gram', 'grams'):
                grams = float(qty)
            else:
                skipped.append(raw)
                debug_lines.append(f"SKIP salt unknown-unit: {raw}")
                continue
            sodium_total_mg += grams * 0.393 * 1000.0
            debug_lines.append(f"OK  salt: {qty} {unit or ''} {name} => {grams:.1f} g (sodium {grams*0.393*1000:.0f} mg)")
            # all other nutrients zero for salt
            continue


        # General mass handling (g/kg)
        if grams is None and qty is not None and unit:
            u = unit.lower()
            if u in ('g', 'gram', 'grams'):
                grams = float(qty)
                source = 'mass_g'
            elif u in ('kg', 'kilo'):
                grams = float(qty) * 1000.0
                source = 'mass_kg'
        # Density by category for volume units
        # YAML categories first (explicit whitelist)
        cat = _match_yaml_category(lname, yaml_categories)
        if grams is None and qty is not None and unit and cat is not None:
            u = unit.lower()
            # direct unit grams in YAML
            if u in ('tbsp', 'tablespoon') and cat.get('gram_per_tbsp') is not None:
                grams = float(qty) * float(cat['gram_per_tbsp'])
                source = 'yaml_tbsp'
            elif u in ('tsp', 'teaspoon') and cat.get('gram_per_tsp') is not None:
                grams = float(qty) * float(cat['gram_per_tsp'])
                source = 'yaml_tsp'
            elif u in ('cup',) and cat.get('gram_per_cup') is not None:
                grams = float(qty) * float(cat['gram_per_cup'])
                source = 'yaml_cup'
            elif u in ('each','st','styck','pcs','pc') and cat.get('grams_per_each') is not None:
                grams = float(qty) * float(cat['grams_per_each'])
                source = 'yaml_each'
            # density from YAML
            elif cat.get('density_g_per_ml') is not None and u in yaml_ML:
                ml = yaml_ML[u] * float(qty)
                grams = ml * float(cat['density_g_per_ml'])
                source = 'yaml_density'

        # Built-in densities if still unresolved
        if grams is None and qty is not None and unit and unit.lower() in ML:
            ml = (yaml_ML.get(unit.lower()) or ML[unit.lower()]) * float(qty)
            dens = None
            if ('olja' in lname) or ('oil' in lname) or ('olive' in lname):
                dens = 0.92
                source = 'dens_oil'
            elif ('cashew' in lname) or ('cashewnöt' in lname) or ('cashewnötter' in lname) or ('nöt' in lname):
                dens = 0.41
                source = 'dens_nuts'
            elif ('pasta' in lname) or ('nudel' in lname) or ('noodle' in lname) or ('spaghetti' in lname) or ('macaroni' in lname):
                dens = 0.43
                source = 'dens_pasta'
            elif ('socker' in lname) or ('sugar' in lname):
                dens = 0.85
                source = 'dens_sugar'
            elif ('mjöl' in lname) or ('flour' in lname):
                dens = 0.60
                source = 'dens_flour'
            elif ('ris' in lname) or ('rice' in lname):
                dens = 0.80
                source = 'dens_rice'
            elif ('kål' in lname) or ('cabbage' in lname):
                dens = 0.30
                source = 'dens_cabbage'
            elif ('sallad' in lname) or ('spenat' in lname) or ('lettuce' in lname) or ('spinach' in lname):
                dens = 0.18
                source = 'dens_leafy'
            elif ('mjölk' in lname) or ('soja' in lname) or ('soy' in lname) or ('milk' in lname) or ('oat milk' in lname) or ('havre' in lname) or ('grädde' in lname) or ('buljong' in lname) or ('kokosmjölk' in lname) or ('coconut milk' in lname):
                dens = 1.03
                source = 'dens_liquid_default'
            if dens is not None:
                grams = ml * dens

        # Heuristic: qty present but unit missing → assume typical units for common words
        if grams is None and qty is not None and (not unit):
            if ('olja' in lname) or ('oil' in lname):
                ml = (yaml_ML.get('tbsp') or 15.0) * float(qty)
                grams = ml * 0.92
                source = 'assume_tbsp_oil'
            elif any(x in lname for x in ['milk','mjölk','juice','saft','grädde','buljong']):
                ml = (yaml_ML.get('dl') or 100.0) * float(qty)
                grams = ml * 1.03
                source = 'assume_dl_liquid'
            elif any(x in lname for x in ['pepper','peppar','curry','kanel','kardemumma','spice','krydda']):
                grams = float(qty) * 2.0
                source = 'assume_tsp_spice'
            elif any(x in lname for x in ['rosmarin','basilika','timjan','dill','koriander','persilja']):
                grams = float(qty) * 5.0
                source = 'assume_tbsp_herb'

        # Spices without quantity → default 1g capped at 10g total
        if grams is None and qty is None and _spice_default(lname):
            add = 1.0
            if spice_acc + add > 10.0:
                add = max(0.0, 10.0 - spice_acc)
                if add == 0.0:
                    skipped.append(raw)
                    debug_lines.append(f"SKIP spice cap reached: {raw}")
                    continue
            grams = add
            spice_acc += add
            flags.append('spice_default')
            source = 'spice_default'

        # Eggs or other 'each' categories without explicit unit but with numeric qty
        if grams is None and qty is not None and not unit and cat is not None and cat.get('grams_per_each') is not None:
            grams = float(qty) * float(cat['grams_per_each'])
            source = 'assume_each_from_category'

        # Pizza defaults for common toppings when still unresolved
        if grams is None and qty is None:
            if 'majsmjöl' in lname:
                debug_lines.append(f"SKIP cornmeal (surface only): {raw}")
                skipped.append(raw)
                continue
            for key, gdef in PIZZA_DEFAULTS_G.items():
                if key in lname:
                    grams = gdef
                    source = 'pizza_default'
                    flags.append('pizza_default')
                    break

        if grams is None:
            skipped.append(raw)
            debug_lines.append(f"SKIP unhandled: {raw}")
            continue

        # plausibility for pasta liters (if unit liter provided)
        if unit and unit.lower() in ('l', 'liter', 'liters') and ('pasta' in lname or 'macaroni' in lname or 'spaghetti' in lname):
            per_liter = grams / float(qty)
            if per_liter < 300:
                grams = 300 * float(qty)
                flags.append('clamped')
                debug_lines.append(f"CLAMP pasta <300g/L: {raw} => {grams:.1f} g")
            elif per_liter > 800:
                grams = 800 * float(qty)
                flags.append('clamped')
                debug_lines.append(f"CLAMP pasta >800g/L: {raw} => {grams:.1f} g")

        # Map rice noodles to pasta if needed
        if ('nudel' in lname) and ('pasta' not in lname):
            lname += ' pasta'

        # per-100g nutrients (Safe Mode: if missing, assume zeros)
        nutrients = _get_per100(lname) or {}
        factor = grams / 100.0
        # record debug line for normal ingredient
        if source == 'wl':
            debug_lines.append(f"OK  {qty} {unit or ''} {name} => {grams:.1f} g [wl]")
        elif source == 'spice_default':
            debug_lines.append(f"OK  {name} => 1.0 g [spice_default]")
        else:
            label = source or 'ok'
            debug_lines.append(f"OK  {qty} {unit or ''} {name} => {grams:.1f} g [{label}]")
        totals['calories'] += (nutrients.get('calories', 0) or 0) * factor
        totals['protein'] += (nutrients.get('protein', 0) or 0) * factor
        totals['fat'] += (nutrients.get('fat', 0) or 0) * factor
        totals['saturatedFat'] += (nutrients.get('saturatedFat', 0) or 0) * factor
        totals['carbs'] += (nutrients.get('carbs', 0) or 0) * factor
        totals['sugar'] += (nutrients.get('sugar', 0) or 0) * factor
        totals['fiber'] += (nutrients.get('fiber', 0) or 0) * factor
        totals['sodium'] += (nutrients.get('sodium', 0) or 0) * factor
        totals['cholesterol'] += (nutrients.get('cholesterol', 0) or 0) * factor

    # Convert sodium to salt when sodium known; else leave as 0 without implying real value
    salt_g = sodium_total_mg * 2.5 / 1000.0
    totals['salt'] = salt_g

    # quick plausibility clamps
    if totals['salt'] / max(1, servings) > 15:
        flags.append('salt_implausible')
        # Hard clamp to 15 g salt per portion
        totals['salt'] = 15.0 * max(1, servings)
        flags.append('salt_clamped')

    per_serving = {k: round(v / max(1, servings), 1) for k, v in totals.items()}
    total = {k: round(v, 1) for k, v in totals.items()}

    meta = {
        'safe_mode': True,
        'skipped': skipped,
        'flags': flags,
        'debugLines': debug_lines,
    }

    return {
        'perServing': per_serving,
        'total': total,
        'meta': meta,
    }


