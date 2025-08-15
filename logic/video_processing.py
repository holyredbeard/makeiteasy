import os
import subprocess
import yt_dlp
import traceback
import torch
import tempfile
import shutil
import time
from pathlib import Path
from backend.transcribe.faster_whisper_engine import transcribe_audio_stream, transcribe_and_collect
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageEnhance
from models.types import Step
import threading
import hashlib
import json
import time
import logging
import numpy as np
import cv2
import pytesseract
import re
import mutagen
from transformers import BlipProcessor, BlipForConditionalGeneration

# --- Tesseract Configuration ---
try:
    if os.path.exists('/opt/homebrew/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
except Exception as e:
    logging.warning(f"Could not set Tesseract path: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('output/video_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Model Loading ---
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# Whisper model for audio transcription
whisper_model = None
model_lock = threading.Lock()

# BLIP model for image analysis
blip_processor = None
blip_model = None
blip_lock = threading.Lock()

def get_whisper_model(model_size="tiny"):
    global whisper_model
    with model_lock:
        if whisper_model is None:
            logger.info(f"Initializing Whisper model ({model_size})...")
            whisper_model = whisper.load_model(model_size, device=device)
            logger.info("Whisper model loaded.")
        return whisper_model

def get_blip_model():
    global blip_processor, blip_model
    with blip_lock:
        if blip_processor is None or blip_model is None:
            logger.info("Initializing BLIP model for image analysis (cached, fast processor)...")
            # use_fast=True minskar preprocessing-overhead
            blip_processor = BlipProcessor.from_pretrained(
                "Salesforce/blip-image-captioning-base",
                use_fast=True
            )
            blip_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            blip_model.to(device)
            logger.info("BLIP model loaded.")
        return blip_processor, blip_model

def preload_vision_models():
    """Warm start for vision models to undvika kallstart vid första Generate."""
    try:
        get_blip_model()
    except Exception as e:
        logger.warning(f"BLIP preload skipped: {e}")

# --- Utility Functions ---
def get_video_id(url: str) -> Optional[str]:
    """Extracts video ID from YouTube URL."""
    if "youtube.com" in url or "youtu.be" in url:
        match = re.search(r"(?<=v=)[^&#]+", url) or re.search(r"(?<=be/)[^&#]+", url)
        return match.group(0) if match else None
    return None


# --- DiskCache implementation (replaces simple JSON cache) ---
try:
    import diskcache as dc
    _cache = dc.Cache("cache")
    _cache_available = True
except ImportError:
    _cache_available = False
    _cache = None

CACHE_TTL_SECONDS = 60 * 60 * 24 * 90  # 90 days


def cache_get(key: str) -> Optional[dict]:
    if not _cache_available or not _cache:
        return None
    try:
        return _cache.get(key)
    except Exception:
        return None


def cache_set(key: str, data: dict):
    if not _cache_available or not _cache:
        return
    try:
        _cache.set(key, data, expire=CACHE_TTL_SECONDS)
    except Exception:
        pass


def try_fetch_captions(video_url: str, job_id: str) -> Optional[dict]:
    """Attempt to download auto-captions via yt-dlp (vtt). Returns dict {text, confidence} or None."""
    video_id = get_video_id(video_url) or job_id
    cache_k = f"captions:{video_id}:v1"
    cached = cache_get(cache_k)
    if cached:
        return cached

    download_path = Path("downloads")
    download_path.mkdir(exist_ok=True)
    outtmpl = str(download_path / f"{job_id}.%(ext)s")
    ydl_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'subtitleslangs': ['sv', 'en.*']
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        # find vtt file
        for f in download_path.iterdir():
            if f.stem == job_id and f.suffix.lower().endswith('.vtt'):
                text = f.read_text(encoding='utf-8', errors='ignore')
                # strip WEBVTT and timestamps
                lines = []
                for ln in text.splitlines():
                    if ln.strip() == '' or ln.strip().upper().startswith('WEBVTT'):
                        continue
                    if '-->' in ln:
                        continue
                    lines.append(ln.strip())
                plain = ' '.join([l for l in lines if l])
                # heuristic confidence
                confidence = 0.8 if len(plain) > 80 else 0.6
                result = {"text": plain, "confidence": confidence, "raw_path": str(f)}
                cache_set(cache_k, result)
                return result
    except Exception as e:
        logger.debug(f"[CAPTIONS] Unable to fetch captions: {e}")
    return None

def get_media_duration(file_path: str, is_audio: bool) -> Optional[float]:
    """
    Gets the duration of a media file.
    Uses mutagen for audio files and OpenCV for video files.
    """
    try:
        if is_audio:
            audio = mutagen.File(file_path)
            if audio and hasattr(audio, 'info') and audio.info:
                logger.info(f"[DURATION] Audio duration (mutagen): {audio.info.length:.2f} seconds")
                return audio.info.length
            logger.warning(f"[DURATION] Could not read audio info from {file_path}")
            return None
        else:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                logger.error(f"[DURATION] Cannot open video file: {file_path}")
                return None
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            logger.info(f"[DURATION] Video duration (OpenCV): {duration:.2f} seconds")
            cap.release()
            return duration
    except Exception as e:
        logger.error(f"[DURATION] Error getting duration for {file_path}: {e}")
        return None

# --- Core Processing Functions ---

def extract_video_metadata(video_url: str) -> dict:
    """Extracts metadata from a video URL using yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            title = info.get('title', 'Unknown Title')
            description = info.get('description', '')
            logger.info(f"[METADATA] Extracted title: {title[:50]}...")
            logger.info(f"[METADATA] Description preview: {description[:80].replace(os.linesep, ' ')}...")

            is_recipe_desc = contains_ingredients(description)
            log_msg = "✅ Description appears to contain a recipe" if is_recipe_desc else "ℹ️ Description does not appear to be a recipe"
            logger.info(f"[METADATA] {log_msg}")

            return {
                'title': title,
                'description': description,
                'is_recipe_in_description': is_recipe_desc
            }
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return {}

def download_thumbnail(video_url: str, job_id: str) -> Optional[str]:
    """Downloads the best available thumbnail for a video."""
    download_path = Path("downloads")
    download_path.mkdir(exist_ok=True)
    
    # Define yt-dlp options for downloading the thumbnail
    ydl_opts = {
        'outtmpl': str(download_path / f'{job_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,  # We only want the thumbnail
        'writethumbnail': True,
    }

    logger.info(f"[THUMBNAIL] Starting thumbnail download for job {job_id}...")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
            
            # Find the downloaded thumbnail (yt-dlp saves it with original extension like .jpg, .webp etc)
            for file in download_path.iterdir():
                if file.stem == job_id and file.suffix != '.mp4' and file.suffix != '.m4a' and file.suffix != '.mp3':
                    logger.info(f"[THUMBNAIL] ✅ SUCCESS: Thumbnail downloaded to {file}")
                    return str(file)
            
            logger.error("[THUMBNAIL] ❌ FAILED: Thumbnail downloaded, but file not found.")
            return None
            
    except Exception as e:
        logger.error(f"[THUMBNAIL] ❌ FAILED: Error downloading thumbnail: {e}")
        return None

def download_video(video_url: str, job_id: str, audio_only: bool = False) -> Optional[str]:
    """
    Downloads video or audio from a URL using yt-dlp with robust format selection.
    """
    download_path = Path("downloads")
    download_path.mkdir(exist_ok=True)
    
    base_ydl_opts = {
        'outtmpl': str(download_path / f'{job_id}.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
        'ignoreerrors': True,
    }

    if audio_only:
        # Try a few audio format selectors to maximize compatibility
        formats = [
            {'format_name': 'Best audio (m4a preferred)', 'format_selector': 'bestaudio[ext=m4a]/bestaudio'},
            {'format_name': 'Audio bitrate <=128 or m4a (fallback)', 'format_selector': 'ba[abr<=128]/140'},
            {'format_name': 'Best audio (any)', 'format_selector': 'bestaudio'}
        ]
        final_ext = None
    else:
        formats = [
            {'format_name': 'Low Resolution (480p)', 'format_selector': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]'},
            {'format_name': 'Standard Definition (720p)', 'format_selector': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]'},
            {'format_name': 'Fallback: Best available up to 720p', 'format_selector': 'best[height<=720]'},
            {'format_name': 'Ultimate Fallback: Worst Quality', 'format_selector': 'worst'}
        ]
        final_ext = 'mp4'

    logger.info(f"[DOWNLOAD] Starting download for job {job_id} (Audio only: {audio_only})...")

    for f_info in formats:
        logger.info(f"[DOWNLOAD] Attempting download with '{f_info['format_name']}' format...")
        specific_opts = base_ydl_opts.copy()
        specific_opts['format'] = f_info['format_selector']
        if 'postprocessors' in f_info:
            specific_opts['postprocessors'] = f_info['postprocessors']
        
        try:
            with yt_dlp.YoutubeDL(specific_opts) as ydl:
                error_code = ydl.download([video_url])
                if error_code == 0:
                    # Scan for any file matching job_id stem and return it
                    for file in download_path.iterdir():
                        if file.stem == job_id:
                            logger.info(f"[DOWNLOAD] ✅ SUCCESS (Scan): Downloaded with '{f_info['format_name']}' format to {file}")
                            return str(file)
                    
                    logger.error("[DOWNLOAD] Download reported success, but no output file was found.")
                    return None
                else:
                    logger.warning(f"[DOWNLOAD] ⚠️ Download failed with error code {error_code} using '{f_info['format_name']}'")
        except Exception as e:
            logger.error(f"[DOWNLOAD] ❌ FAILED download with '{f_info['format_name']}': {e}")
            continue
    
    logger.error("[DOWNLOAD] Download failed after all attempts.")
    return None

def transcribe_audio(video_file_or_url: str, job_id: str, language: str = "en") -> Optional[str]:
    """Transcribe audio from a local file or a URL.
    If given a URL, download audio-only via yt-dlp. Convert to 16k mono WAV and stream transcription
    using faster-whisper. Returns full transcript text (same contract as before).
    """
    logger.info(f"[TRANSCRIBE] Starting transcription for job {job_id} with language '{language}'")
    start_ts = time.time()
    temp_files = []

    try:
        # Captions-first: if input is a URL, attempt to fetch auto-captions and use them if confident
        path_taken = "audio"
        video_id = get_video_id(video_file_or_url)
        pipeline_version = os.getenv("PIPELINE_VERSION", "fw_v1")
        if not Path(str(video_file_or_url)).exists() and video_id:
            captions = try_fetch_captions(video_file_or_url, job_id)
            if captions and captions.get("confidence", 0) >= 0.75:
                logger.info(f"[TRANSCRIBE] Using captions-first result for job {job_id} (confidence={captions.get('confidence')})")
                cache_set(f"transcript:{video_id}:{pipeline_version}", {"text": captions.get("text", ""), "source": "captions"})
                path_taken = "captions"
                # telemetry
                logger.info(f"[TELEMETRY] path_taken={path_taken}, cache_hit=False")
                return captions.get("text", "")
        # Determine input: local file or URL
        audio_path = None
        if Path(str(video_file_or_url)).exists():
            audio_path = str(video_file_or_url)
            audio_dl_ms = 0
        else:
            # treat as URL and download audio-only
            logger.info(f"[TRANSCRIBE] Input appears to be a URL, downloading audio for job {job_id}...")
            dl_start = time.time()
            audio_path = download_video(video_file_or_url, job_id, audio_only=True)
            audio_dl_ms = int((time.time() - dl_start) * 1000)
            if not audio_path:
                logger.error("[TRANSCRIBE] Failed to download audio from URL.")
                return None
            temp_files.append(audio_path)

        duration = get_media_duration(audio_path, is_audio=True)
        if duration is None:
            logger.warning(f"[TRANSCRIBE] Could not determine media duration for {audio_path}, proceeding to conversion/transcription.")
        elif duration < 0.5:
            logger.error(f"[TRANSCRIBE] Media duration is too short ({duration}s), likely no audio content.")
            return None

        # Convert to 16kHz mono WAV
        wav_tmp = tempfile.NamedTemporaryFile(prefix=f"{job_id}_", suffix=".wav", delete=False)
        wav_tmp_path = wav_tmp.name
        wav_tmp.close()

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ac", "1", "-ar", "16000", "-vn", "-f", "wav", wav_tmp_path
        ]
        logger.info(f"[TRANSCRIBE] Converting audio to 16k mono WAV: {' '.join(ffmpeg_cmd[:3])} ...")
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            logger.error(f"[TRANSCRIBE] ffmpeg conversion failed: {e}")
            return None
        temp_files.append(wav_tmp_path)

        # Stream transcription using faster-whisper engine
        logger.info(f"[TRANSCRIBE] Starting faster-whisper streaming for job {job_id}...")
        fw_start = time.time()
        transcript_text, timeline = transcribe_and_collect(wav_tmp_path, lang_hint=language)
        fw_transcribe_ms = int((time.time() - fw_start) * 1000)

        elapsed_ms = int((time.time() - start_ts) * 1000)
        logger.info(f"[TRANSCRIBE] Transcription completed for job {job_id} ({elapsed_ms} ms). Segments: {len(timeline)}")

        # cache transcript if video_id known
        if video_id:
            cache_set(f"transcript:{video_id}:{pipeline_version}", {"text": transcript_text, "timeline": timeline, "source": "audio"})

        # telemetry
        logger.info(f"[TELEMETRY] audio_dl_ms={locals().get('audio_dl_ms',0)}, fw_transcribe_ms={fw_transcribe_ms}, path_taken={path_taken}, cache_hit=False")

        return transcript_text

    except Exception as e:
        logger.error(f"[TRANSCRIBE] Transcription failed: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        # Cleanup temp files
        for fp in temp_files:
            try:
                if Path(fp).exists():
                    Path(fp).unlink()
                    logger.debug(f"[TRANSCRIBE] Removed temp file {fp}")
            except Exception:
                pass

def extract_and_save_frames(video_file: str, job_id: str, interval_seconds: int = 5) -> List[str]:
    """Extracts frames from a video at a given interval and saves them as images."""
    
    frame_dir = Path("frames") / job_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[FRAMES] Starting frame extraction for job {job_id}...")
    
    saved_frames = []
    
    try:
        cap = cv2.VideoCapture(video_file)
        if not cap.isOpened():
            logger.error("[FRAMES] ❌ FAILED: Cannot open video file for frame extraction.")
            return []
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval_seconds)
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frame_path = frame_dir / f"frame_{frame_count // frame_interval}.jpg"
                cv2.imwrite(str(frame_path), frame)
                saved_frames.append(str(frame_path))
                logger.info(f"[FRAMES] ✅ Saved frame to {frame_path}")
            
            frame_count += 1
            
        cap.release()
        logger.info(f"[FRAMES] ✅ SUCCESS: Frame extraction completed. Saved {len(saved_frames)} frames.")
        
    except Exception as e:
        logger.error(f"[FRAMES] ❌ FAILED: Error during frame extraction: {e}")
        return []
        
    return saved_frames

def extract_text_from_frames(video_file: str, job_id: str) -> Optional[str]:
    """
    Extracts text from video frames using Tesseract OCR.
    """
    logger.info("[OCR] Starting OCR analysis on video frames...")
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        logger.error("[OCR] Cannot open video file for OCR.")
        return None

    all_text = []
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps) if fps > 0 else 1

    for i in range(0, frame_count, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            text = pytesseract.image_to_string(thresh, config='--psm 6').strip()

            if text and len(text) > 5:
                logger.info(f"[OCR] Found text in frame {i}: {text[:50].replace(os.linesep, ' ')}...")
                all_text.append(text)
        except Exception as e:
            logger.warning(f"[OCR] Could not process frame {i} with Tesseract: {e}")
            continue
    
    cap.release()
    if not all_text:
        logger.info("[OCR] No readable text found in video frames.")
        return None
    
    unique_text = sorted(list(set(all_text)), key=all_text.index)
    full_text = "\n".join(unique_text)
    logger.info(f"[OCR] OCR completed. Found {len(unique_text)} unique text blocks.")
    return full_text

def analyze_frames_with_blip(frame_paths: List[str], job_id: str) -> Optional[str]:
    """
    Analyzes video frames using BLIP to describe cooking actions and ingredients.
    """
    if not frame_paths:
        logger.info("[BLIP] No frames to analyze.")
        return None
    
    logger.info(f"[BLIP] Starting BLIP analysis on {len(frame_paths)} frames...")
    
    try:
        processor, model = get_blip_model()
        descriptions = []
        
        for i, frame_path in enumerate(frame_paths):
            try:
                # Load and preprocess image
                image = Image.open(frame_path).convert('RGB')
                
                # Generate caption
                inputs = processor(image, return_tensors="pt").to(device)
                out = model.generate(**inputs, max_length=50, num_beams=5)
                caption = processor.decode(out[0], skip_special_tokens=True)
                
                # Add cooking-specific prompts to get better descriptions
                cooking_prompts = [
                    "cooking food",
                    "preparing ingredients", 
                    "kitchen cooking",
                    "food preparation"
                ]
                
                cooking_descriptions = []
                for prompt in cooking_prompts:
                    inputs = processor(image, text=prompt, return_tensors="pt").to(device)
                    out = model.generate(**inputs, max_length=50, num_beams=5)
                    cooking_desc = processor.decode(out[0], skip_special_tokens=True)
                    cooking_descriptions.append(cooking_desc)
                
                # Combine descriptions
                frame_description = f"Frame {i+1}: {caption}. Cooking context: {'; '.join(cooking_descriptions[:2])}"
                descriptions.append(frame_description)
                
                logger.info(f"[BLIP] Frame {i+1}: {caption[:100]}...")
                
            except Exception as e:
                logger.warning(f"[BLIP] Could not analyze frame {i+1}: {e}")
                continue
        
        if not descriptions:
            logger.info("[BLIP] No frames could be analyzed.")
            return None
        
        # Combine all descriptions
        full_description = "\n".join(descriptions)
        logger.info(f"[BLIP] Analysis completed. Generated {len(descriptions)} frame descriptions.")
        return full_description
        
    except Exception as e:
        logger.error(f"[BLIP] Error during frame analysis: {e}")
        return None

def contains_ingredients(text: Optional[str]) -> bool:
    if not text:
        return False
    ingredient_keywords = [
        "ingredients", "components", "you will need",
        "tbsp", "tablespoon", "tsp", "teaspoon",
        "grams", "g ", "kg", "ml", "liter", "cup", "oz",
        "salt", "pepper", "oil", "sugar", "flour", "water", "onion", "garlic"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ingredient_keywords)

if __name__ == '__main__':
    test_url = "https://www.youtube.com/watch?v=your_video_id"
    job_id = "test_job_123"
    
    video_file = download_video(test_url, job_id, audio_only=False)
    if video_file:
       print(f"Video downloaded to: {video_file}")
       ocr_text = extract_text_from_frames(video_file, job_id)
       print(f"OCR Text: {ocr_text}")
