from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import uuid
import subprocess
import os
import json
import re
import requests
from typing import List, Optional
from fpdf import FPDF
import logging
import base64
import time
from datetime import datetime

# Create necessary directories
DOWNLOADS_DIR = Path("downloads")
FRAMES_DIR = Path("frames")
OUTPUT_DIR = Path("output")

for directory in [DOWNLOADS_DIR, FRAMES_DIR, OUTPUT_DIR]:
    directory.mkdir(exist_ok=True)

app = FastAPI(title="MakeItEasy", description="Convert YouTube videos to PDF instructions")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Global job storage - allows multiple simultaneous users!
jobs = {}
# Removed global locks - multiple users can now process videos simultaneously

# Fix tokenizer warnings and optimize multiprocessing
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"  # Prevent thread conflicts
os.environ["MKL_NUM_THREADS"] = "1"  # Intel Math Kernel Library threads

# Local CLIP model configuration
CLIP_MODEL = None  # type: Optional[object]
CLIP_PROCESSOR = None  # type: Optional[object]

def add_log_to_job(job_id: str, message: str):
    """Add log message to job logs"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if job_id not in jobs:
        jobs[job_id] = {}
    
    if 'logs' not in jobs[job_id]:
        jobs[job_id]['logs'] = []
    
    jobs[job_id]['logs'].append({
        "timestamp": timestamp,
        "message": message
    })
    
    # Keep only last 50 logs per job
    if len(jobs[job_id]['logs']) > 50:
        jobs[job_id]['logs'] = jobs[job_id]['logs'][-50:]

def log_progress(job_id: str, step: str, progress: int, message: str):
    """Log progress with progress bar"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    progress_bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
    log_msg = f"[{timestamp}] [{job_id[:8]}] {step}: [{progress_bar}] {progress}% - {message}"
    print(log_msg)
    add_log_to_job(job_id, f"{step}: {progress}% - {message}")

