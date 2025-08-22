#!/usr/bin/env python3
"""
Debug script to specifically test the kokaihop.se pizza recipe extraction
"""
import asyncio
import sys
import os
from playwright.async_api import async_playwright

# Add the logic directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'logic'))

from web_scraper_working import SimpleRecipeScraper

async def debug_kokaihop_extraction():
    """Debug the kokaihop.se extraction specifically"""
    url = "https://www.kokaihop.se/recept/pizza3"
    
    print(f"Debugging kokaihop.se extraction for: {url}")
    print("=" * 60)
    
    # Create scraper instance
    scraper = SimpleRecipeScraper()
    
    try:
        # Get HTML with Playwright to see the actual content
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print("Loading page with Playwright...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Get the rendered HTML
            html = await page.content()
            await browser.close()
            
            print(f"Got HTML ({len(html)} chars)")
            
            # Parse with BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try to extract JSON-LD data
            print("\n1. Checking for JSON-LD data...")
            scripts = soup.find_all('script', type='application/ld+json')
            for i, script in enumerate(scripts):
                try:
                    raw = script.string or script.get_text() or ''
                    if raw.strip():
                        data = json.loads(raw)
                        print(f"JSON-LD script {i}: {json.dumps(data, indent=2)[:500]}...")
                except Exception as e:
                    print(f"Error parsing JSON-LD {i}: {e}")
            
            # Try the kokaihop specific extraction
            print("\n2. Running kokaihop specific extraction...")
            ingredients = scraper._extract_kokaihop_ingredients(soup)
            print(f"Kokaihop ingredients: {ingredients}")
            
            # Also try general JSON-LD extraction
            print("\n3. Running general JSON-LD extraction...")
            recipe = scraper._extract_json_ld(soup)
            if recipe:
                print(f"JSON-LD recipe: {recipe.get('title')}")
                print(f"JSON-LD ingredients: {recipe.get('ingredients', [])}")
            else:
                print("No JSON-LD recipe found")
                
        except Exception as e:
            print(f"Playwright error: {e}")
            
    except Exception as e:
        print(f"General error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_kokaihop_extraction())