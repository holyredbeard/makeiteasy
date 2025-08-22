#!/usr/bin/env python3
"""
Test script to scrape the pizza recipe from kokaihop.se and see what's happening with units.
"""
import asyncio
import sys
import os

# Add the logic directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'logic'))

from web_scraper_working import scrape_recipe_from_url

async def test_pizza_scraper():
    """Test the scraper with the pizza recipe URL"""
    url = "https://www.kokaihop.se/recept/pizza3"
    
    print(f"Testing scraper with URL: {url}")
    print("=" * 50)
    
    try:
        recipe = await scrape_recipe_from_url(url)
        
        print("Recipe extracted:")
        print(f"Title: {recipe.get('title')}")
        print(f"Source: {recipe.get('source')}")
        print(f"Servings: {recipe.get('servings')}")
        print()
        
        print("Ingredients:")
        for i, ingredient in enumerate(recipe.get('ingredients', []), 1):
            if isinstance(ingredient, dict):
                print(f"{i}. {ingredient.get('quantity', '')} {ingredient.get('name', '')}".strip())
            else:
                print(f"{i}. {ingredient}")
        print()
        
        print("Raw ingredients data:")
        for i, ingredient in enumerate(recipe.get('ingredients', []), 1):
            print(f"{i}. {ingredient}")
        print()
        
    except Exception as e:
        print(f"Error scraping recipe: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pizza_scraper())