def log_step(job_id: str, step_num: int, total_steps: int, step_name: str, message: str):
    """Log step progress with visual indicator"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    progress = int((step_num / total_steps) * 100)
    progress_bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
    
    # Define step icons - only for main steps
    step_icons = {
        "DOWNLOADING VIDEO": "[DOWNLOAD]",
        "TRANSCRIBING AUDIO": "[TRANSCRIBE]", 
        "ANALYZING CONTENT": "[ANALYZE]",
        "EXTRACTING FRAMES": "[EXTRACT]",
        "CREATING PDF": "[CREATE]"
    }
    
    icon = step_icons.get(step_name, "[STEP]")
    log_msg = f"[{timestamp}] [{job_id[:8]}] {icon} STEP {step_num}/{total_steps}: [{progress_bar}] {progress}% - {step_name}"
    print(log_msg)
    print(f"[{timestamp}] [{job_id[:8]}] {message}")
    
    add_log_to_job(job_id, f"{icon} STEP {step_num}/{total_steps}: {step_name}")
    add_log_to_job(job_id, f"{message}")

def initialize_clip_model():
    """Initialize CLIP model"""
    global CLIP_MODEL, CLIP_PROCESSOR
    
    # If already loaded, return True
    if CLIP_MODEL is not None and CLIP_PROCESSOR is not None:
        return True
    
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Loading CLIP model...")
        
        from transformers import CLIPProcessor, CLIPModel
        import torch
        
        model_name = "openai/clip-vit-base-patch32"
        
        # Load CLIP model - much faster than BLIP-2!
        processor = CLIPProcessor.from_pretrained(model_name)
        model = CLIPModel.from_pretrained(model_name)
        
        CLIP_PROCESSOR = processor
        CLIP_MODEL = model
        
        print(f"[{timestamp}] CLIP loaded successfully - ready for smart frame selection!")
        return True
        
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] CLIP loading failed: {e}")
        print(f"[{timestamp}] Tip: Run 'pip install transformers' to ensure CLIP support")
        return False

class VideoRequest(BaseModel):
    youtube_url: HttpUrl
    language: str = "en"

class Step(BaseModel):
    number: int
    action: str
    timestamp: str
    explanation: str
    image_path: Optional[str] = None

class VideoContent(BaseModel):
    video_type: str
    title: str
    materials_or_ingredients: List[str]
    steps: List[Step]

def clean_text_for_pdf(text: str) -> str:
    """Clean text to remove problematic characters while preserving Swedish characters"""
    if not text:
        return ""
    
    # Remove any bullet points from the beginning of the text (AI often adds these)
    text = text.strip()
    while text and text[0] in ['•', '●', '◦', '‣', '⁃', '▪', '▫', '▸', '‧']:
        text = text[1:].strip()
    
    # Replace problematic quotation marks and dashes
    replacements = {
        """: '"',
        """: '"',
        "'": "'",
        "'": "'",
        "—": "-",
        "–": "-",
        "…": "...",
        "•": "-",  # Bullet point
        "●": "-",  # Filled bullet
        "◦": "-",  # White bullet  
        "‣": "-",  # Triangular bullet
        "⁃": "-",  # Hyphen bullet
        "▪": "-",  # Black square
        "▫": "-",  # White square
        "▸": "-",  # Triangular bullet
        "‧": "-",  # Hyphenation point
        "‚": ",",
        "„": '"',
        "‹": "<",
        "›": ">",
        "«": '"',
        "»": '"',
    }
    
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    # More aggressive cleaning - keep only safe characters
    safe_chars = []
    for char in result:
        # Keep ASCII chars, Swedish chars, and some common European chars
        if (ord(char) < 128 or 
            char in 'åäöÅÄÖéèàáíìúùóòñÑüÜ°' or 
            char.isspace()):
            safe_chars.append(char)
        else:
            # Replace any other problematic Unicode with simple equivalent
            safe_chars.append('?')
    
    return ''.join(safe_chars).strip()

def download_video(youtube_url: str, job_id: str) -> str:
    """Download video using yt-dlp with progress logging"""
    output_path = DOWNLOADS_DIR / f"{job_id}.mp4"
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Preparing yt-dlp for download...")
    print(f"[{timestamp}] Target format: MP4 (format 18 - optimal quality/size)")
    
    cmd = [
        "yt-dlp",
        "-f", "18",  # MP4 format
        "-o", str(output_path),
        str(youtube_url)
    ]
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Connecting to YouTube and fetching video metadata...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] yt-dlp failed:")
        print(f"[{timestamp}] Error message: {result.stderr}")
        raise Exception(f"Failed to download video: {result.stderr}")
    
    # Check file size
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Video downloaded: {file_size/1024/1024:.1f} MB")
    
    return str(output_path)

def transcribe_audio(video_path: str, job_id: Optional[str] = None) -> str:
    """Transcribe audio using Whisper with progress logging and timeout"""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Loading Whisper tiny model (fast and reliable)...")
        
        import whisper
        import concurrent.futures
        import threading
        
        # Use tiny model for faster, more reliable processing
        model = whisper.load_model("tiny")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Processing audio track from video...")
        
        # Use ThreadPoolExecutor with timeout for reliable processing
        def transcribe_with_model():
            return model.transcribe(video_path, language=None)
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(transcribe_with_model)
                # 90 second timeout for transcription
                result = future.result(timeout=90)
        except concurrent.futures.TimeoutError:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] TIMEOUT: Whisper transcription took too long (>90s)")
            return "INVALID TRANSCRIPTION: Audio processing timed out. Try with a shorter video."
        except Exception as e:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Whisper error: {e}")
            return "INVALID TRANSCRIPTION: Whisper could not process the audio."
        
        # Get detected language
        detected_language = result.get("language", "unknown")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Detected language: {detected_language}")
        if job_id:
            add_log_to_job(job_id, f"Detected language: {detected_language}")
        
        # Handle both string and list results from Whisper
        if isinstance(result["text"], list):
            text = " ".join(result["text"]).strip()
        else:
            text = result["text"].strip()
        
        # Store detected language in the text for later use
        text = f"[DETECTED_LANGUAGE:{detected_language}] {text}"
        
        # Check if we got meaningful text
        if not text or len(text) < 10:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] WARNING: Very short or no text found")
            return "No clear audio text found in the video. Try with a video with clear speech."
        
        # IMPROVED garbage detection
        emoji_count = sum(1 for char in text if ord(char) > 127 and not char.isalpha())
        word_count = len(text.split())
        
        # Check for too many emojis or special characters  
        if emoji_count > word_count * 0.2:  # More than 20% non-standard characters
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] GARBAGE TRANSCRIPTION: {emoji_count} emojis/special chars out of {word_count} words")
            print(f"[{timestamp}] Example: {text[:100]}...")
            return "INVALID TRANSCRIPTION: Too many emojis and special characters. The video likely has poor audio quality or wrong language."
        
        # Check for repetitive patterns (common in bad transcriptions)
        if len(set(text.split())) < len(text.split()) * 0.2:  # Less than 20% unique words
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] REPETITIVE TRANSCRIPTION: Only {len(set(text.split()))} unique words out of {word_count}")
            return "INVALID TRANSCRIPTION: Text is too repetitive. Whisper could not interpret the audio correctly."
        
        # Check for nonsensical character combinations
        nonsense_patterns = ['🥺', '😍', 'уб간', 'ím', 'Mus', 'drainingím']
        nonsense_count = sum(1 for pattern in nonsense_patterns if pattern in text)
        if nonsense_count > 2:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] NONSENSE TRANSCRIPTION: Found {nonsense_count} garbage patterns")
            return "INVALID TRANSCRIPTION: Text contains nonsense. Try with a video with clearer speech."
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        words = len(text.split())
        print(f"[{timestamp}] Transcription complete: {len(text)} characters, ~{words} words")
        if job_id:
            add_log_to_job(job_id, f"Transcription complete: {len(text)} characters, ~{words} words")
        
        return text
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Whisper transcription error: {e}")
        return "Transcription failed due to technical error. Please try again or use a different video."

def call_deepseek_api(prompt: str) -> dict:
    """Call Deepseek API with progress logging"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-add35bac795a45528576d6ae8ee2b5dc",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Sending request to Deepseek AI...")
    print(f"[{timestamp}] Prompt size: {len(prompt)} characters")
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Try to get token usage info if available
        if 'usage' in result:
            usage = result['usage']
            print(f"[{timestamp}] Deepseek response received!")
            print(f"[{timestamp}] Tokens: {usage.get('prompt_tokens', '?')} in + {usage.get('completion_tokens', '?')} out")
        else:
            print(f"[{timestamp}] Deepseek response received!")
        
        return result
    else:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Deepseek API error: {response.status_code}")
        raise Exception(f"API call failed: {response.status_code}")

