import os
import csv
import json
import time
import logging
from typing import Any, Dict, List, Optional
import httpx
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.database import db
from tools.match_utils import normalize, singularize, best_match
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FDC_BASE = "https://api.nal.usda.gov/fdc/v1"


async def fetch_fdc_pages(dataTypes: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    api_key = os.getenv("FDC_API_KEY", "DEMO_KEY")
    page = 1
    results: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            params = {
                "api_key": api_key,
                "dataType": dataTypes,
                "pageNumber": page,
                "pageSize": 200,
            }
            r = await client.get(f"{FDC_BASE}/foods/list", params=params)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            results.extend(batch)
            logger.info(f"FDC page {page} -> {len(batch)} items (total {len(results)})")
            if limit and len(results) >= limit:
                results = results[:limit]
                break
            page += 1
            # small polite delay
            import asyncio
            await asyncio.sleep(0.2)
    return results


def upsert_canonical(records: List[Dict[str, Any]], dry_run: bool = False) -> int:
    inserted = 0
    with db.get_connection() as conn:
        c = conn.cursor()
        for rec in records:
            name_en = rec.get("description") or rec.get("lowercaseDescription") or ""
            if not name_en:
                continue
            name_en = name_en.strip()
            fdc_id = str(rec.get("fdcId")) if rec.get("fdcId") else None
            category = rec.get("dataType") or rec.get("foodCategory") or None
            synonyms = []
            if rec.get("foodAttributes"):
                try:
                    for attr in rec["foodAttributes"]:
                        if attr.get("name") == "synonyms":
                            synonyms.extend([v.get("value") for v in attr.get("values", []) if v.get("value")])
                except Exception:
                    pass
            if dry_run:
                continue
            c.execute(
                "INSERT OR IGNORE INTO canonical_ingredients (name_en, fdc_id, category, synonyms) VALUES (?, ?, ?, ?)",
                (name_en, fdc_id, category, json.dumps(list(set(synonyms))))
            )
            if c.rowcount:
                inserted += 1
        conn.commit()
    return inserted


async def fetch_off_sv(limit: Optional[int] = None) -> List[str]:
    import asyncio
    import pathlib
    import time as _time
    urls = [
        "https://world.openfoodfacts.org/data/taxonomies/ingredients.json",
        "https://static.openfoodfacts.org/data/taxonomies/ingredients.json",
    ]
    cache_path = "/tmp/off_ingredients.json"
    # cache 24h
    if os.path.exists(cache_path) and (_time.time() - os.path.getmtime(cache_path) < 86400):
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
        except Exception:
            data = None
    else:
        data = None
    if data is None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in urls:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    data = r.json()
                    with open(cache_path, 'w') as f:
                        json.dump(data, f)
                    break
                except Exception as e:
                    logger.warning(f"OFF fetch failed from {url}: {e}")
                    await asyncio.sleep(0.5)
    if not isinstance(data, dict):
        logger.warning("OFF taxonomy not loaded; returning empty list")
        return []
    aliases: List[str] = []
    for key, node in data.items():
        try:
            names = []
            # name
            nm = node.get('name') or {}
            for lang_key in ('sv', 'sv:se'):
                if lang_key in nm:
                    v = nm[lang_key]
                    if isinstance(v, str):
                        names.append(v)
                    elif isinstance(v, list):
                        names.extend(v)
            # synonyms
            syns = node.get('synonyms') or {}
            for lang_key in ('sv', 'sv:se'):
                vals = syns.get(lang_key)
                if isinstance(vals, list):
                    names.extend(vals)
            for n in names:
                t = normalize(n)
                if len(t) < 2 or not re.search(r"[a-zåäö]", t):
                    continue
                aliases.append(t)
        except Exception:
            continue
        if limit and len(aliases) >= limit:
            break
    # Heuristic dedupe
    aliases = sorted(list({a for a in aliases}))
    return aliases[:limit] if limit else aliases


def build_aliases(off_items: List[str], canonical_index: List[str]) -> List[tuple]:
    rows: List[tuple] = []
    # Heuristic pre-mapping
    heur = {
        "gräddfil": "sour cream",
        "salladslök": "scallion",
        "ljus soja": "light soy sauce",
        "soja": "soy sauce",
        "sojasås": "soy sauce",
        "idealmakaroner": "elbow macaroni",
        "vegansk ost": "vegan cheese",
        "vegokorv": "meatless sausage",
        "veganska korvar": "meatless sausage",
        "svartpeppar": "black pepper",
        "peppar": "black pepper",
    }
    for alias in off_items:
        ali = normalize(alias)
        target = heur.get(ali)
        conf = 0.95 if target else 0.0
        notes = None
        if not target:
            # fuzzy
            candidates = canonical_index
            best, score = best_match(ali, candidates)
            target = best
            conf = score
        rows.append((ali, 'sv', target, conf, notes))
    return rows


def upsert_aliases(rows: List[tuple], dry_run: bool = False) -> dict:
    stats = {"inserted": 0, "needs_review": 0}
    needs: List[list] = []
    with db.get_connection() as conn:
        c = conn.cursor()
        # build index of canonical names → id
        c.execute("SELECT id, name_en FROM canonical_ingredients")
        canon = c.fetchall()
        name_to_id = {normalize(r[1]): r[0] for r in canon}
        for alias_text, lang, canon_name, conf, notes in rows:
            canon_id = name_to_id.get(normalize(canon_name))
            if not canon_id:
                needs.append([alias_text, lang, canon_name, conf, notes or "no canonical id"])
                stats["needs_review"] += 1
                continue
            # thresholds: insert >=0.90, 0.85-<0.90 needs_review
            if conf < 0.85:
                continue
            if 0.85 <= conf < 0.90:
                needs.append([alias_text, lang, canon_name, conf, notes or "low confidence"])
                stats["needs_review"] += 1
                continue
            if dry_run:
                continue
            c.execute(
                "INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence, notes) VALUES (?, ?, ?, ?, ?)",
                (alias_text, lang, canon_id, conf, notes)
            )
            if c.rowcount:
                stats["inserted"] += 1
        conn.commit()
    if needs:
        os.makedirs("tmp", exist_ok=True)
        with open("tmp/needs_review.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["alias_text", "lang", "matched_canonical", "confidence", "notes"])
            writer.writerows(needs)
    return stats


def list_canonical_names() -> List[str]:
    with db.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT name_en FROM canonical_ingredients")
        return [r[0] for r in c.fetchall()]


def main():
    import argparse
    import asyncio
    load_dotenv(override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--fdc-import", action="store_true")
    parser.add_argument("--off-import", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.fdc_import:
        async def do_fdc():
            recs = await fetch_fdc_pages(["Foundation","SR Legacy","Survey","Branded"], args.limit)
            inserted = upsert_canonical(recs, dry_run=args.dry_run)
            logger.info(f"FDC import: inserted={inserted} total_records={len(recs)} dry_run={args.dry_run}")
        asyncio.run(do_fdc())

    if args.off_import:
        async def do_off():
            off_items = await fetch_off_sv(args.limit)
            canon_names = list_canonical_names()
            rows = build_aliases(off_items, canon_names)
            stats = upsert_aliases(rows, dry_run=args.dry_run)
            logger.info(f"OFF import: inserted={stats['inserted']} needs_review={stats['needs_review']} dry_run={args.dry_run}")
        asyncio.run(do_off())


if __name__ == "__main__":
    main()


