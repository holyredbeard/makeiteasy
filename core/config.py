import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('output/job_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
jobs: Dict[str, Dict[str, Any]] = {}

def cleanup_old_files(max_age_hours: int = 24):
    """Clean up old temporary files."""
    try:
        now = datetime.now()
        cutoff = now - timedelta(hours=max_age_hours)
        
        # Clean up downloads directory
        logger.info(f"Cleaning up files older than {max_age_hours} hours in downloads directory")
        for file in DOWNLOADS_DIR.glob("*"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    logger.info(f"Removing old download: {file}")
                    file.unlink()
        
        # Clean up frames directory
        logger.info(f"Cleaning up files older than {max_age_hours} hours in frames directory")
        for file in FRAMES_DIR.glob("*"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    logger.info(f"Removing old frame: {file}")
                    file.unlink()
        
        # Clean up output directory (keep PDFs for 7 days)
        pdf_cutoff = now - timedelta(days=7)
        logger.info("Cleaning up PDFs older than 7 days in output directory")
        for file in OUTPUT_DIR.glob("*.pdf"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < pdf_cutoff:
                    logger.info(f"Removing old PDF: {file}")
                    file.unlink()
        
        # Clean up job dictionary
        old_jobs = [job_id for job_id, job in jobs.items() 
                   if job.get("created_at") and 
                   datetime.fromisoformat(job["created_at"]) < cutoff]
        for job_id in old_jobs:
            logger.info(f"Removing old job from memory: {job_id}")
            del jobs[job_id]
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def cleanup_job_files(job_id: str):
    """Clean up all files associated with a specific job."""
    try:
        # Remove video file
        video_file = DOWNLOADS_DIR / f"{job_id}.mp4"
        if video_file.exists():
            logger.info(f"Removing video file: {video_file}")
            video_file.unlink()
        
        # Remove frame files
        frame_pattern = f"{job_id}_*.jpg"
        for frame in FRAMES_DIR.glob(frame_pattern):
            logger.info(f"Removing frame file: {frame}")
            frame.unlink()
            
    except Exception as e:
        logger.error(f"Error cleaning up job files for {job_id}: {e}")

def update_status(job_id: str, step: str, status: str, message: str, pdf_path: Optional[str] = None):
    """Updates the status of a job, its specific step, and appends a log message."""
    if job_id not in jobs:
        jobs[job_id] = {
            "status": "starting",
            "steps": {},
            "logs": [],
            "created_at": datetime.now().isoformat()
        }

    # Add a timestamped log
    log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] [{step.upper()}] {message}"
    if "logs" not in jobs[job_id]:
        jobs[job_id]["logs"] = []
    jobs[job_id]["logs"].append(log_entry)
    
    # Update overall job status
    if step.lower() == "overall":
        jobs[job_id]["status"] = status
        jobs[job_id]["message"] = message
        if pdf_path:
            jobs[job_id]["pdf_path"] = pdf_path
            
        # If job is completed or failed, clean up temporary files
        if status in ["completed", "failed"]:
            cleanup_job_files(job_id)
    else:
        # Update specific step status
        if "steps" not in jobs[job_id]:
            jobs[job_id]["steps"] = {}
        jobs[job_id]["steps"][step] = {"status": status, "message": message}

# Run cleanup every 24 hours
def schedule_cleanup():
    """Schedule periodic cleanup of old files."""
    import threading
    cleanup_old_files()
    cleanup_thread = threading.Timer(24 * 3600, schedule_cleanup)
    cleanup_thread.daemon = True
    cleanup_thread.start()

# Start the cleanup scheduler
schedule_cleanup()

# Global variables for holding the CLIP model and processor
# This is a simple in-memory cache. For a multi-worker setup, this
# should be handled by a dedicated model serving solution.
CLIP_MODEL = None
CLIP_PROCESSOR = None

# TODO: Add API keys and other sensitive information here,
# preferably loaded from environment variables using a library like python-dotenv.
# Example: DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") 