import os
from pathlib import Path
from typing import Optional
import logging
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# --- Logging Configuration ---
def setup_logging():
    """
    Configures the root logger for the application.
    - Clears existing handlers to prevent duplicate logs on reload.
    - Adds a stream handler for console output.
    - Adds a file handler to write logs to 'app.log'.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicates during reloads
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create a formatter
    log_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add a handler to stream logs to the console
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    root_logger.addHandler(stream_handler)

    # Add a handler to write logs to a file for diagnostics
    file_handler = RotatingFileHandler("app.log", maxBytes=10*1024*1024, backupCount=3)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    
    logging.info("Logging re-configured to use console and app.log")


# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Directory for storing downloaded videos
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Directory for storing extracted video frames
FRAMES_DIR = BASE_DIR / "frames"
FRAMES_DIR.mkdir(exist_ok=True)

# Directory for storing generated PDF files
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory storage for job status and results
# TODO: Replace this with a more robust solution like Redis or a database
# for better scalability and persistence across server restarts.
jobs = {}

def update_status(job_id: str, step: str, status: str, message: str, pdf_path: Optional[str] = None):
    """
    Updates the status of a job, its specific step, and appends a log message
    for the frontend to display.
    """
    if job_id not in jobs:
        jobs[job_id] = {"status": "starting", "steps": {}, "logs": []}

    # Add a timestamped log for the frontend
    log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] [{step.upper()}] {message}"
    if "logs" not in jobs[job_id]:
        jobs[job_id]["logs"] = []
    jobs[job_id]["logs"].append(log_entry)
    
    # Update the overall job status if the step is 'overall'
    if step.lower() == "overall":
        jobs[job_id]["status"] = status
        jobs[job_id]["message"] = message
        if pdf_path:
            jobs[job_id]["pdf_path"] = pdf_path
    else:
        # Update the status of a specific step
        if "steps" not in jobs[job_id]:
            jobs[job_id]["steps"] = {}
        jobs[job_id]["steps"][step] = {"status": status, "message": message}

# Global variables for holding the CLIP model and processor
# This is a simple in-memory cache. For a multi-worker setup, this
# should be handled by a dedicated model serving solution.
CLIP_MODEL = None
CLIP_PROCESSOR = None

# TODO: Add API keys and other sensitive information here,
# preferably loaded from environment variables using a library like python-dotenv.
# Example: DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") 