def analyze_video_content(text: str, language: str = "en") -> VideoContent:
    """Analyze video content using Deepseek"""
    
    # Extract detected language from transcription
    detected_language = "en"  # Default fallback
    if text and text.startswith("[DETECTED_LANGUAGE:"):
        try:
            lang_end = text.find("]")
            if lang_end > 0:
                detected_language = text[19:lang_end]  # Extract language code
                text = text[lang_end + 1:].strip()  # Remove language prefix
                print(f"Using detected language: {detected_language}")
        except:
            pass
    
    # Use detected language instead of hardcoded Swedish
    target_language = detected_language
    
    # Language mappings for fallback content - MUCH MORE DETAILED!
    language_content = {
        "en": {
            "title": "Delicious Homemade Recipe (audio analysis failed)",
            "ingredients": [
                "2-3 cups Main protein (chicken, beef, fish, or vegetarian option)",
                "1 large Onion, diced",
                "2-3 cloves Garlic, minced",
                "1-2 tbsp Olive oil or cooking oil",
                "1 tsp Salt (or to taste)",
                "1/2 tsp Black pepper",
                "1-2 tbsp Mixed herbs (oregano, basil, or thyme)",
                "1/2 cup Cooking liquid (broth, wine, or water)",
                "2-3 cups Vegetables (see video for specific types)",
                "Optional: Cheese, cream, or other finishing ingredients"
            ],
            "steps": [
                ("Prep all ingredients", "Wash, chop, and measure all ingredients. Prepare your workspace with cutting boards, knives, and cooking utensils. Preheat pan or oven if needed."),
                ("Start cooking base", "Heat oil in a large pan over medium-high heat. Add onions and cook for 3-4 minutes until softened. Add garlic and cook for another minute until fragrant."),
                ("Add main protein", "Add your main protein to the pan. Cook for 5-7 minutes, stirring occasionally, until browned on all sides. Season with salt and pepper."),
                ("Add vegetables and seasonings", "Add vegetables and herbs to the pan. Stir to combine. Add cooking liquid if needed. Cook for 10-15 minutes until vegetables are tender."),
                ("Final seasoning and plating", "Taste and adjust seasoning with salt, pepper, and herbs. Add any finishing ingredients like cheese or cream. Serve hot with appropriate sides."),
                ("Serve and enjoy", "Transfer to serving plates or bowls. Garnish as desired. Serve immediately while hot for best flavor and texture.")
            ]
        },
        "sv": {
            "title": "Homemade Specialty (audio analysis failed)",
            "ingredients": [
                "500-750 g Main protein (chicken, beef, fish or vegetarian)",
                "1 large Yellow onion, chopped",
                "2-3 cloves Garlic, minced",
                "2 tbsp Olive oil or canola oil",
                "1 tsp Salt (or to taste)",
                "1/2 tsp Black pepper, ground",
                "1-2 tbsp Mixed herbs (oregano, basil or thyme)",
                "1/2 cup Cooking liquid (broth, wine or water)",
                "400-500 g Mixed vegetables (see video for specific types)",
                "2-3 Potatoes or rice as side dish",
                "Optional: Cheese, cream or other finishing ingredients"
            ],
            "steps": [
                ("Prepare all ingredients", "Rinse, chop and measure all ingredients carefully. Prepare your workspace with cutting boards, knives and kitchen utensils. Preheat pan or oven if needed."),
                ("Start with the base", "Heat oil in a large pan over medium-high heat. Add onion and cook for 3-4 minutes until softened. Add garlic and cook for another minute until fragrant."),
                ("Add the main protein", "Add your main protein to the pan. Cook for 5-7 minutes while stirring until nicely browned on all sides. Season with salt and pepper."),
                ("Add vegetables and seasonings", "Add the vegetables and herbs to the pan. Stir well. Pour in cooking liquid if needed. Let cook for 10-15 minutes until vegetables are tender."),
                ("Final seasoning and plating", "Taste and adjust seasoning with salt, pepper and herbs. Add any finishing ingredients like cheese or cream."),
                ("Serve and enjoy", "Distribute on plates or bowls. Garnish as desired. Serve immediately while hot for best flavor and consistency.")
            ]
        }
    }
    
    # Get content for the detected language, fallback to English
    content = language_content.get(target_language, language_content["en"])
    
    # Handle failed transcription
    if ("INVALID TRANSCRIPTION" in text or 
        "Transcription failed" in text or 
        len(text.strip()) < 10):
        
        return VideoContent(
            video_type="recipe",
            title=content["title"],
            materials_or_ingredients=content["ingredients"],
            steps=[
                Step(
                    number=i+1,
                    action=step[0],
                    timestamp=f"{i*2+1}:00",
                    explanation=step[1]
                ) for i, step in enumerate(content["steps"])
            ]
        )
    
    # Create language-specific prompt
    language_prompts = {
        "en": f"""
        Analyze this video transcription and extract step-by-step instructions in English.
        
        IMPORTANT for ingredients/materials:
        - ALWAYS include measurements and quantities (e.g. "2 cups flour", "3 apples", "1 tbsp salt")
        - If measurements aren't mentioned, use reasonable amounts based on recipe type
        - Capitalize ingredient names
        - Use standard measurements (cups, tbsp, tsp, lbs, oz, pieces)
        - NEVER use bullet points (•, ●, ◦) or special characters in ingredient list
        - Write plain text without formatting
        
        IMPORTANT for steps:
        - Write clear instructions without special characters
        - Use only plain text, no bullet points or Unicode symbols
        
        Return the result as JSON with this structure:
        {{
            "video_type": "recipe/building/tutorial/other",
            "title": "Video title",
            "materials_or_ingredients": ["2 cups Flour", "3 Apples", "1 tbsp Salt"],
            "steps": [
                {{
                    "number": 1,
                    "action": "Brief step description",
                    "timestamp": "0:30",
                    "explanation": "Detailed explanation of what to do"
                }}
            ]
        }}
        
        Transcription: {text}
        """,
        "sv": f"""
        Analyze this video transcription and extract step-by-step instructions in English.
        
        IMPORTANT for ingredients/materials:
        - ALWAYS include measurements and quantities (e.g. "2 cups flour", "3 apples", "1 tbsp salt")
        - If measurements aren't mentioned, use reasonable amounts based on recipe type
        - Capitalize ingredient names
        - Use standard measurements (cups, tbsp, tsp, lbs, oz, pieces)
        - NEVER use bullet points (•, ●, ◦) or special characters in ingredient list
        - Write plain text without formatting
        
        IMPORTANT for steps:
        - Write clear instructions without special characters
        - Use only plain text, no bullet points or Unicode symbols
        
        Return the result as JSON with this structure:
        {{
            "video_type": "recipe/building/tutorial/other",
            "title": "Video title",
            "materials_or_ingredients": ["2 cups Flour", "3 Apples", "1 tbsp Salt"],
            "steps": [
                {{
                    "number": 1,
                    "action": "Brief step description",
                    "timestamp": "0:30",
                    "explanation": "Detailed explanation of what to do"
                }}
            ]
        }}
        
        Transcription: {text}
        """
    }
    
    # Use the appropriate prompt for the detected language
    prompt = language_prompts.get(target_language, language_prompts["en"])
    
    try:
        response = call_deepseek_api(prompt)
        content = response["choices"][0]["message"]["content"]
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Interpreting AI response and extracting JSON...")
        print(f"[{timestamp}] Response size: {len(content)} characters")
        
        # Try multiple JSON parsing approaches
        content_data = None
        
        # Approach 1: Direct JSON parsing
        try:
            content_data = json.loads(content.strip())
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] JSON parsing successful (direct parsing)")
        except json.JSONDecodeError:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] Direct JSON parsing failed, trying code block...")
        
        # Approach 2: Extract from markdown code block
        if not content_data:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    content_data = json.loads(json_match.group(1))
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] JSON parsing successful (code block)")
                except json.JSONDecodeError:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Code block parsing failed, trying regex...")
        
        # Approach 3: Find any JSON object in text
        if not content_data:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    content_data = json.loads(json_match.group())
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] JSON parsing successful (regex search)")
                except json.JSONDecodeError:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] All JSON parsing methods failed")
        
        # If we got valid JSON, create VideoContent
        if content_data:
            # Validate required fields
            if all(key in content_data for key in ["video_type", "title", "materials_or_ingredients", "steps"]):
                steps = [Step(**step) for step in content_data['steps']]
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] VideoContent created ({target_language}):")
                print(f"[{timestamp}] Title: {content_data['title']}")
                print(f"[{timestamp}] Type: {content_data['video_type']}")
                print(f"[{timestamp}] Materials: {len(content_data['materials_or_ingredients'])} items")
                print(f"[{timestamp}] Steps: {len(content_data['steps'])} instructions")
                
                return VideoContent(
                    video_type=content_data['video_type'],
                    title=content_data['title'],
                    materials_or_ingredients=content_data['materials_or_ingredients'],
                    steps=steps
                )
        
        # If all parsing failed, create fallback
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] FALLBACK: Creating standard content")
        print(f"[{timestamp}] AI response preview: {content[:200]}...")
        
        return VideoContent(
            video_type="other",
            title="API response could not be parsed",
            materials_or_ingredients=["See video for details"],
            steps=[
                Step(
                    number=1,
                    action="API response could not be parsed",
                    timestamp="0:00",
                    explanation="The API returned a response that could not be parsed as JSON."
                ),
                Step(
                    number=2,
                    action="Follow video instructions manually",
                    timestamp="1:00",
                    explanation="Watch the video and follow the instructions manually."
                )
            ]
        )
    
    except Exception as e:
        print(f"Analysis error: {e}")
        # Return fallback content
        return VideoContent(
            video_type="other",
            title="Video analysis failed",
            materials_or_ingredients=["No materials could be identified"],
            steps=[
                Step(
                    number=1,
                    action="Analysis failed",
                    timestamp="0:00",
                    explanation=f"Could not analyze video content: {str(e)}"
                ),
                Step(
                    number=2,
                    action="Try again later",
                    timestamp="1:00",
                    explanation="Please try processing the video again in a moment."
                )
            ]
        )

