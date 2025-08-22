#!/usr/bin/env python3
"""
Test script to scrape the ICA.se hamburger recipe and debug ingredient parsing
"""
import asyncio
import sys
import os

# Add the current directory to the path to import the scraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logic.web_scraper_working import SimpleRecipeScraper

async def test_ica_scraping():
    """Test scraping the ICA hamburger recipe"""
    url = "https://www.ica.se/recept/hamburgare-712808/"
    
    scraper = SimpleRecipeScraper()
    print(f"Scraping URL: {url}")
    
    try:
        recipe = await scraper.scrape_recipe(url)
        print("\n=== SCRAPED RECIPE ===")
        print(f"Title: {recipe.get('title', 'N/A')}")
        print(f"Source: {recipe.get('source', 'N/A')}")
        print(f"Servings: {recipe.get('servings', 'N/A')}")
        
        print("\n=== INGREDIENTS ===")
        for i, ing in enumerate(recipe.get('ingredients', []), 1):
            if isinstance(ing, dict):
                print(f"{i}. {ing.get('quantity', '')} {ing.get('name', '')}".strip())
            else:
                print(f"{i}. {ing}")
        
        print("\n=== INSTRUCTIONS ===")
        for i, inst in enumerate(recipe.get('instructions', []), 1):
            if isinstance(inst, dict):
                print(f"{i}. {inst.get('description', '')}")
            else:
                print(f"{i}. {inst}")
                
    except Exception as e:
        print(f"Error scraping recipe: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ica_scraping())