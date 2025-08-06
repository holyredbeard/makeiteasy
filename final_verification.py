import asyncio
import json
from logic.web_scraper import scrape_recipe_from_url

def verify_scraper():
    """
    This script will test the web scraper functionality by fetching a recipe 
    from a hardcoded URL and printing the structured JSON result.
    This helps to verify that the data extraction for all required fields 
    (title, description, image, times, nutrition, etc.) works as expected 
    before running the full application.
    """
    test_url = "https://www.ica.se/recept/kramig-kycklinggryta-med-soltorkade-tomater-729340/"
    
    print(f"--- Starting Scraper Verification ---")
    print(f"Testing with URL: {test_url}")
    
    try:
        recipe_data = scrape_recipe_from_url(test_url, download_image=False)
        
        if recipe_data:
            print("\n--- SCRAPER RESULT (Structured JSON) ---")
            # Use json.dumps for pretty printing the dictionary
            print(json.dumps(recipe_data, indent=2, ensure_ascii=False))
            print("\n--- VERIFICATION CHECKLIST ---")
            
            checks = {
                "Title": "title" in recipe_data and recipe_data["title"],
                "Description": "description" in recipe_data and recipe_data["description"],
                "Image URL": "image_url" in recipe_data and recipe_data["image_url"],
                "Ingredients": "ingredients" in recipe_data and len(recipe_data["ingredients"]) > 0,
                "Instructions": "instructions" in recipe_data and len(recipe_data["instructions"]) > 0,
                "Servings": "servings" in recipe_data and recipe_data["servings"],
                "Prep Time": "prep_time" in recipe_data and recipe_data["prep_time"],
                "Cook Time": "cook_time" in recipe_data and recipe_data["cook_time"],
                "Nutritional Info": "nutritional_information" in recipe_data and recipe_data["nutritional_information"],
                "  - Calories": "nutritional_information" in recipe_data and "calories" in recipe_data.get("nutritional_information", {}),
                "  - Protein": "nutritional_information" in recipe_data and "proteinContent" in recipe_data.get("nutritional_information", {}),
                "  - Fat": "nutritional_information" in recipe_data and "fatContent" in recipe_data.get("nutritional_information", {}),
                "  - Carbs": "nutritional_information" in recipe_data and "carbohydrateContent" in recipe_data.get("nutritional_information", {}),
            }
            
            all_passed = True
            for name, passed in checks.items():
                status = "✅ PASSED" if passed else "❌ FAILED"
                if not passed:
                    all_passed = False
                print(f"{name.ljust(20)}: {status}")
                
            print("\n--- VERIFICATION SUMMARY ---")
            if all_passed:
                print("✅ All fields extracted successfully.")
            else:
                print("❌ Some fields failed extraction. Review the JSON output above.")
        else:
            print("\n--- SCRAPER RESULT ---")
            print("❌ FAILED: Scraper returned no data.")

    except Exception as e:
        print(f"\n--- An error occurred during verification ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_scraper()