def extract_frame(video_path: str, timestamp: str, output_path: str, video_duration: Optional[float] = None, step_number: int = 1, total_steps: int = 7):
    """Extract frame from video - SMART timing for cooking videos"""
    try:
        # Convert timestamp to seconds with better parsing
        ai_suggested_time = 10  # default fallback
        
        if ":" in timestamp:
            parts = timestamp.split(":")
            if len(parts) == 2:
                try:
                    minutes = int(parts[0])
                    secs = int(parts[1])
                    ai_suggested_time = minutes * 60 + secs
                except ValueError:
                    ai_suggested_time = 10
            elif len(parts) == 3:
                try:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    secs = int(parts[2])
                    ai_suggested_time = hours * 3600 + minutes * 60 + secs
                except ValueError:
                    ai_suggested_time = 10
        else:
            try:
                ai_suggested_time = int(float(timestamp)) if timestamp.isdigit() else 10
            except ValueError:
                ai_suggested_time = 10
        
        # SMART COOKING VIDEO TIMING - prioritize smart distribution over unreliable AI timestamps
        if video_duration and video_duration > 30:
            # Skip intro/outro, focus on middle cooking content
            cooking_start = video_duration * 0.1  # Skip first 10%
            cooking_end = video_duration * 0.9     # Skip last 10%
            cooking_duration = cooking_end - cooking_start
            
            # FIXED: Trust AI timestamps when they're within cooking zone - they're usually more accurate!
            if cooking_start <= ai_suggested_time <= cooking_end:
                # AI time is within reasonable cooking zone - USE IT!
                seconds = ai_suggested_time
                print(f"Using AI time {ai_suggested_time:.1f}s for step {step_number} (within cooking zone {cooking_start:.1f}s-{cooking_end:.1f}s)")
            else:
                # Only use smart distribution as fallback when AI time is clearly outside video bounds
                step_interval = cooking_duration / total_steps  
                smart_time = cooking_start + (step_number - 1) * step_interval + (step_interval / 2)
                seconds = smart_time
                print(f"Using smart time {smart_time:.1f}s for step {step_number} (AI time {ai_suggested_time:.1f}s outside cooking zone {cooking_start:.1f}s-{cooking_end:.1f}s)")
        else:
            # Short video fallback - still prefer AI time if reasonable
            if video_duration:
                seconds = max(5, min(ai_suggested_time, video_duration - 5))
                print(f"Short video: Using constrained AI time {seconds:.1f}s for step {step_number}")
            else:
                seconds = ai_suggested_time
                print(f"No duration info: Using AI time {ai_suggested_time:.1f}s for step {step_number}")
        
        # Extract frame with better quality settings
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(seconds), 
            '-i', video_path,
            '-vframes', '1', 
            '-q:v', '1',  # Best quality
            '-vf', 'scale=640:360',  # Consistent size
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            print(f"Frame extraction failed for timestamp {timestamp}, creating placeholder")
            create_placeholder_image(output_path)
            return False
        
        return True
            
    except Exception as e:
        print(f"Frame extraction failed: {e}")
        create_placeholder_image(output_path)
        return False

