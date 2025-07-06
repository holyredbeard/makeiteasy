import os
import subprocess
import yt_dlp
import whisper
import torch
import traceback
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageStat
from transformers import CLIPProcessor, CLIPModel
from models.types import Step
import threading

# --- Configuration ---
DOWNLOADS_DIR = Path("downloads")
FRAMES_DIR = Path("frames")
DOWNLOADS_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)

class ModelManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check pattern
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
                    print("Initializing Whisper model (tiny)...")
                    self.whisper_model = whisper.load_model("tiny")
                    print("Whisper model loaded.")

    def _initialize_clip(self) -> None:
        """Initialize CLIP model if not already initialized."""
        if not self.clip_model or not self.clip_processor:
            with self._lock:
                if not self.clip_model or not self.clip_processor:
                    print("Initializing CLIP model...")
                    self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                    self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                    print("CLIP model loaded.")

    def get_whisper_model(self):
        """Get Whisper model, initializing if necessary."""
        self._initialize_whisper()
        return self.whisper_model

    def get_clip_models(self) -> Tuple[CLIPModel, CLIPProcessor]:
        """Get CLIP models, initializing if necessary."""
        self._initialize_clip()
        return self.clip_model, self.clip_processor

def download_video(youtube_url: str, job_id: str) -> str:
    output_path = DOWNLOADS_DIR / f"{job_id}.mp4"
    ydl_opts = {
        'format': '18',
        'outtmpl': str(output_path),
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return str(output_path)

def transcribe_audio(video_path: str, job_id: Optional[str] = None) -> str:
    model_manager = ModelManager()
    whisper_model = model_manager.get_whisper_model()
    result = whisper_model.transcribe(video_path)
    return result['text']

def get_video_duration(video_path: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None

def create_placeholder_image(output_path: str):
    img = Image.new('RGB', (640, 360), color = 'lightgray')
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    d.text((10,10), "Image not available", fill=(0,0,0), font=font)
    img.save(output_path, 'JPEG')

def analyze_frame_quality(image_path: str) -> float:
    try:
        with Image.open(image_path) as img:
            stat = ImageStat.Stat(img)
            return stat.stddev[0]
    except Exception:
        return 0.0

def query_local_clip(image_path: str, instruction_text: str) -> Optional[float]:
    model_manager = ModelManager()
    clip_model, clip_processor = model_manager.get_clip_models()
    
    try:
        image = Image.open(image_path)
        inputs = clip_processor(text=[instruction_text], images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = clip_model(**inputs)
        return outputs.logits_per_image.item()
    except Exception as e:
        print(f"Error querying CLIP: {e}")
        return None

def smart_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    final_path = FRAMES_DIR / f"{job_id}_{step.number}.jpg"
    step.image_path = str(final_path)

    try:
        if not video_duration:
            video_duration = get_video_duration(video_path) or 600

        cooking_start = video_duration * 0.1
        cooking_end = video_duration * 0.9
        
        try:
            time_parts = list(map(int, step.timestamp.split(':')))
            ai_time = sum(p * 60**i for i, p in enumerate(reversed(time_parts)))
        except (ValueError, AttributeError):
            ai_time = 0

        if not (cooking_start <= ai_time <= cooking_end):
             step_interval = (cooking_end - cooking_start) / total_steps
             ai_time = cooking_start + (step.number - 1) * step_interval

        cmd = ['ffmpeg', '-y', '-ss', str(ai_time), '-i', video_path, '-vframes', '1', '-q:v', '2', str(final_path)]
        subprocess.run(cmd, capture_output=True, text=True)

        if not final_path.exists() or final_path.stat().st_size < 1000:
            create_placeholder_image(str(final_path))
            return False
        return True

    except Exception as e:
        print(f"Frame selection failed for step {step.number}: {e}")
        create_placeholder_image(str(final_path))
        return False 