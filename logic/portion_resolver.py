from typing import Optional, Dict, List, Tuple


ML_CONST = {
    'tsp': 5.0,
    'teaspoon': 5.0,
    'tbsp': 15.0,
    'tablespoon': 15.0,
    'cup': 240.0,
    'dl': 100.0,
    'l': 1000.0,
    'liter': 1000.0,
    'liters': 1000.0,
    'st': 1.0,  # styck - not a volume unit but needed for matching
}


class PortionUnresolved(Exception):
    pass


def _lower(s: Optional[str]) -> str:
    return (s or '').strip().lower()


def _match_category(name: str, rules: dict) -> Tuple[Optional[str], Optional[dict]]:
    cats = (rules or {}).get('categories', {})
    lname = _lower(name)
    best_match = None
    best_length = 0
    
    for key, cfg in cats.items():
        for m in (cfg or {}).get('match', []) or []:
            m_lower = _lower(m)
            if m_lower in lname:
                # Prefer longer matches to avoid "mjöl" matching "mjölk"
                if len(m_lower) > best_length:
                    best_match = (key, cfg)
                    best_length = len(m_lower)
    
    return best_match if best_match else (None, None)


def _extract_portions_from_fdc(food_portions: Optional[list]) -> List[Dict]:
    out: List[Dict] = []
    for p in food_portions or []:
        ht = p.get('householdText') or p.get('modifier') or p.get('portionDescription') or p.get('householdUnit') or ''
        gw = p.get('gramWeight')
        if gw is None:
            continue
        out.append({"householdText": str(ht), "gramWeight": float(gw)})
    return out


