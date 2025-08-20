#!/usr/bin/env python3
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
import argparse
import httpx
from core.database import db


def translate(name_en: str, lang: str) -> str | None:
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return None
    system = "Translate the ingredient name into the requested language. Reply ONLY with the translated ingredient name."
    user = f"Translate the ingredient '{name_en}' into {lang}. Return ONLY the translated ingredient name."
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    timeout = httpx.Timeout(15.0, connect=5.0, read=15.0)
    r = httpx.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (((data.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip().split('\n')[0][:128]


def main():
    parser = argparse.ArgumentParser(description='Seed ingredient translations using DeepSeek')
    parser.add_argument('--langs', type=str, default='sv,da', help='Comma-separated languages (e.g., sv,da,no,fi)')
    parser.add_argument('--limit', type=int, default=50, help='Limit number of canonical ingredients to process')
    args = parser.parse_args()

    langs = [l.strip().lower() for l in args.langs.split(',') if l.strip()]
    canon = db.get_all_canonical()[: args.limit]
    total_new = 0
    total_fail = 0

    for row in canon:
        cid = row['id']
        name_en = row['name_en']
        for lang in langs:
            try:
                translated = translate(name_en, lang)
                if translated:
                    db.upsert_translation(cid, lang, translated)
                    total_new += 1
                else:
                    total_fail += 1
            except Exception:
                total_fail += 1

    os.makedirs('tmp', exist_ok=True)
    with open('tmp/missing_translations.csv', 'a') as f:
        f.write(f"processed={len(canon)} langs={langs} new={total_new} failed={total_fail}\n")
    print(f"Seed done: new={total_new}, failed={total_fail}")


if __name__ == '__main__':
    main()


