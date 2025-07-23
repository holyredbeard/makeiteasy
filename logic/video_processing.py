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

# --- Tesseract Configuration ---
# Set the path to the Tesseract executable, especially for macOS/Homebrew
try:
    if os.path.exists('/opt/homebrew/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
    # Add other common paths if needed, e.g., for Windows or other Linux distros
    # elif os.path.exists('C:/Program Files/Tesseract-OCR/tesseract.exe'):
    #     pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'
except Exception as e:
    # Log an error if the path configuration fails, but don't crash
    logging.warning(f"Could not set Tesseract path: {e}")


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

def is_recipe_description(description: str) -> bool:
    """Check if a video description likely contains a recipe."""
    if not description or len(description.strip()) < 20:
        return False
    
    # Convert to lowercase for case-insensitive matching
    desc_lower = description.lower()
    
    # Recipe-related keywords in multiple languages
    recipe_keywords = [
        # English
        'ingredients', 'recipe', 'instructions', 'directions', 'prep time', 'cook time',
        'servings', 'serves', 'preparation', 'cooking', 'method', 'steps',
        # Swedish
        'ingredienser', 'recept', 'instruktioner', 'riktningar', 'förberedelsetid', 'koktid',
        'portioner', 'serverar', 'förberedelse', 'tillagning', 'metod', 'steg',
        # Common cooking terms
        'tbsp', 'tsp', 'cup', 'gram', 'g', 'kg', 'ml', 'l', 'oz', 'lb',
        'dl', 'msk', 'tsk', 'krm', 'st', 'stycken', 'paket', 'burk',
        # Cooking actions
        'mix', 'stir', 'cook', 'bake', 'fry', 'boil', 'simmer', 'heat',
        'blanda', 'röra', 'koka', 'baka', 'steka', 'koka', 'sjuda', 'värma',
        # Measurements and amounts
        '1/', '2/', '3/', '4/', '1/2', '1/3', '1/4', '3/4', '2/3',
        '1-', '2-', '3-', '4-', '5-', '6-', '7-', '8-', '9-',
        # Bullet points and lists
        '•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.',
        '1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)',
    ]
    
    # Check for recipe keywords
    keyword_matches = sum(1 for keyword in recipe_keywords if keyword in desc_lower)
    
    # Check for structured content (bullet points, numbered lists)
    structured_content = any(char in description for char in ['•', '-', '*']) or \
                        any(f"{i}." in description for i in range(1, 10)) or \
                        any(f"{i})" in description for i in range(1, 10))
    
    # Check for measurements/amounts
    has_measurements = any(measure in desc_lower for measure in ['tbsp', 'tsp', 'cup', 'gram', 'g', 'kg', 'ml', 'l', 'dl', 'msk', 'tsk'])
    
    # Score-based approach
    score = 0
    if keyword_matches >= 2:
        score += 3
    elif keyword_matches >= 1:
        score += 1
    
    if structured_content:
        score += 2
    
    if has_measurements:
        score += 2
    
    # Check for minimum length (recipes are usually detailed)
    if len(description.strip()) > 100:
        score += 1
    
    # Threshold for considering it a recipe
    return score >= 3

def extract_video_metadata(video_url: str) -> dict:
    """Extract video metadata including title and description."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            description = info.get('description', '')
            is_recipe = is_recipe_description(description)
            
            metadata = {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'description': description,
                'is_recipe_description': is_recipe,
            }
            
            log_video_step("METADATA", f"Extracted title: {metadata['title']}")
            if description:
                desc_preview = description[:100] + "..." if len(description) > 100 else description
                log_video_step("METADATA", f"Description preview: {desc_preview}")
                if is_recipe:
                    log_video_step("METADATA", "✅ Description appears to contain a recipe - will be used for recipe generation")
                else:
                    log_video_step("METADATA", "ℹ️ Description does not appear to be a recipe - will use transcription only")
            else:
                log_video_step("METADATA", "ℹ️ No description found - will use transcription only")
            
            return metadata
            
    except Exception as e:
        log_video_step("METADATA", f"Failed to extract metadata: {e}", error=True)
        return {'title': 'Unknown Title', 'description': '', 'is_recipe_description': False}

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

def download_video(video_url: str, job_id: str) -> Optional[Tuple[str, str, dict]]:
    """Download video from YouTube or TikTok with optimized format selection."""
    log_video_step("DOWNLOAD", f"Starting optimized download for job {job_id}...")
    output_path = DOWNLOADS_DIR / f"{job_id}.mp4"

    # Clean up any existing file
    if output_path.exists():
        output_path.unlink()

    # Optimized format selection to prioritize the absolute smallest video file to minimize download time.
    # This directly uses the 'worst' keyword which yt-dlp uses to select the lowest quality video and audio.
    format_option = 'worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst'

    try:
        ydl_opts = {
            'format': format_option,
            'outtmpl': str(output_path),
            'noplaylist': True,
            'quiet': True,
            'retries': 3,  # Add retries for robustness
            'fragment_retries': 3,
        }

        log_video_step("DOWNLOAD", f"Attempting download with optimized format: {format_option}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if output_path.exists() and output_path.stat().st_size > 50000:
            log_video_step("DOWNLOAD", f"✅ SUCCESS: Downloaded with optimized format")
            
            # Extract metadata after successful download
            metadata = extract_video_metadata(video_url)
            video_title = sanitize_filename(metadata.get('title', 'recipe'))
            
            return str(output_path), video_title, metadata
        else:
            log_video_step("DOWNLOAD", "Download with optimized format resulted in an empty or invalid file.", error=True)

    except Exception as e:
        log_video_step("DOWNLOAD", f"❌ FAILED optimized download: {e}", error=True)

    log_video_step("DOWNLOAD", "Download failed after all attempts.", error=True)
    return None

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

def simple_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    """
    Simple frame selection that extracts frames at regular intervals without using CLIP.
    This is a fallback when CLIP-based selection fails.
    """
    output_path = FRAMES_DIR / f"{job_id}_step_{step.step_number}.jpg"
    
    if not video_duration:
        video_duration = get_video_duration(video_path)
        
    if not video_duration:
        log_video_step("SIMPLE_SELECT", f"Cannot determine video duration for step {step.step_number}", error=True)
        create_placeholder_image(str(output_path), step.step_number, "Video duration unknown")
        step.image_path = str(output_path)
        return False
    
    # Calculate time for this step (simple approach)
    step_time = video_duration * (step.step_number - 0.5) / total_steps
    
    log_video_step("SIMPLE_SELECT", f"Extracting frame at {step_time:.2f}s for step {step.step_number}")
    
    if extract_frame(video_path, step_time, str(output_path)):
        step.image_path = str(output_path)
        return True
    else:
        log_video_step("SIMPLE_SELECT", f"Failed to extract frame for step {step.step_number}", error=True)
        create_placeholder_image(str(output_path), step.step_number, "Could not extract frame")
        step.image_path = str(output_path)
        return False

def smart_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    """
    Selects the best frame for a step using CLIP for relevance and quality metrics.
    Falls back to simple frame selection if CLIP fails.
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

        if best_frame_time is not None and highest_similarity > 0.1:  # Add minimum similarity threshold
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
        else:
            log_video_step("SMART_SELECT", f"CLIP found frame with low similarity ({highest_similarity:.2f}), falling back to simple selection", error=False)
                
    except Exception as e:
        log_video_step("SMART_SELECT", f"Error in smart frame selection for step {step.step_number}: {e}", error=True)
        log_video_step("SMART_SELECT", f"Traceback: {traceback.format_exc()}", error=True)
    
    # Fallback to simple frame selection if CLIP fails or no good frame is found
    log_video_step("SMART_SELECT", "Falling back to simple frame selection.", error=False)
    return simple_frame_selection(video_path, step, job_id, video_duration, total_steps)

def contains_ingredients(text: str) -> bool:
    """
    Check if the transcribed text contains recipe ingredients or cooking-related content.
    Returns True if the text appears to contain recipe information.
    """
    if not text or len(text.strip()) < 10:
        return False
    
    # Recipe-related keywords in Swedish and English
    recipe_keywords = [
        # Swedish
        'ingrediens', 'recept', 'koka', 'steka', 'baka', 'blanda', 'tillsätt', 'smör', 'mjöl', 'socker',
        'salt', 'peppar', 'olja', 'vitlök', 'lök', 'tomat', 'ost', 'kött', 'kyckling', 'fisk',
        'gram', 'kg', 'dl', 'ml', 'krm', 'msk', 'tsk', 'st', 'stycken', 'paket',
        
        # English
        'ingredient', 'recipe', 'cook', 'fry', 'bake', 'mix', 'add', 'butter', 'flour', 'sugar',
        'salt', 'pepper', 'oil', 'garlic', 'onion', 'tomato', 'cheese', 'meat', 'chicken', 'fish',
        'grams', 'kg', 'cups', 'tbsp', 'tsp', 'pieces', 'packages', 'ounces', 'pounds'
    ]
    
    # Cooking action words
    cooking_actions = [
        'koka', 'steka', 'baka', 'blanda', 'tillsätt', 'röra', 'vispa', 'krama', 'skära',
        'cook', 'fry', 'bake', 'mix', 'add', 'stir', 'whisk', 'knead', 'cut', 'chop'
    ]
    
    # Measurement words
    measurements = [
        'gram', 'kg', 'dl', 'ml', 'krm', 'msk', 'tsk', 'st', 'stycken', 'paket',
        'grams', 'cups', 'tbsp', 'tsp', 'pieces', 'packages', 'ounces', 'pounds'
    ]
    
    text_lower = text.lower()
    
    # Check for recipe keywords
    keyword_count = sum(1 for keyword in recipe_keywords if keyword in text_lower)
    
    # Check for cooking actions
    action_count = sum(1 for action in cooking_actions if action in text_lower)
    
    # Check for measurements
    measurement_count = sum(1 for measurement in measurements if measurement in text_lower)
    
    # Check for numbers (likely measurements)
    number_count = len(re.findall(r'\d+', text))
    
    # Scoring system
    score = 0
    if keyword_count >= 3:
        score += 2
    if action_count >= 2:
        score += 2
    if measurement_count >= 2:
        score += 2
    if number_count >= 3:
        score += 1
    
    # If text is very short, require higher score
    if len(text) < 50:
        return score >= 4
    else:
        return score >= 3

def extract_text_from_frames(video_path: str, job_id: str, max_frames: int = 10) -> str:
    """
    Extract text from video frames using OCR.
    Returns combined text from all frames that contain readable text.
    """
    try:
        log_video_step("OCR", f"Starting OCR analysis on video frames...")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            log_video_step("OCR", "Failed to open video for OCR")
            return ""
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        # Extract frames at regular intervals
        frame_interval = max(1, total_frames // max_frames)
        extracted_texts = []
        
        for i in range(0, total_frames, frame_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Preprocess image for better OCR
            # Convert to grayscale
            gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
            
            # Apply threshold to get black text on white background
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Try to extract text
            try:
                text = pytesseract.image_to_string(thresh, lang='eng+swe')
                text = text.strip()
                
                if text and len(text) > 5:  # Only keep meaningful text
                    extracted_texts.append(text)
                    log_video_step("OCR", f"Found text in frame {i}: {text[:50]}...")
                    
            except Exception as e:
                log_video_step("OCR", f"OCR failed on frame {i}: {e}")
                continue
        
        cap.release()
        
        # Combine all extracted text
        combined_text = "\n".join(extracted_texts)
        
        if combined_text:
            log_video_step("OCR", f"OCR completed. Found {len(extracted_texts)} frames with text.")
            return combined_text
        else:
            log_video_step("OCR", "No readable text found in video frames.")
            return ""
            
    except Exception as e:
        log_video_step("OCR", f"OCR analysis failed: {e}")
        return "" 