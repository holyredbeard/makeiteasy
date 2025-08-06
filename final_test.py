import pytest
from fastapi.testclient import TestClient
import json
from main import app  # Import your FastAPI app

# Create a TestClient instance
client = TestClient(app)

def test_scrape_recipe_success():
    """
    Tests the /scrape-recipe endpoint with a known good URL.
    This simulates the exact request the frontend makes and verifies
    that the backend processes it without errors and returns a valid
    recipe structure.
    """
    test_url = "https://www.ica.se/recept/kramig-kycklinggryta-med-soltorkade-tomater-729340/"
    
    response = client.post(
        "/api/v1/scrape-recipe",
        json={"url": test_url}
    )
    
    # 1. Check for successful HTTP status code
    assert response.status_code == 200, f"Expected status 200, but got {response.status_code}. Response: {response.text}"
    
    # 2. Check that the response is valid JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        pytest.fail("Response is not valid JSON.")
        
    # 3. Check for the top-level 'recipe' key
    assert "recipe" in data, "The 'recipe' key is missing from the response."
    recipe = data["recipe"]
    
    # 4. Verify that the recipe contains all essential fields
    required_keys = [
        "title", "description", "ingredients", "instructions", 
        "image_url", "cook_time", "servings", "nutritional_information"
    ]
    for key in required_keys:
        assert key in recipe and recipe[key] is not None, f"Required key '{key}' is missing or null."
        
    # 5. Verify nutritional information structure
    assert isinstance(recipe["nutritional_information"], dict), "Nutritional information should be an object."
    
    print("\n--- Backend Test Passed ---")
    print(f"Title: {recipe['title']}")
    print(f"Image URL: {recipe['image_url']}")
    print("All required fields are present and valid.")
    print("--------------------------")

def test_scrape_recipe_failure_bad_url():
    """
    Tests the /scrape-recipe endpoint with a URL that is known to be difficult
    or impossible to scrape, ensuring it fails gracefully.
    """
    test_url = "https://www.instagram.com/p/C2xX8J5Lp8q/" # An instagram post
    
    response = client.post(
        "/api/v1/scrape-recipe",
        json={"url": test_url}
    )
    
    # Expecting a 422 or 500 series error, as the scraping should fail.
    # A 422 indicates a validation error (e.g., URL not scrapable)
    # A 500 indicates a server error during scraping. Both are acceptable failure modes.
    assert response.status_code >= 400, f"Expected a failure status code (>=400), but got {response.status_code}."
    
    data = response.json()
    assert "detail" in data, "Failure response should contain a 'detail' key."
    
    print("\n--- Backend Failure Test Passed ---")
    print(f"Received expected failure for URL: {test_url}")
    print(f"Detail: {data['detail']}")
    print("---------------------------------")

