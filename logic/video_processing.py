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
import re

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

def sanitize_filename(title: str) -> str:
    """Convert video title to a safe filename format."""
    # Remove or replace problematic characters
    safe_title = re.sub(r'[^\w\s-]', '', title)  # Remove special characters except spaces and hyphens
    safe_title = re.sub(r'[-\s]+', '-', safe_title)  # Replace spaces and multiple hyphens with single hyphen
    safe_title = safe_title.strip('-')  # Remove leading/trailing hyphens
    safe_title = safe_title.lower()  # Convert to lowercase
    
    # Limit length to avoid filesystem issues
    if len(safe_title) > 50:
        safe_title = safe_title[:50].rstrip('-')
    
    # Ensure it's not empty
    if not safe_title:
        safe_title = "recipe"
    
    return safe_title

def extract_video_metadata(video_url: str) -> dict:
    """Extract video metadata including title."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            metadata = {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
            }
            
            log_video_step("METADATA", f"Extracted title: {metadata['title']}")
            return metadata
            
    except Exception as e:
        log_video_step("METADATA", f"Failed to extract metadata: {e}", error=True)
        return {'title': 'Unknown Title'}

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

def is_tiktok_url(url: str) -> bool:
    """Check if the URL is a TikTok URL."""
    tiktok_patterns = [
        r'(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/\d+',
        r'(?:https?://)?(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+',
        r'(?:https?://)?(?:www\.)?tiktok\.com/t/[A-Za-z0-9]+',
        r'(?:https?://)?(?:m\.)?tiktok\.com/@[^/]+/video/\d+',
    ]
    
    for pattern in tiktok_patterns:
        if re.match(pattern, url.strip()):
            return True
    return False

def is_youtube_url(url: str) -> bool:
    """Check if the URL is a YouTube URL."""
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',  # YouTube Shorts support
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+',
        r'(?:https?://)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/channel/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/user/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/c/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/@[\w-]+',
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url.strip()):
            return True
    return False

def download_video(video_url: str, job_id: str) -> Tuple[str, str]:
    """Download video from YouTube or TikTok with enhanced error handling and validation."""
    log_video_step("DOWNLOAD", f"Starting download for job {job_id}")
    log_video_step("DOWNLOAD", f"URL: {video_url}")
    output_path = DOWNLOADS_DIR / f"{job_id}.mp4"
    
    # Detect platform
    is_tiktok = is_tiktok_url(video_url)
    is_youtube = is_youtube_url(video_url)
    
    if is_tiktok:
        log_video_step("DOWNLOAD", "Detected TikTok URL")
        platform = "TikTok"
    elif is_youtube:
        log_video_step("DOWNLOAD", "Detected YouTube URL") 
        platform = "YouTube"
    else:
        log_video_step("DOWNLOAD", "Unknown platform, attempting download anyway")
        platform = "Unknown"
    
    try:
        # Configure format options based on platform
        if is_tiktok:
            # TikTok-specific format options
            format_options = [
                'best[height<=1080][ext=mp4]',  # Best quality up to 1080p MP4
                'best[ext=mp4]',                # Best available MP4
                'worst[height>=360][ext=mp4]',  # At least 360p MP4
                'worst[ext=mp4]',               # Smallest available MP4
                'best',                         # Absolute best available
            ]
        else:
            # YouTube and other platforms format options - enhanced for Shorts
            format_options = [
                'best[height<=720][ext=mp4]',   # Best quality up to 720p MP4 (good for Shorts)
                'best[height<=480][ext=mp4]',   # Best quality up to 480p MP4
                'worst[height>=360][ext=mp4]',  # At least 360p MP4
                'best[ext=mp4]',                # Best available MP4
                'worst[height>=240][ext=mp4]',  # At least 240p MP4
                'worst[ext=mp4]',               # Smallest available MP4
                '22',                           # 720p MP4 (YouTube format)
                '18',                           # 360p MP4 (YouTube format)
                'best',                         # Absolute best available
                'worst',                        # Absolute smallest available
            ]
        
        min_file_size = 50000  # Minimum 50KB for valid video
        
        for format_option in format_options:
            try:
                # Clean up any existing file
                if output_path.exists():
                    output_path.unlink()
                
                ydl_opts = {
                    'format': format_option,
                    'outtmpl': str(output_path),
                    'noplaylist': True,
                    'extract_flat': False,
                    'writesubtitles': False,
                    'writeautomaticsub': False,
                    'ignoreerrors': False,
                    'no_warnings': False,
                }
                
                # Add platform-specific options
                if is_tiktok:
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                    })
                elif is_youtube:
                    # Enhanced YouTube-specific options for better compatibility
                    ydl_opts.update({
                        'extractor_args': {
                            'youtube': {
                                'skip': ['hls'],  # Skip HLS streams that might cause issues
                                'player_client': ['android', 'web', 'ios'],  # Try multiple clients
                                'innertube_host': 'www.youtube.com',
                                'innertube_key': None,
                            }
                        },
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                    })
                
                log_video_step("DOWNLOAD", f"Attempting download with format: {format_option}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                
                # Validate downloaded file
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    log_video_step("DOWNLOAD", f"Downloaded file size: {file_size} bytes")
                    
                    if file_size >= min_file_size:
                        # Additional validation: check if it's actually a video file
                        try:
                            duration = get_video_duration(str(output_path))
                            if duration and duration > 1.0:  # At least 1 second
                                log_video_step("DOWNLOAD", f"Successfully downloaded {platform} video with format '{format_option}': {output_path} ({file_size} bytes, {duration:.2f}s)")
                                # Extract video title for filename
                                try:
                                    metadata = extract_video_metadata(video_url)
                                    video_title = sanitize_filename(metadata['title'])
                                except Exception as e:
                                    log_video_step("DOWNLOAD", f"Failed to extract title: {e}")
                                    video_title = "recipe"
                                return str(output_path), video_title
                            else:
                                log_video_step("DOWNLOAD", f"Downloaded file has no valid duration ({duration}s), trying next format")
                        except Exception as duration_error:
                            log_video_step("DOWNLOAD", f"Cannot validate video duration: {duration_error}, trying next format")
                    else:
                        log_video_step("DOWNLOAD", f"Downloaded file is too small ({file_size} bytes), trying next format")
                    
                    # Clean up small/invalid file
                    output_path.unlink()
                else:
                    log_video_step("DOWNLOAD", f"No file was downloaded with format '{format_option}'")
                    
            except Exception as format_error:
                log_video_step("DOWNLOAD", f"Format '{format_option}' failed: {format_error}")
                if output_path.exists():
                    output_path.unlink()  # Clean up failed download
                continue
        
        # If we get here, all formats failed
        raise Exception(f"All download format options failed for {platform} video. The video may be unavailable, region-blocked, or in an unsupported format.")
            
    except Exception as e:
        log_video_step("DOWNLOAD", f"Error downloading {platform} video: {e}", error=True)
        raise

def transcribe_audio(video_path: str, job_id: Optional[str] = None) -> str:
    """Transcribe video audio with comprehensive error handling and fallback content."""
    log_video_step("TRANSCRIBE", f"Starting transcription for job {job_id}")
    
    try:
        # Check if video file exists and has content
        if not os.path.exists(video_path):
            log_video_step("TRANSCRIBE", f"Video file does not exist: {video_path}", error=True)
            return "Video file could not be found. Please try downloading the video again."
        
        file_size = os.path.getsize(video_path)
        log_video_step("TRANSCRIBE", f"Video file size: {file_size} bytes")
        
        if file_size < 50000:  # Less than 50KB is likely empty or corrupted
            log_video_step("TRANSCRIBE", f"Video file is too small ({file_size} bytes), likely empty or corrupted", error=True)
            return "The downloaded video file appears to be corrupted or empty. This may be due to the video being unavailable or region-blocked. Please try a different video or check if the video is accessible in your region."
        
        # Check video duration to ensure it has content
        duration = get_video_duration(video_path)
        if not duration or duration < 1.0:  # Less than 1 second
            log_video_step("TRANSCRIBE", f"Video duration is too short ({duration}s), likely no audio content", error=True)
            return "The video appears to be too short or contains no audio content. Please ensure the video has spoken content that can be transcribed."
        
        log_video_step("TRANSCRIBE", f"Video validation passed - Duration: {duration:.2f}s, Size: {file_size} bytes")
        
        model_manager = ModelManager()
        whisper_model = model_manager.get_whisper_model()
        
        # Try with different configurations to handle various audio issues
        transcription_attempts = [
            {"params": {"fp16": False}, "description": "standard settings"},
            {"params": {"fp16": False, "language": "en"}, "description": "English language hint"},
            {"params": {"fp16": False, "language": "en", "task": "transcribe"}, "description": "explicit transcribe task"},
            {"params": {"fp16": False, "temperature": 0.0}, "description": "deterministic mode"},
        ]
        
        for i, attempt in enumerate(transcription_attempts, 1):
            try:
                log_video_step("TRANSCRIBE", f"Attempt {i}/{len(transcription_attempts)}: {attempt['description']}")
                result = whisper_model.transcribe(video_path, **attempt['params'])
                
                if result and 'text' in result and result['text'].strip():
                    transcribed_text = result['text'].strip()
                    log_video_step("TRANSCRIBE", f"Successfully transcribed audio (attempt {i}): {len(transcribed_text)} characters")
                    return transcribed_text
                else:
                    log_video_step("TRANSCRIBE", f"Attempt {i} returned empty text, trying next approach")
                    
            except Exception as attempt_error:
                log_video_step("TRANSCRIBE", f"Attempt {i} failed: {attempt_error}")
                if i < len(transcription_attempts):
                    continue
                else:
                    # This was the last attempt, provide fallback
                    log_video_step("TRANSCRIBE", "All transcription attempts failed, providing fallback content")
                    return f"Audio transcription failed after {len(transcription_attempts)} attempts. The video may contain no speech, background music only, or audio in a format that cannot be processed. Please review the video manually to extract any cooking instructions or recipe information."
        
        # If we get here, all attempts returned empty text
        log_video_step("TRANSCRIBE", "All transcription attempts returned empty text, providing fallback content")
        return "The video audio could not be transcribed, possibly due to no speech content, background music only, or audio quality issues. Please review the video manually for any cooking instructions or recipe information."
            
    except Exception as e:
        log_video_step("TRANSCRIBE", f"Transcription process failed: {e}", error=True)
        return f"Audio transcription encountered an error: {str(e)}. Please try again or review the video manually for cooking instructions."

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