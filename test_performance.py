#!/usr/bin/env python3
"""
Test script to measure scraping performance with timing diagnostics
"""
import asyncio
import sys
import os
import time

# Add the current directory to the path to import the scraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable debug mode
os.environ['SCRAPER_DEBUG'] = '1'

# Configure logging to see debug output
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from logic.web_scraper_working import SimpleRecipeScraper

async def test_performance():
    """Test scraping performance with timing"""
    urls = [
        "https://www.ica.se/recept/hamburgare-712808/",
        "https://www.kokaihop.se/recept/fyllda-agghalvor-med-rom-creme-fraiche-rodlok-mm",
        "https://www.ica.se/recept/pannkakor-713489/",
        "https://www.kokaihop.se/recept/klassiska-kottbullar",
        # Add more URLs if needed for testing
    ]
    
    scraper = SimpleRecipeScraper()
    
    for url in urls:
        print(f"\n=== Testing URL: {url} ===")
        start_time = time.time()
        
        try:
            recipe = await scraper.scrape_recipe(url)
            total_time = time.time() - start_time
            print(f"Total time: {total_time:.2f}s")
            print(f"Title: {recipe.get('title', 'N/A')}")
            print(f"Source: {recipe.get('source', 'N/A')}")
            print(f"Ingredients count: {len(recipe.get('ingredients', []))}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_performance())