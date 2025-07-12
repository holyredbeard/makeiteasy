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
import pytesseract

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

def log_video_step(step_name: str, message: str, error: bool = False):
    """Unified logger for video processing steps."""
    if error:
        logger.error(f"[{step_name}] {message}")
    else:
        logger.info(f"[{step_name}] {message}")

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
        # Try multiple format options prioritizing smaller file sizes for faster downloads
        format_options = [
            'worst[height>=240][ext=mp4]', # Smallest quality MP4 (but at least 240p)
            'worst[ext=mp4]',              # Smallest available MP4
            '18',                          # 360p MP4 (fallback)
            '17',                          # 144p 3GP (very small)
            'worst',                       # Absolute smallest available
        ]
        
        for format_option in format_options:
            try:
                ydl_opts = {
                    'format': format_option,
                    'outtmpl': str(output_path),
                    'noplaylist': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                
                if output_path.exists() and output_path.stat().st_size > 0:
                    log_video_step("DOWNLOAD", f"Successfully downloaded video with format '{format_option}': {output_path}")
                    return str(output_path)
                    
            except Exception as format_error:
                log_video_step("DOWNLOAD", f"Format '{format_option}' failed: {format_error}")
                continue
        
        # If we get here, all formats failed
        raise Exception("All download format options failed")
            
    except Exception as e:
        log_video_step("DOWNLOAD", f"Error downloading video: {e}", error=True)
        raise

def transcribe_audio(video_path: str, job_id: Optional[str] = None) -> str:
    """Transcribe video audio with error handling."""
    log_video_step("TRANSCRIBE", f"Starting transcription for job {job_id}")
    
    try:
        model_manager = ModelManager()
        whisper_model = model_manager.get_whisper_model()
        
        # Try with different configurations to handle tensor size issues
        try:
            result = whisper_model.transcribe(video_path, fp16=False)
        except Exception as e1:
            log_video_step("TRANSCRIBE", f"First attempt failed: {e1}, trying with different settings")
            try:
                result = whisper_model.transcribe(video_path, fp16=False, language="en")
            except Exception as e2:
                log_video_step("TRANSCRIBE", f"Second attempt failed: {e2}, trying with minimal settings")
                result = whisper_model.transcribe(video_path, fp16=False, language="en", task="transcribe")
        
        if result and 'text' in result:
            log_video_step("TRANSCRIBE", "Successfully transcribed audio")
            return result['text']
        else:
            raise Exception("Transcription result is empty or invalid")
            
    except Exception as e:
        log_video_step("TRANSCRIBE", f"Error transcribing audio: {e}", error=True)
        raise

def get_video_duration(video_path: str) -> Optional[float]:
    """Get the duration of a video file using OpenCV."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log_video_step("DURATION", f"Cannot open video file: {video_path}", error=True)
            return None
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            log_video_step("DURATION", "FPS is zero, cannot calculate duration.", error=True)
            return None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        cap.release()
        log_video_step("DURATION", f"Video duration: {duration:.2f} seconds")
        return duration
    except Exception as e:
        log_video_step("DURATION", f"Failed to get video duration with OpenCV: {e}", error=True)
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

def extract_frame(video_path: str, time_in_seconds: float, output_path: str) -> bool:
    """Extract a single frame from a video at a specific time using OpenCV."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log_video_step("FRAME_EXTRACT", f"Cannot open video file: {video_path}", error=True)
            return False

        # Ensure time is within video bounds
        duration = get_video_duration(video_path)
        if duration and time_in_seconds > duration:
            time_in_seconds = duration - 0.1 # Get a frame just before the end
        if time_in_seconds < 0:
            time_in_seconds = 0
        
        cap.set(cv2.CAP_PROP_POS_MSEC, time_in_seconds * 1000)
        success, image = cap.read()
        cap.release()
        
        if success:
            log_video_step("FRAME_EXTRACT", f"Extracting frame at {time_in_seconds:.2f}s to {output_path}")
            cv2.imwrite(output_path, image)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                log_video_step("FRAME_EXTRACT", "Frame extracted successfully.")
                return True
            else:
                log_video_step("FRAME_EXTRACT", "Frame extraction failed (file is empty or invalid).", error=True)
                return False
        else:
            log_video_step("FRAME_EXTRACT", f"Failed to get frame at {time_in_seconds:.2f}s.", error=True)
            return False
    except Exception as e:
        log_video_step("FRAME_EXTRACT", f"Error during frame extraction with OpenCV: {e}", error=True)
        return False

def extract_thumbnail(video_path: str, job_id: str) -> Optional[str]:
    """
    Extracts a representative thumbnail from the video, preferably from the end.
    """
    output_path = str(FRAMES_DIR / f"{job_id}_thumbnail.jpg")
    duration = get_video_duration(video_path)
    
    if not duration:
        log_video_step("THUMBNAIL", "Could not get video duration, cannot extract thumbnail.", error=True)
        return None
        
    # Try to get a frame from 95% of the way through the video
    extraction_time = duration * 0.95
    log_video_step("THUMBNAIL", f"Attempting to extract thumbnail at {extraction_time:.2f}s (95% mark).")
    
    if extract_frame(video_path, extraction_time, output_path):
        return output_path
    
    # Fallback: try the 85% mark
    extraction_time = duration * 0.85
    log_video_step("THUMBNAIL", f"Fallback: Attempting to extract thumbnail at {extraction_time:.2f}s (85% mark).")
    if extract_frame(video_path, extraction_time, output_path):
        return output_path
        
    log_video_step("THUMBNAIL", "Failed to extract a thumbnail after multiple attempts.", error=True)
    return None

def smart_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    """
    Selects the best frame for a step using CLIP for relevance and quality metrics.
    """
    output_path = FRAMES_DIR / f"{job_id}_step_{step.step_number}.jpg"
    
    if not video_duration:
        video_duration = get_video_duration(video_path)
    
    if not video_duration:
        log_video_step("SMART_SELECT", f"Cannot determine video duration for step {step.step_number}", error=True)
        create_placeholder_image(str(output_path), step.step_number, "Video duration unknown")
        step.image_path = str(output_path)
        return False
        
    try:
        model_manager = ModelManager()
        clip_model, clip_processor = model_manager.get_clip_models()

        # Generate candidate frames
        num_frames_to_sample = 20  # Sample 20 frames from the relevant video segment
        search_start_time = video_duration * (step.step_number - 1) / total_steps
        search_end_time = video_duration * step.step_number / total_steps
        
        candidate_times = np.linspace(search_start_time, search_end_time, num_frames_to_sample)
        
        best_frame_time = None
        highest_similarity = -1.0

        # Prepare text input for CLIP
        text_input = clip_processor(text=[step.description], return_tensors="pt", padding=True)

        log_video_step("SMART_SELECT", f"Finding best frame for: '{step.description}'")

        for time_in_seconds in candidate_times:
            temp_frame_path = FRAMES_DIR / f"temp_clip_{time_in_seconds}.jpg"
            if extract_frame(video_path, time_in_seconds, str(temp_frame_path)):
                try:
                    image = Image.open(temp_frame_path)
                    image_input = clip_processor(images=image, return_tensors="pt")
                    
                    with torch.no_grad():
                        outputs = clip_model(**text_input, **image_input)
                        similarity = outputs.logits_per_image.item()

                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_frame_time = time_in_seconds

                finally:
                    if temp_frame_path.exists():
                        temp_frame_path.unlink()

        if best_frame_time is not None:
            log_video_step("SMART_SELECT", f"Best frame found at {best_frame_time:.2f}s with similarity {highest_similarity:.2f}")
            if extract_frame(video_path, best_frame_time, str(output_path)):
                # Final quality check and enhancement
                quality = analyze_frame_quality(str(output_path))
                if quality < 0.3:
                    log_video_step("SMART_SELECT", "Best frame has low quality, enhancing...", error=False)
                    enhance_image(str(output_path))
                
                step.image_path = str(output_path)
                return True
        else:
            log_video_step("SMART_SELECT", "CLIP analysis did not yield a best frame.", error=True)

    except Exception as e:
        log_video_step("SMART_SELECT", f"Error in smart frame selection for step {step.step_number}: {e}", error=True)
        log_video_step("SMART_SELECT", f"Traceback: {traceback.format_exc()}", error=True)
    
    # Fallback if CLIP fails or no good frame is found
    log_video_step("SMART_SELECT", "Falling back to placeholder image.", error=False)
    create_placeholder_image(str(output_path), step.step_number, "Could not find relevant frame")
    step.image_path = str(output_path)
    return False 

def extract_text_from_frames(video_path: str, job_id: str) -> str:
    """Extract text from video frames using OCR."""
    log_video_step("OCR", f"Starting OCR text extraction for job {job_id}")
    
    try:
        duration = get_video_duration(video_path)
        if not duration:
            log_video_step("OCR", "Could not get video duration", error=True)
            return ""
        
        # Extract frames every 5 seconds to capture text
        extracted_text = []
        # Smart frame selection - scale interval based on video length
        if duration <= 60:  # Short video (≤1 min) - every 10 seconds
            interval = 10
        elif duration <= 300:  # Medium video (≤5 min) - every 15 seconds
            interval = 15
        elif duration <= 600:  # Long video (≤10 min) - every 20 seconds
            interval = 20
        else:  # Very long video (>10 min) - every 30 seconds
            interval = 30
        
        frame_times = np.arange(0, duration, interval)
        
        for time_seconds in frame_times:
            temp_frame_path = FRAMES_DIR / f"ocr_frame_{time_seconds:.1f}.jpg"
            
            if extract_frame(video_path, time_seconds, str(temp_frame_path)):
                try:
                    # Use pytesseract to extract text
                    image = Image.open(temp_frame_path)
                    text = pytesseract.image_to_string(image, config='--psm 6')
                    
                    if text.strip():
                        log_video_step("OCR", f"Found text at {time_seconds}s: {text[:50]}...")
                        extracted_text.append(text.strip())
                
                except Exception as e:
                    log_video_step("OCR", f"OCR failed for frame at {time_seconds}s: {e}", error=True)
                
                finally:
                    # Clean up temporary frame
                    if temp_frame_path.exists():
                        temp_frame_path.unlink()
        
        # Combine all extracted text
        combined_text = "\n".join(extracted_text)
        log_video_step("OCR", f"OCR extraction complete. Found {len(extracted_text)} text segments")
        
        return combined_text
        
    except Exception as e:
        log_video_step("OCR", f"Error in OCR extraction: {e}", error=True)
        return "" 