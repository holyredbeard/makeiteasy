import asyncio
import os
import logging
from api.routes import process_video_request
from models.types import VideoRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

async def main():
    """
    Runs a full end-to-end verification of the video processing pipeline.
    """
    log.info("--- Starting Final Verification ---")
    
    # 1. Define the test request
    # This URL is for a short, simple recipe video.
    test_request = VideoRequest(
        youtube_url="https://www.youtube.com/watch?v=FgYkBfV_adw",
        job_id="final_verification_test"
    )
    
    log.info(f"Test URL: {test_request.youtube_url}")
    log.info(f"Job ID: {test_request.job_id}")
    
    # 2. Clean up previous run files
    output_pdf = f"output/{test_request.job_id}.pdf"
    if os.path.exists(output_pdf):
        os.remove(output_pdf)
        log.info(f"Removed old PDF: {output_pdf}")
    
    # 3. Execute the main processing function
    try:
        log.info("Calling process_video_request...")
        pdf_path = await process_video_request(test_request)
        
        # 4. Verify the result
        if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
            log.info("--- ✅ VERIFICATION SUCCESS ---")
            log.info(f"PDF generated successfully at: {pdf_path}")
            log.info("The file is valid and not empty.")
        else:
            log.error("--- ❌ VERIFICATION FAILED ---")
            log.error("The process completed, but the final PDF was not created or is empty.")
            
    except Exception as e:
        log.error("--- ❌ VERIFICATION FAILED ---")
        log.error(f"An unexpected error occurred during the process: {e}", exc_info=True)

if __name__ == "__main__":
    # Ensure the output directory exists
    if not os.path.exists("output"):
        os.makedirs("output")
    
    asyncio.run(main())