def get_video_duration(video_path: str) -> Optional[float]:
    """Get video duration in seconds"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        print(f"Failed to get video duration: {e}")
    return None

def create_placeholder_image(output_path: str):
    """Create placeholder image"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (640, 360), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Try to use a better font
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        text = "Image not available"
        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (640 - text_width) // 2
        y = (360 - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        img.save(output_path, 'JPEG')
    except:
        # Create empty file as fallback
        with open(output_path, 'w') as f:
            f.write("")

def analyze_frame_quality(image_path: str) -> float:
    """FAST frame quality analysis using basic image metrics"""
    try:
        from PIL import Image, ImageStat
        
        with Image.open(image_path) as img:
            # Resize to small size for much faster processing
            img.thumbnail((160, 90))  # Much smaller = much faster
            
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Quick basic metrics only
            stat = ImageStat.Stat(img)
            
            # Simple brightness check (avoid too dark/bright)
            brightness = sum(stat.mean) / len(stat.mean)
            brightness_score = 1.0 - abs(brightness - 128) / 128.0
            
            # Simple contrast check
            contrast = sum(stat.stddev) / len(stat.stddev)
            contrast_score = min(contrast / 30.0, 1.0)  # Lowered threshold
            
            # Skip expensive edge detection and histogram analysis
            # Just use basic brightness + contrast
            final_score = brightness_score * 0.4 + contrast_score * 0.6
            
            return max(0.3, min(1.0, final_score))  # Higher minimum for speed
            
    except Exception as e:
        print(f"Frame quality analysis failed: {e}")
        return 0.7  # Higher default score

def query_local_clip(image_path: str, instruction_text: str) -> Optional[float]:
    """Query local CLIP model for frame relevance - much faster than BLIP-2!"""
    try:
        if not CLIP_MODEL or not CLIP_PROCESSOR:
            print("CLIP model not loaded, falling back to quality analysis")
            return None
        
        import torch
        from PIL import Image
        
        # Load and preprocess image
        image = Image.open(image_path)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create text prompts for comparison
        cooking_action = instruction_text.strip()
        positive_prompt = f"someone {cooking_action} in kitchen"
        negative_prompt = "empty kitchen with no cooking activity"
        
        # Process inputs with CLIP
        inputs = CLIP_PROCESSOR(
            text=[positive_prompt, negative_prompt], 
            images=image, 
            return_tensors="pt", 
            padding=True
        )
        
        # Get CLIP predictions - very fast!
        with torch.no_grad():
            outputs = CLIP_MODEL(**inputs)
            logits_per_image = outputs.logits_per_image  # Image-text similarity scores
            probs = logits_per_image.softmax(dim=1)      # Convert to probabilities
        
        # Get relevance score (probability of positive vs negative)
        relevance_score = float(probs[0][0])  # Probability of positive match
        
        print(f"CLIP relevance {relevance_score:.2f} for '{cooking_action}'")
        return relevance_score
        
    except Exception as e:
        print(f"Local CLIP error: {e}, falling back to quality analysis")
        return None

def smart_frame_selection(video_path: str, step: Step, job_id: str, video_duration: Optional[float] = None, total_steps: int = 7) -> bool:
    """Smart frame selection with CLIP for optimal image quality"""
    try:
        print(f"Smart frame selection for step {step.number}: {step.action}")
        
        # Initialize CLIP model if not already loaded
        if not CLIP_MODEL or not CLIP_PROCESSOR:
            print("Initializing CLIP model for smart frame selection...")
            success = initialize_clip_model()
            if success:
                print("CLIP model loaded successfully!")
            else:
                print("CLIP model loading failed, using quality analysis only")
        
        # Improved timing calculation specifically for cooking videos
        if not video_duration:
            return False
            
        # Define cooking zone (skip intro/outro)
        cooking_start = max(30, video_duration * 0.15)  # Skip first 15% or 30s minimum
        cooking_end = min(video_duration - 30, video_duration * 0.85)  # Skip last 15% or 30s minimum
        cooking_duration = cooking_end - cooking_start
        
        if cooking_duration <= 0:
            return False
        
        # Get base time from AI (convert timestamp to seconds)
        base_time = 10  # default
        if ":" in step.timestamp:
            parts = step.timestamp.split(":")
            if len(parts) == 2:
                try:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    base_time = minutes * 60 + seconds
                except ValueError:
                    base_time = 10
        
        # Check if AI time is reasonable
        ai_time_reasonable = cooking_start <= base_time <= cooking_end
        
        if ai_time_reasonable:
            # Use AI time as primary candidate
            primary_time = base_time
            print(f"Step {step.number}: Using AI time {base_time}s (within cooking zone)")
        else:
            # Calculate distributed time for this step
            step_interval = cooking_duration / total_steps
            distributed_time = cooking_start + (step.number - 1) * step_interval + (step_interval / 2)
            primary_time = distributed_time
            print(f"Step {step.number}: AI time {base_time}s outside cooking zone, using distributed time {distributed_time:.1f}s")
        
        # Extract multiple candidate frames around the primary time
        candidate_times = []
        
        # BLIP-2 SMART: Generate multiple candidates for AI analysis
        candidate_times = [primary_time]  # Always include the primary time
        
        # Add nearby times for better selection (±15 seconds)
        for offset in [-15, -10, -5, 5, 10, 15]:
            candidate_time = primary_time + offset
            if cooking_start <= candidate_time <= cooking_end:
                candidate_times.append(candidate_time)
        
        # If AI time was reasonable but different from primary, add it too
        if ai_time_reasonable and abs(base_time - primary_time) > 3:
            if base_time not in candidate_times:
                candidate_times.append(base_time)
        
        if not candidate_times:
            # Fallback: just use the primary time
            candidate_times = [primary_time]
        
        print(f"Candidate times for step {step.number}: {[f'{t:.1f}s' for t in candidate_times]}")
        
        # Extract candidate frames
        candidates = []
        temp_frames = []
        
        for i, time_sec in enumerate(candidate_times):
            temp_path = FRAMES_DIR / f"{job_id}_{step.number}_candidate_{i}.jpg"
            cmd = [
                'ffmpeg', '-y', '-ss', str(time_sec), '-i', video_path,
                '-vframes', '1', '-q:v', '3', '-vf', 'scale=320:180', str(temp_path)  # Smaller + lower quality = much faster
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)  # 3s timeout instead of 10s
            if result.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
                candidates.append((temp_path, time_sec))
                temp_frames.append(temp_path)
        
        if not candidates:
            print(f"No candidate frames extracted, using standard method")
            return False
        
        # BLIP-2 ANALYSIS: Use AI to select the best frame that matches the step
        best_frame = None
        best_score = 0.0
        time_sec = 0
        
        if candidates:
            # Create simple instruction prompt for BLIP-2
            instruction_prompt = f"What cooking activity is shown in this image?"
            
            for candidate_path, candidate_time in candidates:
                # Use CLIP to analyze this frame
                relevance_score = query_local_clip(candidate_path, step.action)
                
                if relevance_score is None:
                    # Fallback to quality analysis if BLIP-2 fails
                    relevance_score = analyze_frame_quality(candidate_path)
                    print(f"Frame at {candidate_time:.1f}s: quality score {relevance_score:.2f} (BLIP-2 fallback)")
                else:
                    print(f"Frame at {candidate_time:.1f}s: BLIP-2 relevance {relevance_score:.2f} for '{step.action}'")
                
                # Choose the frame with highest relevance
                if relevance_score > best_score:
                    best_score = relevance_score
                    best_frame = candidate_path
                    time_sec = candidate_time
            
            if best_frame:
                print(f"Selected frame at {time_sec:.1f}s with score {best_score:.2f} (BLIP-2 ANALYSIS)")
        
        # Copy best frame to final location
        final_path = FRAMES_DIR / f"{job_id}_{step.number}.jpg"
        
        if best_frame:  # Remove threshold check for speed
            import shutil
            shutil.copy2(best_frame, final_path)
            print(f"Selected frame -> {final_path}")
            success = True
        else:
            success = False
        
        # Clean up temporary files
        for temp_path in temp_frames:
            try:
                os.remove(temp_path)
            except:
                pass
        
        return success
        
    except Exception as e:
        print(f"Smart frame selection failed: {e}")
        return False

def generate_pdf(video_content: VideoContent, job_id: str, language: str = "en") -> str:
    """Generate PDF with professional layout matching the reference design"""
    output_path = OUTPUT_DIR / f"{job_id}.pdf"
    
    try:
        # Create PDF with custom margins
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        
        # Set margins
        pdf.set_margins(20, 20, 20)
        
        # TITLE - Large, bold, uppercase
        pdf.set_font("Arial", "B", 24)
        title = clean_text_for_pdf(video_content.title).upper()
        pdf.ln(15)
        
        # Calculate title position for centering
        title_width = pdf.get_string_width(title)
        page_width = pdf.w - 2 * pdf.l_margin
        title_x = (page_width - title_width) / 2 + pdf.l_margin
        pdf.set_x(title_x)
        pdf.cell(title_width, 12, title, ln=True)
        
        # DESCRIPTION TEXT - Professional paragraph
        pdf.ln(8)
        pdf.set_font("Arial", "", 11)
        
        # Create a description based on video type
        if video_content.video_type == "recipe":
            description = f"A simple and delicious recipe that combines the best ingredients for an exquisite meal. Perfect balance between flavor and nutrition, ideal for both weekdays and celebrations. Follow these steps for guaranteed results that will impress family and friends."
        else:
            description = f"A step-by-step guide that takes you through the entire process in a simple and clear way. Professional tips and techniques that make the difference. Everything you need to know to succeed with your project from start to finish."
        
        # Word wrap for description
        words = description.split()
        line = ""
        max_width = 140  # characters per line
        
        for word in words:
            if len(line + " " + word) < max_width:
                line += " " + word if line else word
            else:
                if line:
                    pdf.cell(0, 6, line, ln=True)
                line = word
        if line:
            pdf.cell(0, 6, line, ln=True)
        
        # Add some metadata
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, f"Number of steps: {len(video_content.steps)}", ln=True)
        if video_content.video_type == "recipe":
            pdf.cell(0, 5, f"Number of ingredients: {len(video_content.materials_or_ingredients)}", ln=True)
        
        # INGREDIENTS/MATERIALS SECTION
        pdf.ln(12)
        pdf.set_font("Arial", "B", 16)
        
        if video_content.video_type == "recipe":
            section_title = "Ingredients:"
        else:
            section_title = "Material:"
            
        pdf.cell(0, 10, section_title, ln=True)
        
        # Ingredients list with bullets
        pdf.set_font("Arial", "", 11)
        pdf.ln(3)
        
        # Two-column layout for ingredients if many items
        ingredients = video_content.materials_or_ingredients
        if len(ingredients) > 8:
            # Two columns
            mid_point = len(ingredients) // 2
            left_column = ingredients[:mid_point]
            right_column = ingredients[mid_point:]
            
            y_start = pdf.get_y()
            
            # Left column
            for item in left_column:
                clean_item = clean_text_for_pdf(item)
                if clean_item and not clean_item.startswith(('•', '-')):
                    clean_item = clean_item[0].upper() + clean_item[1:] if len(clean_item) > 1 else clean_item.upper()
                pdf.cell(90, 6, f"- {clean_item}", ln=True)  # Use - instead of •
            
            # Right column
            pdf.set_xy(110, y_start)
            for item in right_column:
                clean_item = clean_text_for_pdf(item)
                if clean_item and not clean_item.startswith(('•', '-')):
                    clean_item = clean_item[0].upper() + clean_item[1:] if len(clean_item) > 1 else clean_item.upper()
                pdf.cell(90, 6, f"- {clean_item}", ln=True)  # Use - instead of •
                pdf.set_x(110)
            
            # Reset to full width
            pdf.set_x(pdf.l_margin)
        else:
            # Single column
            for item in ingredients:
                clean_item = clean_text_for_pdf(item)
                if clean_item and not clean_item.startswith(('•', '-')):
                    clean_item = clean_item[0].upper() + clean_item[1:] if len(clean_item) > 1 else clean_item.upper()
                pdf.cell(0, 6, f"- {clean_item}", ln=True)  # Use - instead of •
        
        # INSTRUCTIONS SECTION
        pdf.ln(15)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Instructions:", ln=True)
        
        # Steps with images
        for i, step in enumerate(video_content.steps, 1):
            pdf.ln(8)
            
            # Check if we need a new page
            if pdf.get_y() > 250:
                pdf.add_page()
                pdf.ln(10)
            
            # Step number and title
            pdf.set_font("Arial", "B", 14)
            action = clean_text_for_pdf(step.action)
            
            # Create step header like "1. Prepare the Chicken:"
            step_header = f"{i}. {action}:"
            pdf.cell(0, 8, step_header, ln=True)
            
            pdf.ln(3)
            
            # Step explanation
            pdf.set_font("Arial", "", 11)
            explanation = clean_text_for_pdf(step.explanation)
            
            # Check if we have an image for this step
            step_image_path = FRAMES_DIR / f"{job_id}_{step.number}.jpg"
            has_image = os.path.exists(step_image_path) and os.path.getsize(step_image_path) > 1000
            
            if has_image:
                # Text with image layout
                y_start = pdf.get_y()
                
                # Text area (left side, reduced width)
                text_width = 100  # mm
                words = explanation.split()
                line = ""
                max_chars = 60  # Reduced for image layout
                
                for word in words:
                    if len(line + " " + word) < max_chars:
                        line += " " + word if line else word
                    else:
                        if line:
                            pdf.cell(text_width, 5, line, ln=True)
                        line = word
                if line:
                    pdf.cell(text_width, 5, line, ln=True)
                
                # Image (right side)
                try:
                    img_x = text_width + 25  # Position from left
                    img_y = y_start
                    img_width = 60  # mm
                    
                    pdf.image(str(step_image_path), x=img_x, y=img_y, w=img_width)
                    
                    # Ensure we move past the image
                    text_height = pdf.get_y() - y_start
                    img_height = img_width * 0.6  # Approximate aspect ratio
                    
                    if img_height > text_height:
                        pdf.set_y(y_start + img_height + 5)
                    
                except Exception as e:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Could not add image for step {step.number}: {e}")
                    
            else:
                # Full-width text (no image)
                words = explanation.split()
                line = ""
                max_chars = 90
                
                for word in words:
                    if len(line + " " + word) < max_chars:
                        line += " " + word if line else word
                    else:
                        if line:
                            pdf.cell(0, 5, line, ln=True)
                        line = word
                if line:
                    pdf.cell(0, 5, line, ln=True)
            
            # Add subtle separator between steps
            if i < len(video_content.steps):
                pdf.ln(8)
                pdf.set_draw_color(230, 230, 230)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        
        # Footer
        pdf.ln(15)
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, f"Generated by MakeItEasy - {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
        
        # Save PDF
        pdf.output(str(output_path))
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] PDF created with professional layout: {output_path}")
        return str(output_path)
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        # Create simple fallback PDF - ENSURE we create a valid PDF file
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "PDF generation failed", ln=True)
            pdf.ln(10)
            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 10, "An error occurred while creating the PDF file.", ln=True)
            pdf.ln(5)
            pdf.cell(0, 10, f"Error message: {str(e)}", ln=True)
            pdf.ln(10)
            pdf.cell(0, 10, "Try processing the video again or contact support.", ln=True)
            
            # Ensure the fallback PDF is saved
            pdf.output(str(output_path))
            print(f"Fallback PDF created: {output_path}")
            return str(output_path)
            
        except Exception as fallback_error:
            print(f"Even fallback PDF creation failed: {fallback_error}")
            # Last resort: create a minimal PDF with basic text
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "", 12)
                pdf.cell(0, 10, "Critical error in PDF creation", ln=True)
                pdf.output(str(output_path))
                return str(output_path)
            except:
                # Absolute last resort: create empty PDF structure
                with open(output_path, 'wb') as f:
                    f.write(b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n174\n%%EOF')
                return str(output_path)

@app.post("/generate")
async def generate_instructions(video: VideoRequest, background_tasks: BackgroundTasks) -> dict:
    """Generate instructions from YouTube video - supports multiple simultaneous users!"""
    
    # Create new job for this user - no global locks needed!
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing"}
    
    print(f"Starting new job: {job_id}")
    
    background_tasks.add_task(process_video_task, str(video.youtube_url), job_id, video.language)
    return {"job_id": job_id, "status": "processing"}

def process_video_task(youtube_url: str, job_id: str, language: str = "en"):
    """Process video in background with detailed logging - each job runs independently"""
    
    start_time = time.time()
    total_steps = 5
    
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print("=" * 80)
        print(f"[{timestamp}] STARTING NEW JOB: {job_id}")
        print(f"[{timestamp}] YouTube URL: {youtube_url}")
        print(f"[{timestamp}] Language: {language}")
        print("=" * 80)
        
        # Add logs to job for browser console
        add_log_to_job(job_id, "=" * 80)
        add_log_to_job(job_id, f"STARTING NEW JOB: {job_id}")
        add_log_to_job(job_id, f"YouTube URL: {youtube_url}")
        add_log_to_job(job_id, f"Language: {language}")
        add_log_to_job(job_id, "=" * 80)
        
        # Step 1: Download
        step_start = time.time()
        log_step(job_id, 1, total_steps, "DOWNLOADING VIDEO", "Using yt-dlp to download from YouTube")
        jobs[job_id]["status"] = "processing"
        
        log_progress(job_id, "DOWNLOAD", 10, "Starting yt-dlp...")
        video_path = download_video(youtube_url, job_id)
        step_time = time.time() - step_start
        
        log_progress(job_id, "DOWNLOAD", 100, f"Done! Video saved: {video_path} ({step_time:.1f}s)")
        
        # Step 2: Transcribe
        step_start = time.time()
        log_step(job_id, 2, total_steps, "TRANSCRIBING AUDIO", "Using Whisper tiny model for fast processing")
        jobs[job_id]["status"] = "transcribing"
        
        log_progress(job_id, "TRANSCRIPTION", 20, "Loading Whisper model...")
        transcript = transcribe_audio(video_path, job_id)
        step_time = time.time() - step_start
        
        log_progress(job_id, "TRANSCRIPTION", 100, f"Done! Text: {len(transcript)} characters ({step_time:.1f}s)")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{job_id[:8]}] PREVIEW: {transcript[:150]}...")
        add_log_to_job(job_id, f"PREVIEW: {transcript[:150]}...")
        
        # Step 3: Analyze
        step_start = time.time()
        log_step(job_id, 3, total_steps, "ANALYZING CONTENT", "Using Deepseek AI to extract step-by-step instructions")
        jobs[job_id]["status"] = "analyzing"
        
        log_progress(job_id, "ANALYSIS", 30, "Sending text to Deepseek AI...")
        video_content = analyze_video_content(transcript, language)
        step_time = time.time() - step_start
        
        log_progress(job_id, "ANALYSIS", 100, f"Done! Title: {video_content.title} ({step_time:.1f}s)")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{job_id[:8]}] VIDEO TYPE: {video_content.video_type}")
        print(f"[{timestamp}] [{job_id[:8]}] NUMBER OF STEPS: {len(video_content.steps)}")
        print(f"[{timestamp}] [{job_id[:8]}] MATERIALS: {len(video_content.materials_or_ingredients)} items")
        add_log_to_job(job_id, f"VIDEO TYPE: {video_content.video_type}")
        add_log_to_job(job_id, f"NUMBER OF STEPS: {len(video_content.steps)}")
        add_log_to_job(job_id, f"MATERIALS: {len(video_content.materials_or_ingredients)} items")
        
        # Step 4: Extract Frames
        step_start = time.time()
        log_step(job_id, 4, total_steps, "EXTRACTING FRAMES", f"Smart frame selection for {len(video_content.steps)} steps")
        jobs[job_id]["status"] = "extracting_frames"
        
        # Get video duration
        video_duration = get_video_duration(video_path)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{job_id[:8]}] VIDEO LENGTH: {video_duration:.1f} seconds")
        add_log_to_job(job_id, f"VIDEO LENGTH: {video_duration:.1f} seconds")
        
        # Frame extraction with progress
        successful_extractions = 0
        smart_extractions = 0
        
        for i, step in enumerate(video_content.steps, 1):
            frame_progress = int((i / len(video_content.steps)) * 70) + 30  # 30-100%
            log_progress(job_id, "FRAME EXTRACTION", frame_progress, f"Processing step {i}/{len(video_content.steps)}: {step.action}")
            
            # ULTRA-FAST: Only try smart frame selection, no fallback to save time
            smart_success = smart_frame_selection(video_path, step, job_id, video_duration, len(video_content.steps))
            
            if smart_success:
                successful_extractions += 1
                smart_extractions += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] [{job_id[:8]}] FAST: Step {step.number} - {step.action}")
            else:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] [{job_id[:8]}] SKIP: Step {step.number} (no fallback for speed)")
        
        step_time = time.time() - step_start
        log_progress(job_id, "FRAME EXTRACTION", 100, f"Done! {successful_extractions}/{len(video_content.steps)} frames ({step_time:.1f}s)")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{job_id[:8]}] RESULTS: {smart_extractions} smart, {successful_extractions-smart_extractions} standard")
        add_log_to_job(job_id, f"RESULTS: {smart_extractions} smart, {successful_extractions-smart_extractions} standard")
        
        # Step 5: Generate PDF
        step_start = time.time()
        log_step(job_id, 5, total_steps, "CREATING PDF", "Combining text and images into final PDF")
        jobs[job_id]["status"] = "generating_pdf"
        
        log_progress(job_id, "PDF", 80, "Creating PDF document...")
        pdf_path = generate_pdf(video_content, job_id, language)
        step_time = time.time() - step_start
        
        # Check result
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            total_time = time.time() - start_time
            pdf_size = os.path.getsize(pdf_path)
            
            log_progress(job_id, "PDF", 100, f"Done! Size: {pdf_size} bytes ({step_time:.1f}s)")
            
            jobs[job_id].update({
                "status": "completed",
                "pdf_path": pdf_path
            })
            
            # Final summary
            timestamp = datetime.now().strftime("%H:%M:%S")
            print("=" * 80)
            print(f"[{timestamp}] JOB COMPLETED: {job_id}")
            print(f"[{timestamp}] TOTAL TIME: {total_time:.1f} seconds")
            print(f"[{timestamp}] PDF SIZE: {pdf_size/1024:.1f} KB")
            print(f"[{timestamp}] SUCCESS: {successful_extractions}/{len(video_content.steps)} steps with images")
            print("=" * 80)
            
            # Add final summary to job logs
            add_log_to_job(job_id, "=" * 80)
            add_log_to_job(job_id, f"JOB COMPLETED: {job_id}")
            add_log_to_job(job_id, f"TOTAL TIME: {total_time:.1f} seconds")
            add_log_to_job(job_id, f"PDF SIZE: {pdf_size/1024:.1f} KB")
            add_log_to_job(job_id, f"SUCCESS: {successful_extractions}/{len(video_content.steps)} steps with images")
            add_log_to_job(job_id, "=" * 80)
            
        else:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{job_id[:8]}] CRITICAL ERROR: PDF file is empty or does not exist!")
            jobs[job_id].update({
                "status": "failed",
                "error": "PDF file creation failed - file is empty"
            })
        
    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S")
        total_time = time.time() - start_time
        print("=" * 80)
        print(f"[{timestamp}] JOB FAILED: {job_id}")
        print(f"[{timestamp}] TIME BEFORE ERROR: {total_time:.1f} seconds")
        print(f"[{timestamp}] ERROR MESSAGE: {e}")
        print("=" * 80)
        
        import traceback
        traceback.print_exc()
        jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })
    
    finally:
        # Job completed - this job slot is now free for the next user
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Job {job_id[:8]} completed, resources released")

@app.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/result/{job_id}")
async def get_result(job_id: str) -> FileResponse:
    """Get generated PDF for download"""
    
    # First check if job exists in memory
    if job_id in jobs:
        job = jobs[job_id]
        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed")
        pdf_path = job["pdf_path"]
    else:
        # If job not in memory, check if PDF file exists on disk
        # This handles cases where server was restarted after job completion
        pdf_path = OUTPUT_DIR / f"{job_id}.pdf"
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            raise HTTPException(status_code=404, detail="PDF file not found or empty")
        pdf_path = str(pdf_path)
    
    # Verify the PDF file actually exists and is not empty
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise HTTPException(status_code=404, detail="PDF file not found or empty")
    
    # Create a better filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"MakeItEasy_Recipe_{timestamp}.pdf"
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main web interface"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read()) 