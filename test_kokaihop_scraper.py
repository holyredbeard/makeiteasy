#!/usr/bin/env python3
"""
Test script to verify kokaihop.se scraping improvements
"""
import asyncio
import sys
import os

# Add the logic directory to the path so we can import the scraper
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'logic'))

from web_scraper_working import SimpleRecipeScraper

async def test_kokaihop_scraper():
    """Test the kokaihop.se scraper with the specific URL"""
    url = "https://www.kokaihop.se/recept/fyllda-agghalvor-med-rom-creme-fraiche-rodlok-mm"
    
    print(f"Testing kokaihop.se scraper with URL: {url}")
    print("=" * 80)
    
    scraper = SimpleRecipeScraper()
    
    try:
        recipe = await scraper.scrape_recipe(url)
        
        print(f"Title: {recipe.get('title', 'N/A')}")
        print(f"Source: {recipe.get('source', 'N/A')}")
        print("\nIngredients:")
        for i, ingredient in enumerate(recipe.get('ingredients', []), 1):
            print(f"  {i}. {ingredient}")
        
        print(f"\nNumber of ingredients found: {len(recipe.get('ingredients', []))}")
        
        # Check for the specific ingredients mentioned by the user
        expected_ingredients = ['ägg', 'rödlök', 'rom', 'crème fraiche', 'salt', 'dill', 'isbergssallad']
        found_ingredients = []
        
        for ingredient in recipe.get('ingredients', []):
            ingredient_name = ingredient.get('name', '').lower()
            for expected in expected_ingredients:
                if expected in ingredient_name:
                    found_ingredients.append(ingredient)
        
        print(f"\nFound expected ingredients: {len(found_ingredients)}/{len(expected_ingredients)}")
        for found in found_ingredients:
            print(f"  ✓ {found}")
        
        # Check if quantities are present
        ingredients_with_quantities = []
        for ingredient in recipe.get('ingredients', []):
            # Look for numbers or common units in the ingredient
            ingredient_str = f"{ingredient.get('quantity', '')} {ingredient.get('name', '')}".strip()
            if any(char.isdigit() for char in ingredient_str) or any(unit in ingredient_str.lower() for unit in ['st', 'g', 'dl', 'msk', 'tsk', 'krm']):
                ingredients_with_quantities.append(ingredient)
        
        print(f"\nIngredients with quantities: {len(ingredients_with_quantities)}/{len(recipe.get('ingredients', []))}")
        for ingredient in ingredients_with_quantities:
            print(f"  ✓ {ingredient}")
            
    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kokaihop_scraper())