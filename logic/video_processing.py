import os
import subprocess
import yt_dlp
import whisper
import torch
import traceback
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageEnhance
from transformers import CLIPProcessor, CLIPModel
from models.types import Step
import threading
import logging
import numpy as np
import cv2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('output/video_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
DOWNLOADS_DIR = Path("downloads")
FRAMES_DIR = Path("frames")
DOWNLOADS_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)

def log_video_step(step: str, message: str, error: bool = False):
    """Helper function for consistent video processing logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_message = f"[VIDEO {timestamp}] [{step}] {message}"
    if error:
        logger.error(log_message)
    else:
        logger.info(log_message)

class ModelManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
                    cls._instance.clip_model = None
                    cls._instance.clip_processor = None
                    cls._instance.whisper_model = None
                    cls._instance._initialized = False
        return cls._instance

    def _initialize_whisper(self) -> None:
        """Initialize Whisper model if not already initialized."""
        if not self.whisper_model:
            with self._lock:
                if not self.whisper_model:
                    log_video_step("MODEL", "Initializing Whisper model (tiny)...")
                    self.whisper_model = whisper.load_model("tiny")
                    log_video_step("MODEL", "Whisper model loaded.")

    def _initialize_clip(self) -> None:
        """Initialize CLIP model if not already initialized."""
        if not self.clip_model or not self.clip_processor:
            with self._lock:
                if not self.clip_model or not self.clip_processor:
                    log_video_step("MODEL", "Initializing CLIP model...")
                    self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                    self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                    log_video_step("MODEL", "CLIP model loaded.")

    def get_whisper_model(self):
        """Get Whisper model, initializing if necessary."""
        self._initialize_whisper()
        return self.whisper_model

    def get_clip_models(self) -> Tuple[CLIPModel, CLIPProcessor]:
        """Get CLIP models, initializing if necessary."""
        self._initialize_clip()
        return self.clip_model, self.clip_processor

def download_video(youtube_url: str, job_id: str) -> str:
    """Download video with progress logging."""
    log_video_step("DOWNLOAD", f"Starting download for job {job_id}")
    output_path = DOWNLOADS_DIR / f"{job_id}.mp4"
    
    try:
        ydl_opts = {
            'format': '18',  # 360p mp4
            'outtmpl': str(output_path),
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        if output_path.exists() and output_path.stat().st_size > 0:
            log_video_step("DOWNLOAD", f"Successfully downloaded video: {output_path}")
            return str(output_path)
        else:
            raise Exception("Downloaded file is empty or does not exist")
            
    except Exception as e:
        log_video_step("DOWNLOAD", f"Error downloading video: {e}", error=True)
        raise

def transcribe_audio(video_path: str, job_id: Optional[str] = None) -> str:
    """Transcribe video audio with error handling."""
    log_video_step("TRANSCRIBE", f"Starting transcription for job {job_id}")
    
    try:
        model_manager = ModelManager()
        whisper_model = model_manager.get_whisper_model()
        result = whisper_model.transcribe(video_path)
        
        if result and 'text' in result:
            log_video_step("TRANSCRIBE", "Successfully transcribed audio")
            return result['text']
        else:
            raise Exception("Transcription result is empty or invalid")
            
    except Exception as e:
        log_video_step("TRANSCRIBE", f"Error transcribing audio: {e}", error=True)
        raise

def get_video_duration(video_path: str) -> Optional[float]:
    """Get video duration using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True
        )
        duration = float(result.stdout)
        log_video_step("DURATION", f"Video duration: {duration:.2f} seconds")
        return duration
    except Exception as e:
        log_video_step("DURATION", f"Error getting video duration: {e}", error=True)
        return None

