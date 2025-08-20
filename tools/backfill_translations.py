#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.database import db
from logic.translator import translate_canonical


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--lang', required=True)
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    items = db.get_all_canonical()[: args.limit]
    total = 0
    for row in items:
        cid = row['id']
        name = row['name_en']
        res = translate_canonical(cid, args.lang)
        text = res.get('translated_text')
        print(f"{cid}\t{name}\t->\t{args.lang}:{text}\t({res.get('source')} {res.get('confidence')})")
        total += 1
    print(f"Done. Processed {total} items.")


if __name__ == '__main__':
    main()


