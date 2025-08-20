import hashlib
import json
import logging
from typing import Optional, Tuple, Dict, Any, List
import os
import httpx
from core.database import db

logger = logging.getLogger(__name__)


def _hash_key(name_raw: str, lang: str) -> str:
    return hashlib.sha256(f"{lang}::{name_raw.strip().lower()}".encode("utf-8")).hexdigest()


# Confidence thresholds
CONF_THRESH = {
    "SAFE": 0.95,
    "OK": 0.88,
    "LOW": 0.75,
}

def classify_confidence(c: float) -> str:
    if c >= CONF_THRESH["SAFE"]:
        return "SAFE"
    if c >= CONF_THRESH["OK"]:
        return "OK"
    if c >= CONF_THRESH["LOW"]:
        return "LOW"
    return "NOMATCH"


def _append_needs_review(row: Dict[str, Any]):
    try:
        import os, csv, time
        os.makedirs("tmp", exist_ok=True)
        path = "tmp/needs_review.csv"
        write_header = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["timestamp","raw","parsed_name","name_en","canonical_id","confidence","class","source","notes"])
            w.writerow([
                int(time.time()),
                row.get("raw"),
                row.get("parsed_name"),
                row.get("name_en"),
                row.get("canonical_id"),
                row.get("confidence"),
                row.get("class"),
                row.get("source"),
                row.get("notes"),
            ])
    except Exception as e:
        logger.warning(f"needs_review append failed: {e}")


def _lookup_canonical_id(name_en: str) -> Optional[int]:
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM canonical_ingredients WHERE LOWER(name_en)=LOWER(?)", (name_en,))
            row = c.fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning(f"canonical lookup failed: {e}")
        return None


GLOSSARY = {
    "soja": "soy sauce",
    "ljus soja": "light soy sauce",
    "mörk soja": "dark soy sauce",
    "matlagningsgrädde": "cooking cream",
    "gräddfil": "sour cream",
    "salladslök": "scallion",
    "idealmakaroner": "elbow macaroni",
    "gammaldags idealmakaroner": "elbow macaroni",
    "rökt tofu": "smoked tofu",
    "vegansk ost": "vegan cheese",
    "veganska korvar": "vegan sausage",
    "svartpeppar": "black pepper",
    "peppar": "black pepper",
    "sojamjölk": "soy milk",
    "linfrö": "flaxseed",
    "linfröägg": "flaxseed",
    "vatten": "water",
    "kranvatten": "tap water",
    "salt": "salt",
}


def try_lexicon(name_raw: str, lang: str) -> Optional[Tuple[str, float, Optional[int], str]]:
    key = name_raw.strip().lower()
    if key in GLOSSARY:
        name_en = GLOSSARY[key]
        return name_en, 0.98, _lookup_canonical_id(name_en), "glossary"
    # DB-backed aliases
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT ci.name_en, ci.id, ia.confidence FROM ingredient_aliases ia JOIN canonical_ingredients ci ON ci.id = ia.canonical_ingredient_id "
                "WHERE LOWER(ia.alias_text) = LOWER(?) AND ia.lang = ? ORDER BY ia.confidence DESC LIMIT 1",
                (key, lang.lower()),
            )
            row = c.fetchone()
            if row and row[0]:
                return row[0], float(row[2] or 0.95), int(row[1]), "alias"
    except Exception as e:
        logger.warning(f"try_lexicon DB lookup failed: {e}")
    return None