def create_placeholder_image(output_path: str, step_number: int, error_message: str = "Image not available"):
    """Create a more informative placeholder image."""
    try:
        img = Image.new('RGB', (640, 360), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("Arial.ttf", 24)
            small_font = ImageFont.truetype("Arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw step number
        draw.text((10, 10), f"Step {step_number}", fill='black', font=font)
        
        # Draw error message
        draw.text((10, 50), error_message, fill='black', font=small_font)
        
        # Draw timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, 320), f"Generated: {timestamp}", fill='black', font=small_font)
        
        img.save(output_path, 'JPEG', quality=95)
        log_video_step("PLACEHOLDER", f"Created placeholder image for step {step_number}")
        
    except Exception as e:
        log_video_step("PLACEHOLDER", f"Error creating placeholder: {e}", error=True)
        # Create absolute minimum placeholder
        img = Image.new('RGB', (640, 360), color='lightgray')
        img.save(output_path, 'JPEG')

def analyze_frame_quality(image_path: str) -> float:
    """Analyze image quality with multiple metrics."""
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale for analysis
            gray = img.convert('L')
            
            # Calculate standard deviation (contrast)
            stat = ImageStat.Stat(gray)
            std_dev = stat.stddev[0]
            
            # Calculate brightness
            brightness = ImageStat.Stat(img).mean[0]
            
            # Calculate blur detection (Laplacian variance)
            img_array = np.array(gray)
            laplacian = cv2.Laplacian(img_array, cv2.CV_64F)
            blur_score = np.var(laplacian)
            
            # Normalize and combine scores
            std_dev_norm = min(std_dev / 50.0, 1.0)  # Normalize contrast
            brightness_norm = min(brightness / 128.0, 1.0)  # Normalize brightness
            blur_norm = min(blur_score / 500.0, 1.0)  # Normalize blur score
            
            # Weighted combination
            quality_score = (std_dev_norm * 0.4 + brightness_norm * 0.3 + blur_norm * 0.3)
            
            log_video_step("QUALITY", f"Image quality score: {quality_score:.2f}")
            return quality_score
            
    except Exception as e:
        log_video_step("QUALITY", f"Error analyzing frame quality: {e}", error=True)
        return 0.0

def enhance_image(image_path: str) -> bool:
    """Enhance image quality if needed."""
    try:
        with Image.open(image_path) as img:
            # Auto-enhance color
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.2)
            
            # Adjust contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.1)
            
            # Adjust brightness
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.1)
            
            # Save enhanced image
            img.save(image_path, 'JPEG', quality=95)
            log_video_step("ENHANCE", "Successfully enhanced image")
            return True
            
    except Exception as e:
        log_video_step("ENHANCE", f"Error enhancing image: {e}", error=True)
        return False

def extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame with multiple attempts."""
    try:
        # First attempt - exact timestamp
        cmd = ['ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path, '-vframes', '1', '-q:v', '2', str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            quality = analyze_frame_quality(str(output_path))
            if quality > 0.5:  # Good quality threshold
                enhance_image(str(output_path))
                return True
        
        # Second attempt - try 0.5 seconds before
        cmd = ['ffmpeg', '-y', '-ss', str(max(0, timestamp - 0.5)), '-i', video_path, '-vframes', '1', '-q:v', '2', str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            quality = analyze_frame_quality(str(output_path))
            if quality > 0.4:  # Lower threshold for second attempt
                enhance_image(str(output_path))
                return True
        
        # Third attempt - try 0.5 seconds after
        cmd = ['ffmpeg', '-y', '-ss', str(timestamp + 0.5), '-i', video_path, '-vframes', '1', '-q:v', '2', str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if output_path.exists() and output_path.stat().st_size > 1000:
            quality = analyze_frame_quality(str(output_path))
            if quality > 0.3:  # Even lower threshold for third attempt
                enhance_image(str(output_path))
                return True
        
        return False
        
    except Exception as e:
        log_video_step("EXTRACT", f"Error extracting frame: {e}", error=True)
        return False

def smart_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    """Smart frame selection with multiple fallback strategies."""
    log_video_step("FRAME", f"Starting frame selection for step {step.number}")
    
    final_path = FRAMES_DIR / f"{job_id}_{step.number}.jpg"
    step.image_path = str(final_path)

    try:
        if not video_duration:
            video_duration = get_video_duration(video_path) or 600

        cooking_start = video_duration * 0.1
        cooking_end = video_duration * 0.9
        
        # Strategy 1: Use AI-provided timestamp
        try:
            time_parts = list(map(int, step.timestamp.split(':')))
            ai_time = sum(p * 60**i for i, p in enumerate(reversed(time_parts)))
            if cooking_start <= ai_time <= cooking_end:
                log_video_step("FRAME", f"Trying AI timestamp: {ai_time}")
                if extract_frame(video_path, ai_time, final_path):
                    return True
        except (ValueError, AttributeError):
            pass

        # Strategy 2: Calculate based on step number
        step_interval = (cooking_end - cooking_start) / total_steps
        calculated_time = cooking_start + (step.number - 1) * step_interval
        log_video_step("FRAME", f"Trying calculated timestamp: {calculated_time}")
        if extract_frame(video_path, calculated_time, final_path):
            return True

        # Strategy 3: Try multiple points in the video
        test_points = [
            video_duration * 0.25,
            video_duration * 0.5,
            video_duration * 0.75
        ]
        
        for time in test_points:
            log_video_step("FRAME", f"Trying fallback timestamp: {time}")
            if extract_frame(video_path, time, final_path):
                return True

        # If all strategies fail, create an informative placeholder
        log_video_step("FRAME", "All frame extraction strategies failed, creating placeholder")
        create_placeholder_image(str(final_path), step.number, "Could not extract suitable frame")
        return False

    except Exception as e:
        log_video_step("FRAME", f"Error in frame selection: {e}", error=True)
        create_placeholder_image(str(final_path), step.number, f"Error: {str(e)}")
        return False 