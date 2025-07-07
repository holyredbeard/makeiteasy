from models.types import VideoContent, Step
from logic.pdf_generator import generate_pdf
import uuid
from pathlib import Path

def create_test_video_content():
    return VideoContent(
        title="Test Recipe with Unicode Characters • ö ä å",
        description="This is a test recipe description with special characters: • ö ä å",
        materials_or_ingredients=[
            "• 2 cups flour",
            "• 1 tsp salt",
            "• 3 eggs",
            "• 250ml milk",
            "• Butter for frying",
            "• Sugar & cinnamon"
        ],
        steps=[
            Step(number=1, explanation="Mix flour and salt in a bowl"),
            Step(number=2, explanation="Add eggs and milk • whisk until smooth"),
            Step(number=3, explanation="Let rest for 30 minutes"),
            Step(number=4, explanation="Heat pan & add butter"),
            Step(number=5, explanation="Pour batter & cook until golden")
        ],
        servings="4",
        prep_time="15 minutes",
        cook_time="20 minutes"
    )

def test_pdf_generation():
    # Create test content
    video_content = create_test_video_content()
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Generate PDF
        pdf_path = generate_pdf(video_content, job_id)
        print(f"PDF generated successfully at: {pdf_path}")
        
        # Verify file exists and has content
        pdf_file = Path(pdf_path)
        if pdf_file.exists() and pdf_file.stat().st_size > 0:
            print(f"PDF file verified: {pdf_file.stat().st_size} bytes")
        else:
            print("Error: PDF file is missing or empty")
            
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")

if __name__ == "__main__":
    test_pdf_generation() 