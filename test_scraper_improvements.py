#!/usr/bin/env python3
"""
Test script to verify the web scraper improvements work correctly
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from logic.web_scraper_new import FlexibleWebCrawler

async def test_scraper_improvements():
    """Test the improved web scraper with various Swedish recipe sites"""
    
    print("Testing web scraper improvements...")
    
    crawler = FlexibleWebCrawler()
    
    # Test URLs that previously failed
    test_urls = [
        "https://www.56kilo.se/lax-i-ugn-med-kramig-citron-och-ostsas/",
        "https://www.arla.se/recept/smalandska-kroppkakor/",
        "https://svensktkott.se/recept/kokta-grisftter/",
        "https://www.arla.se/recept/abborre-med-pepparrotspotatis/",
        "https://www.ica.se/recept/klassisk-kalops-632631/"  # This one should work
    ]
    
    for url in test_urls:
        print(f"\n--- Testing: {url} ---")
        
        try:
            # First try quick extraction
            html = await crawler._fetch_html_simple(url)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            result = await crawler._extract_quick_sources(soup, url)
            
            if result:
                print(f"✅ SUCCESS: Extracted recipe from {url}")
                print(f"   Title: {result.get('title', 'No title')}")
                print(f"   Ingredients: {len(result.get('ingredients', []))} items")
                print(f"   Instructions: {len(result.get('instructions', []))} steps")
                
                # Validate it looks like a Swedish recipe
                is_valid = crawler._validate_swedish_recipe(result)
                print(f"   Valid Swedish recipe: {is_valid}")
                
            else:
                print(f"❌ Quick extraction failed for {url}")
                # Try AI fallback
                print("   Trying AI fallback...")
                content_text = crawler.content_extractor.find_main_content(soup).get_text(strip=True)
                if len(content_text) > 100:
                    print(f"   Content length: {len(content_text)} chars")
                    # Check if content looks like a recipe
                    looks_like_recipe = crawler._looks_like_recipe(content_text)
                    print(f"   Looks like recipe: {looks_like_recipe}")
                else:
                    print("   Not enough content for AI analysis")
                    
        except Exception as e:
            print(f"❌ Error testing {url}: {e}")
    
    print("\n--- Testing content validation ---")
    
    # Test validation with different content types
    test_cases = [
        {
            "title": "Pannkakor",
            "ingredients": ["2 dl vetemjöl", "2 ägg", "3 dl mjölk"],
            "instructions": ["Blanda alla ingredienser", "Stek i panna"],
            "description": "Goda svenska pannkakor"
        },
        {
            "title": "Website Footer",
            "ingredients": [],
            "instructions": [],
            "description": "Kokaihop är Sverige största community"
        },
        {
            "title": "Navigation",
            "ingredients": ["Home", "About", "Contact"],
            "instructions": ["Click here", "Scroll down"],
            "description": "Site navigation menu"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        is_valid = crawler._validate_swedish_recipe(test_case)
        print(f"Test case {i+1}: {is_valid} - {test_case['title']}")

if __name__ == "__main__":
    asyncio.run(test_scraper_improvements())