def resolve_grams(quantity: Optional[float], unit: Optional[str], name: str, fdc_food_json: Optional[dict], rules: Optional[dict]) -> Dict:
    """Resolve grams using priority:
    1) Category-specific direct mappings (tbsp/tsp/cup/each) from portion_rules
    2) FDC portions
    3) Category density → ml * density
    4) Default for spices
    5) Fallback 100 g

    Returns dict with keys: grams, portion_source, calc, category
    """
    if quantity is None:
        # If spice default present
        cat_key, cat_cfg = _match_category(name, rules or {})
        if cat_key and cat_key.startswith('spices'):
            default_g = ((rules or {}).get('policy', {}) or {}).get('spice_default_grams', 1.5)
            return {"grams": float(default_g), "portion_source": "default_spice", "calc": f"spice default {default_g} g", "category": cat_key}
        
        # Handle new vegetable/fruit categories with default weights when quantity is missing
        if cat_cfg and cat_cfg.get('category') in ['vegetables', 'fruit', 'produce']:
            default_weights = {
                # Vegetables - each
                'vegetables_alliums': 130,      # onion, garlic
                'vegetables_roots_tubers': 120, # carrot, potato
                'vegetables_nightshades': 150,  # tomato, bell pepper
                'vegetables_cucurbits': 200,    # cucumber, zucchini
                'vegetables_leafy_greens': 30,  # lettuce, spinach (per cup)
                'vegetables_legumes': 100,      # peas, green beans
                'vegetables_corn': 150,         # corn
                'vegetables_mushrooms': 50,     # mushrooms
                'vegetables_aromatics': 100,    # celery, asparagus
                'vegetables_olives_capers': 10, # olives, capers
                # Fruits - each
                'fruit_citrus': 130,            # orange, lemon
                'fruit_berries': 5,             # berries (per piece)
                'fruit_pomes_stone_tropical': 150, # apple, banana
                'fruit_dried': 5,               # raisins, dried fruit
            }
            
            if cat_key in default_weights:
                default_weight = default_weights[cat_key]
                return {"grams": float(default_weight), "portion_source": "default_produce", "calc": f"default {default_weight} g for {cat_key}", "category": cat_key}
        
        # Handle other categories with default units
        if cat_cfg:
            if cat_cfg.get('default_unit') == 'each' and cat_cfg.get('grams_per_each'):
                default_weight = cat_cfg['grams_per_each']
                return {"grams": float(default_weight), "portion_source": "default_each", "calc": f"default {default_weight} g per each", "category": cat_key}
            elif cat_cfg.get('default_unit') == 'tbsp' and cat_cfg.get('gram_per_tbsp'):
                default_weight = cat_cfg['gram_per_tbsp']
                return {"grams": float(default_weight), "portion_source": "default_tbsp", "calc": f"default {default_weight} g per tbsp", "category": cat_key}
            elif cat_cfg.get('default_unit') == 'tsp' and cat_cfg.get('gram_per_tsp'):
                default_weight = cat_cfg['gram_per_tsp']
                return {"grams": float(default_weight), "portion_source": "default_tsp", "calc": f"default {default_weight} g per tsp", "category": cat_key}
            elif cat_cfg.get('default_unit') == 'cup' and cat_cfg.get('gram_per_cup'):
                default_weight = cat_cfg['gram_per_cup']
                return {"grams": float(default_weight), "portion_source": "default_cup", "calc": f"default {default_weight} g per cup", "category": cat_key}
        
        return {"grams": 100.0, "portion_source": "default", "calc": "assumed 100 g", "category": cat_key}

    unit_l = _lower(unit)
    cat_key, cat_cfg = _match_category(name, rules or {})

    # 1) Category direct mappings
    if cat_cfg:
        # Allow default unit if unit missing
        use_unit = unit_l or _lower(cat_cfg.get('default_unit'))
        if use_unit in ('tbsp', 'tablespoon') and cat_cfg.get('gram_per_tbsp') is not None:
            grams = float(quantity) * float(cat_cfg['gram_per_tbsp'])
            return {"grams": grams, "portion_source": "rules_tbsp", "calc": f"{quantity} tbsp × {cat_cfg['gram_per_tbsp']} g/tbsp", "category": cat_key}
        if use_unit in ('tsp', 'teaspoon') and cat_cfg.get('gram_per_tsp') is not None:
            grams = float(quantity) * float(cat_cfg['gram_per_tsp'])
            return {"grams": grams, "portion_source": "rules_tsp", "calc": f"{quantity} tsp × {cat_cfg['gram_per_tsp']} g/tsp", "category": cat_key}
        if use_unit in ('cup',) and cat_cfg.get('gram_per_cup') is not None:
            grams = float(quantity) * float(cat_cfg['gram_per_cup'])
            return {"grams": grams, "portion_source": "rules_cup", "calc": f"{quantity} cup × {cat_cfg['gram_per_cup']} g/cup", "category": cat_key}
        if use_unit in ('each', 'st') and cat_cfg.get('grams_per_each') is not None:
            grams = float(quantity) * float(cat_cfg['grams_per_each'])
            return {"grams": grams, "portion_source": "rules_each", "calc": f"{quantity} each × {cat_cfg['grams_per_each']} g/each", "category": cat_key}

    # 1.5) Handle new vegetable/fruit categories with default weights
    if cat_cfg and cat_cfg.get('category') in ['vegetables', 'fruit', 'produce']:
        # Default weights for common produce items
        default_weights = {
            # Vegetables - each
            'vegetables_alliums': 130,      # onion, garlic
            'vegetables_roots_tubers': 120, # carrot, potato
            'vegetables_nightshades': 150,  # tomato, bell pepper
            'vegetables_cucurbits': 200,    # cucumber, zucchini
            'vegetables_leafy_greens': 30,  # lettuce, spinach (per cup)
            'vegetables_legumes': 100,      # peas, green beans
            'vegetables_corn': 150,         # corn
            'vegetables_mushrooms': 50,     # mushrooms
            'vegetables_aromatics': 100,    # celery, asparagus
            'vegetables_olives_capers': 10, # olives, capers
            # Fruits - each
            'fruit_citrus': 130,            # orange, lemon
            'fruit_berries': 5,             # berries (per piece)
            'fruit_pomes_stone_tropical': 150, # apple, banana
            'fruit_dried': 5,               # raisins, dried fruit
        }
        
        # Use default weight for the category
        if cat_key in default_weights:
            default_weight = default_weights[cat_key]
            if use_unit in ('each', 'st', None):
                grams = float(quantity) * default_weight
                return {"grams": grams, "portion_source": "rules_produce", "calc": f"{quantity} each × {default_weight} g/each", "category": cat_key}
            elif use_unit in ('cup',):
                # For leafy greens and other cup-based items
                grams = float(quantity) * default_weight
                return {"grams": grams, "portion_source": "rules_produce", "calc": f"{quantity} cup × {default_weight} g/cup", "category": cat_key}
            elif use_unit in ('tbsp',):
                # For small items like olives, capers
                grams = float(quantity) * default_weight
                return {"grams": grams, "portion_source": "rules_produce", "calc": f"{quantity} tbsp × {default_weight} g/tbsp", "category": cat_key}

    # 2) FDC portions
    fdc_portions = _extract_portions_from_fdc((fdc_food_json or {}).get('foodPortions') or (fdc_food_json or {}).get('householdPortions'))
    if fdc_portions:
        preferred = ["cup", "tbsp", "tsp", "tablespoon", "teaspoon"]
        for p in fdc_portions:
            ht = (p.get('householdText') or '').lower()
            gw = p.get('gramWeight')
            if not ht or gw is None:
                continue
            if any(k in ht for k in preferred) and unit_l in ht:
                grams = float(gw) * float(quantity)
                return {"grams": grams, "portion_source": "fdc_portion", "calc": f"{quantity} × {gw} g/{unit_l}", "category": cat_key}

    # 3) Density fallback (category density if provided)
    density = None
    if cat_cfg and cat_cfg.get('density_g_per_ml') is not None:
        density = float(cat_cfg['density_g_per_ml'])
    elif rules and rules.get('policy', {}).get('density_g_per_ml') is not None:
        density = float(rules['policy']['density_g_per_ml'])
    if density and unit_l in ML_CONST:
        ml = ML_CONST[unit_l] * float(quantity)
        grams = ml * float(density)
        return {"grams": grams, "portion_source": "density", "calc": f"{quantity} {unit_l} × {ML_CONST[unit_l]} ml/{unit_l} × {density} g/ml", "category": cat_key}

    # 4) Spice default (if category is spices)
    if cat_key and cat_key.startswith('spices'):
        default_g = ((rules or {}).get('policy', {}) or {}).get('spice_default_grams', 1.5)
        return {"grams": float(default_g), "portion_source": "default_spice", "calc": f"spice default {default_g} g", "category": cat_key}

    # 5) Fallback
    return {"grams": 100.0, "portion_source": "default", "calc": "assumed 100 g", "category": cat_key}


