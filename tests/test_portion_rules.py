import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from logic.rules_loader import load_portion_rules
from logic.portion_resolver import resolve_grams


def approx(a, b, tol=2.0):
    return abs(a - b) <= tol


def test_pecans_one_cup():
    rules = load_portion_rules()
    res = resolve_grams(1.0, 'cup', 'pecans', None, rules)
    assert approx(res['grams'], 99.0, tol=5.0)  # target ~99g, allow small tolerance


def test_butter_two_tbsp():
    rules = load_portion_rules()
    res = resolve_grams(2.0, 'tbsp', 'butter', None, rules)
    assert 28.0 <= res['grams'] <= 30.0


def test_brown_sugar_one_tbsp():
    rules = load_portion_rules()
    res = resolve_grams(1.0, 'tbsp', 'brown sugar', None, rules)
    assert 12.0 <= res['grams'] <= 13.0


def test_cinnamon_half_tsp():
    rules = load_portion_rules()
    res = resolve_grams(0.5, 'tsp', 'cinnamon', None, rules)
    assert 1.2 <= res['grams'] <= 1.3  # 0.5 tsp × 2.5 g/tsp = 1.25g


def test_pasta_one_point_five_liters_dry():
    rules = load_portion_rules()
    res = resolve_grams(1.5, 'l', 'pasta', None, rules)
    assert 500 <= res['grams'] <= 1100


def test_salt_quarter_tsp_sodium():
    rules = load_portion_rules()
    res = resolve_grams(0.25, 'tsp', 'salt', None, rules)
    grams = res['grams']
    # density policy says 1.2 g/ml, tsp=5ml → 0.25 tsp = 1.25 ml → ~1.5 g
    assert 1.3 <= grams <= 1.7
    sodium_fraction = rules['policy']['salt']['sodium_fraction']
    sodium_mg = grams * sodium_fraction * 1000.0
    assert 550 <= sodium_mg <= 650



