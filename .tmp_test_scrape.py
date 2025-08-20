import asyncio, json
from logic.web_scraper_new import scrape_recipe_from_url


def fmt_ing(x):
    if isinstance(x, dict):
        q = x.get('quantity') or ''
        n = x.get('name') or ''
        notes = x.get('notes')
        s = (q + ' ' + n).strip()
        if notes:
            s += f' ({notes})'
        return s
    return str(x)


async def main():
    urls = [
        'https://www.ica.se/recept/pannkakor-grundsmet-2083/',
        'https://receptfavoriter.se/recept/crepes-smet-recept-pa-smet-till-crepes.html',
        'https://recept.se/recept/crepes-med-svampstuvning',
    ]
    for u in urls:
        try:
            d = await scrape_recipe_from_url(u)
            ings = d.get('ingredients') or []
            ing_disp = [fmt_ing(i) for i in ings]
            info = {
                'url': u,
                'title': d.get('title'),
                'servings': d.get('servings'),
                'times': {
                    'prep': d.get('prep_time_minutes'),
                    'cook': d.get('cook_time_minutes'),
                    'total': d.get('total_time_minutes')
                },
                'image_url': d.get('image_url'),
                'ingredients_count': len(ings),
                'first_5_ingredients': ing_disp[:5],
                'instructions_count': len(d.get('instructions') or []),
                'first_3_instructions': (d.get('instructions') or [])[:3]
            }
            print(json.dumps(info, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({'url': u, 'error': str(e)}))


if __name__ == '__main__':
    asyncio.run(main())