def try_rules(name_raw: str, lang: str) -> Optional[Tuple[str, float, Optional[int], str]]:
    text = name_raw.strip().lower()
    if lang.lower() == "sv":
        # Normalise brand/marketing terms
        replacements = {
            "gammaldags ": "",
            "old style ": "",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        # Specific composites
        if text in ("ljus soja", "ljus sojasås", "soja ljus"):
            return "light soy sauce", 0.9, _lookup_canonical_id("light soy sauce"), "rule"
        if text in ("soja", "sojasås"):
            return "soy sauce", 0.9, _lookup_canonical_id("soy sauce"), "rule"
        if text.startswith("vitlöksklyft"):
            return "garlic", 0.9, _lookup_canonical_id("garlic"), "rule"
        if text.startswith("krossade tomater"):
            return "crushed tomatoes", 0.95, _lookup_canonical_id("crushed tomatoes"), "rule"
        if text == "idealmakaroner":
            return "elbow macaroni", 0.95, _lookup_canonical_id("elbow macaroni"), "rule"
        if text == "rökt tofu":
            return "smoked tofu", 0.95, _lookup_canonical_id("smoked tofu"), "rule"
        if text in ("veganska korvar", "vegokorv", "vegansk korv"):
            return "meatless sausage", 0.93, _lookup_canonical_id("meatless sausage"), "rule"
        if text == "sojamjölk":
            return "soy milk", 0.95, _lookup_canonical_id("soy milk"), "rule"
        if text == "vegansk ost":
            return "vegan cheese", 0.95, _lookup_canonical_id("vegan cheese"), "rule"
        if text in ("svartpeppar", "peppar"):
            return "black pepper", 0.95, _lookup_canonical_id("black pepper"), "rule"
        if text == "vatten":
            return "water", 1.0, _lookup_canonical_id("water"), "rule"
    return None


def try_mt(name_raw: str, lang: str) -> Optional[Tuple[str, float, Optional[int], str]]:
    # Placeholder for MT; return None to avoid remote calls for now.
    return None


def _deepseek_fallback_normalize(name_raw: str, lang: str, quantity: Optional[float] = None, unit: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            return None
        qty_part = f" | qty={quantity}" if quantity is not None else ""
        unit_part = f" {unit}" if unit else ""
        system = "You normalize food ingredient names for a nutrition database. Reply ONLY with the canonical English ingredient name."
        user = (
            "Normalize this ingredient to a canonical English ingredient name suitable for USDA/FDC matching. "
            f"Input: '{name_raw}{unit_part}{qty_part}'. Reply ONLY with the canonical English ingredient name."
        )
        timeout = httpx.Timeout(12.0, connect=5.0, read=12.0)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        resp = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        out = resp.json()
        content = ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        name_en = content.strip().split("\n")[0][:128]
        if not name_en:
            return None
        canon = db.get_or_create_canonical(name_en)
        if canon:
            # persist alias for next time
            try:
                db.upsert_alias(name_raw.strip().lower(), lang.strip().lower(), canon, 0.8, "deepseek")
            except Exception:
                pass
        # log
        try:
            os.makedirs('tmp', exist_ok=True)
            with open('tmp/deepseek_fallback.log', 'a') as f:
                f.write(f"{name_raw}\t{lang}\t{quantity or ''}\t{unit or ''}\t{name_en}\t{canon or ''}\n")
        except Exception:
            pass
        return {"name_en": name_en, "canonical_id": canon, "confidence": 0.8, "class": classify_confidence(0.8), "source": "deepseek", "notes": None}
    except Exception as e:
        logger.warning(f"deepseek_fallback_normalize failed: {e}")
        return None


def translate_ingredient_name(name_raw: str, lang: str, parsed_name: Optional[str] = None, quantity: Optional[float] = None, unit: Optional[str] = None) -> Dict[str, Any]:
    # cache lookup
    key = _hash_key(name_raw, lang)
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT name_en, source, confidence FROM translation_cache WHERE key_hash = ? LIMIT 1", (key,))
            row = c.fetchone()
            if row:
                conf = float(row[2] or 1.0)
                klass = classify_confidence(conf)
                return {"name_en": row[0], "canonical_id": _lookup_canonical_id(row[0]), "confidence": conf, "class": klass, "source": row[1], "notes": None}
    except Exception as e:
        logger.warning(f"translation_cache read failed: {e}")

    for source, fn in (("lexicon", try_lexicon), ("rule", try_rules), ("mt", try_mt)):
        result = fn(name_raw, lang)
        if result:
            name_en, conf, canon_id, src = result
            # write cache
            try:
                with db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO translation_cache (key_hash, name_raw, lang, name_en, source, confidence) VALUES (?, ?, ?, ?, ?, ?)", (key, name_raw, lang, name_en, src, conf))
                    conn.commit()
            except Exception as e:
                logger.warning(f"translation_cache write failed: {e}")
            klass = classify_confidence(conf)
            # auto alias persist for SAFE/OK when not from alias
            if klass in ("SAFE","OK") and src != "alias" and canon_id:
                try:
                    with db.get_connection() as conn:
                        c = conn.cursor()
                        c.execute("INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence, notes) VALUES (?, ?, ?, ?, ?)", (name_raw.strip().lower(), lang, canon_id, conf, src))
                        conn.commit()
                except Exception as e:
                    logger.warning(f"auto-alias persist failed: {e}")
            # If low confidence → try Deepseek fallback once
            if klass in ("LOW","NOMATCH"):
                ds = _deepseek_fallback_normalize(name_raw, lang, quantity=quantity, unit=unit)
                if ds:
                    # cache deepseek result
                    try:
                        with db.get_connection() as conn:
                            c = conn.cursor()
                            c.execute("INSERT OR REPLACE INTO translation_cache (key_hash, name_raw, lang, name_en, source, confidence) VALUES (?, ?, ?, ?, ?, ?)", (key, name_raw, lang, ds.get('name_en'), 'deepseek', ds.get('confidence')))
                            conn.commit()
                    except Exception as e:
                        logger.warning(f"translation_cache write (deepseek) failed: {e}")
                    return ds
                # Else record needs_review and return low
                _append_needs_review({
                    "raw": name_raw,
                    "parsed_name": parsed_name or name_raw,
                    "name_en": name_en,
                    "canonical_id": canon_id,
                    "confidence": conf,
                    "class": klass,
                    "source": src,
                    "notes": None,
                })
            return {"name_en": name_en, "canonical_id": canon_id, "confidence": conf, "class": klass, "source": src, "notes": None}

    # Default: assume already English
    # Try Deepseek as final fallback
    ds = _deepseek_fallback_normalize(name_raw, lang, quantity=quantity, unit=unit)
    if ds:
        try:
            with db.get_connection() as conn:
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO translation_cache (key_hash, name_raw, lang, name_en, source, confidence) VALUES (?, ?, ?, ?, ?, ?)", (key, name_raw, lang, ds.get('name_en'), 'deepseek', ds.get('confidence')))
                conn.commit()
        except Exception as e:
            logger.warning(f"translation_cache write (deepseek end) failed: {e}")
        return ds
    # No deepseek available → record needs_review and return NOMATCH
    _append_needs_review({"raw": name_raw, "parsed_name": parsed_name or name_raw, "name_en": None, "canonical_id": None, "confidence": 0, "class": "NOMATCH", "source": 'none', "notes": None})
    return {"name_en": None, "canonical_id": None, "confidence": 0.0, "class": "NOMATCH", "source": "none", "notes": None}



def resolve(original_text: str, lang: str) -> Dict[str, Any]:
    """Resolve an ingredient string to canonical_ingredient_id with confidence and source.

    Steps:
      1) alias/lexicon
      2) fuzzy against canonical_ingredients.name_en
      3) DeepSeek fallback
    """
    text = (original_text or '').strip()
    # 1) Lexicon / alias
    lex = try_lexicon(text, lang)
    if lex:
        name_en, conf, canon_id, src = lex
        if conf >= 0.90 and canon_id:
            return {"canonical_ingredient_id": canon_id, "confidence": conf, "source": "alias"}

    # 2) Fuzzy against canonical
    try:
        rows = db.get_all_canonical()
        candidates = [(r["id"], r["name_en"]) for r in rows]
        # naive best match
        from tools.match_utils import best_match
        best_name, score = best_match(text, [n for _, n in candidates])
        if score >= 0.85:
            matched = next((cid for cid, nm in candidates if nm == best_name), None)
            if matched:
                return {"canonical_ingredient_id": matched, "confidence": score, "source": "fuzzy"}
    except Exception as e:
        logger.warning(f"resolve fuzzy failed: {e}")

    # 3) DeepSeek fallback
    try:
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if api_key:
            system = "Map the ingredient to a canonical English ingredient name (nutrition DB ready). Reply ONLY with the canonical English name."
            user = f"Map the ingredient '{text}' to a canonical English food ingredient name suitable for nutrition databases. Reply ONLY with the canonical English ingredient name."
            timeout = httpx.Timeout(10.0, connect=5.0, read=10.0)
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            resp = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            out = resp.json()
            content = ((out.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            name_en = content.strip().split("\n")[0][:128]
            canon = db.get_or_create_canonical(name_en)
            if canon:
                # create alias for next time at 0.8
                db.upsert_alias(text.lower(), lang, canon, 0.8, "deepseek")
                return {"canonical_ingredient_id": canon, "confidence": 0.8, "source": "deepseek"}
    except Exception as e:
        logger.warning(f"deepseek resolve failed: {e}")

    # below 0.75 → needs review
    _append_needs_review({
        "raw": text,
        "parsed_name": text,
        "name_en": None,
        "canonical_id": None,
        "confidence": 0.0,
        "class": "NOMATCH",
        "source": "resolve",
        "notes": None,
    })
    return {"canonical_ingredient_id": None, "confidence": 0.0, "source": "resolve"}


def translate_canonical(canonical_id: int, target_lang: str) -> Dict[str, Any]:
    """Return translated text for a canonical ingredient, using alias → DeepSeek → cache persist."""
    lang = target_lang.strip().lower()
    # 1) Already translated?
    existing = db.get_translation_for(canonical_id, lang)
    if existing:
        return {"translated_text": existing, "source": "cache", "confidence": 0.99}
    # 2) Alias as translation
    alias = db.get_alias_for_canonical(canonical_id, lang)
    if alias:
        db.upsert_translation(canonical_id, lang, alias[0], source='alias', confidence=alias[1])
        return {"translated_text": alias[0], "source": "alias", "confidence": alias[1]}
    # 3) DeepSeek fallback
    try:
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            return {"translated_text": None, "source": "none", "confidence": 0.0}
        name_en = db.get_canonical_name(canonical_id) or ''
        system = "Translate the ingredient name into the requested language. Reply ONLY with the translated ingredient name."
        user = f"Translate this ingredient name from English to {lang}, keep it short, food-specific: {name_en}"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        timeout = httpx.Timeout(12.0, connect=5.0, read=12.0)
        r = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        out = r.json()
        text = (((out.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip().split('\n')[0][:128]
        if text:
            # persist
            db.upsert_translation(canonical_id, lang, text, source='deepseek', confidence=0.9)
            # log
            try:
                os.makedirs('tmp', exist_ok=True)
                with open('tmp/deepseek_translations.log', 'a') as f:
                    f.write(f"{canonical_id}\t{lang}\t{name_en}\t{text}\n")
            except Exception:
                pass
            return {"translated_text": text, "source": "deepseek", "confidence": 0.9}
    except Exception as e:
        logger.warning(f"translate_canonical deepseek failed: {e}")
    return {"translated_text": None, "source": "none", "confidence": 0.0}

