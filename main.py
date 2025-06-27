from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, Optional, List
import uuid
import os
import json
from pathlib import Path
import whisper
import yt_dlp
import ffmpeg
from fpdf import FPDF
import time
import requests
import re

app = FastAPI(title="Make It Easy - Video Processing API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Deepseek API configuration
DEEPSEEK_API_KEY = "sk-add35bac795a45528576d6ae8ee2b5dc"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Initialize Whisper model
whisper_model = whisper.load_model("small")

# Job status storage - simplified global queue
jobs: Dict[str, Dict] = {}
current_job_id: Optional[str] = None  # Track the currently processing job
job_lock = False  # Simple lock to prevent multiple jobs

# Add a startup cleanup to ensure no stale jobs
def cleanup_stale_jobs():
    """Clean up any stale jobs on startup"""
    global jobs, current_job_id
    jobs.clear()
    current_job_id = None
    print("Cleaned up stale jobs on startup")

# Call cleanup on startup
cleanup_stale_jobs()

# Create necessary directories
DOWNLOAD_DIR = Path("downloads")
FRAMES_DIR = Path("frames")
OUTPUT_DIR = Path("output")

for dir_path in [DOWNLOAD_DIR, FRAMES_DIR, OUTPUT_DIR]:
    dir_path.mkdir(exist_ok=True)

class VideoRequest(BaseModel):
    youtube_url: HttpUrl

class Step(BaseModel):
    number: int
    action: str
    timestamp: str
    explanation: str
    image_path: Optional[str] = None

class VideoContent(BaseModel):
    video_type: str  # "recipe", "building", "tutorial", "other"
    title: str
    materials_or_ingredients: List[str]
    steps: List[Step]

def call_deepseek_api(prompt: str) -> dict:
    """Call Deepseek API with a prompt and return the response"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 3000
    }
    
    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def download_video(youtube_url: str, job_id: str) -> str:
    """Download video from YouTube and return the path to the downloaded file"""
    output_path = DOWNLOAD_DIR / f"{job_id}.mp4"
    ydl_opts = {
        'format': 'best',
        'outtmpl': str(output_path)
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([str(youtube_url)])
    return str(output_path)

def transcribe_audio(video_path: str) -> str:
    """Transcribe audio from video file using Whisper"""
    try:
        result = whisper_model.transcribe(video_path)
        text = result["text"].strip()
        
        # Check if we got any meaningful text
        if not text or len(text) < 10:
            return "No clear audio content found in the video. Please provide a video with clear speech."
        
        return text
    except Exception as e:
        print(f"Whisper transcription error: {e}")
        return "Unable to transcribe audio from the video. The audio might be too short, corrupted, or contain no speech."

def analyze_video_content(text: str) -> VideoContent:
    """Analyze video transcript and create structured content with video type detection"""
    # Handle cases where transcription failed
    if "Unable to transcribe" in text or "No clear audio content" in text:
        return VideoContent(
            video_type="other",
            title="Audio Transcription Failed",
            materials_or_ingredients=["Clear audio required"],
            steps=[
                Step(number=1, action="Audio transcription failed", timestamp="00:00", 
                     explanation=text),
                Step(number=2, action="Try with a different video", timestamp="01:00", 
                     explanation="Please try uploading a video with clearer audio content or speech."),
                Step(number=3, action="Check video quality", timestamp="02:00", 
                     explanation="Ensure the video has audible speech and is not too short.")
            ]
        )
    
    prompt = f"""
    Analyze this video transcript and determine what type of instructional video it is, then create structured content.

    First, identify the video type:
    - "recipe" if it's about cooking/baking/food preparation
    - "building" if it's about construction, DIY, crafts, or making something physical
    - "tutorial" if it's about software, skills, or general how-to
    - "other" if it doesn't fit the above categories

    Then create appropriate content based on the type:
    - For recipes: List ingredients first, then cooking steps with "Börja med att...", "Sen ska du...", etc.
    - For building: List tools and materials first, then building steps with "Först behöver du...", "Nästa steg är att...", etc.
    - For tutorials: List requirements first, then tutorial steps with "Steg 1:", "Därefter...", etc.

    You MUST respond with ONLY a valid JSON object in this exact format:
    {{
        "video_type": "recipe|building|tutorial|other",
        "title": "Descriptive title in Swedish",
        "materials_or_ingredients": ["item 1", "item 2", "item 3"],
        "steps": [
            {{"number": 1, "action": "action description in Swedish", "timestamp": "MM:SS", "explanation": "detailed explanation in Swedish"}},
            {{"number": 2, "action": "action description in Swedish", "timestamp": "MM:SS", "explanation": "detailed explanation in Swedish"}}
        ]
    }}

    Make sure to:
    1. Write everything in Swedish
    2. Use appropriate language for the video type (cooking terms for recipes, building terms for construction, etc.)
    3. Create realistic timestamps based on the content
    4. Make steps clear and actionable
    5. Include 4-8 steps typically

    Transcript:
    {text}
    """
    
    try:
        response = call_deepseek_api(prompt)
        content = response['choices'][0]['message']['content'].strip()
        
        # Try to extract JSON from the response
        try:
            content_data = json.loads(content)
            steps = [Step(**step) for step in content_data['steps']]
            return VideoContent(
                video_type=content_data['video_type'],
                title=content_data['title'],
                materials_or_ingredients=content_data['materials_or_ingredients'],
                steps=steps
            )
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    content_data = json.loads(json_match.group(1))
                    steps = [Step(**step) for step in content_data['steps']]
                    return VideoContent(
                        video_type=content_data['video_type'],
                        title=content_data['title'],
                        materials_or_ingredients=content_data['materials_or_ingredients'],
                        steps=steps
                    )
                except json.JSONDecodeError:
                    pass
            
            # If that fails, try to find any JSON object in the text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    content_data = json.loads(json_match.group())
                    steps = [Step(**step) for step in content_data['steps']]
                    return VideoContent(
                        video_type=content_data['video_type'],
                        title=content_data['title'],
                        materials_or_ingredients=content_data['materials_or_ingredients'],
                        steps=steps
                    )
                except json.JSONDecodeError:
                    pass
            
            # If still fails, create a simple fallback
            return VideoContent(
                video_type="other",
                title="Instruktioner från video",
                materials_or_ingredients=["Se video för detaljer"],
                steps=[
                    Step(number=1, action="Förbered allt som behövs", timestamp="00:00", explanation="Börja med att förbereda allt som visas i videon"),
                    Step(number=2, action="Följ videoinstruktionerna", timestamp="01:00", explanation="Följ de detaljerade instruktionerna som visas i videon"),
                    Step(number=3, action="Slutför uppgiften", timestamp="02:00", explanation="Avsluta som det demonstreras i videon")
                ]
            )
    except Exception as e:
        print(f"Error calling Deepseek API: {e}")
        return VideoContent(
            video_type="other",
            title="API-fel uppstod",
            materials_or_ingredients=["Försök igen senare"],
            steps=[
                Step(number=1, action="API-fel uppstod", timestamp="00:00", 
                     explanation=f"Det uppstod ett fel vid bearbetning av videon: {str(e)}"),
                Step(number=2, action="Försök igen senare", timestamp="01:00", 
                     explanation="Vänligen försök bearbeta videon igen om en stund."),
                Step(number=3, action="Kontrollera videoformat", timestamp="02:00", 
                     explanation="Se till att videon är en giltig YouTube-URL och innehåller tydligt tal.")
            ]
        )

def extract_frame(video_path: str, timestamp: str, output_path: str):
    """Extract a frame from the video at the given timestamp using subprocess"""
    try:
        # Convert MM:SS to seconds for ffmpeg
        if ":" in timestamp:
            parts = timestamp.split(":")
            seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            seconds = int(timestamp)
        
        # Use subprocess instead of ffmpeg-python for better compatibility
        import subprocess
        
        # Try multiple ffmpeg command approaches
        commands = [
            # Simple seek and extract with update flag
            [
                'ffmpeg', '-y', '-ss', str(seconds), '-i', video_path,
                '-vframes', '1', '-update', '1', '-q:v', '2', output_path
            ],
            # Alternative with different format
            [
                'ffmpeg', '-y', '-i', video_path, '-ss', str(seconds),
                '-vframes', '1', '-f', 'image2', output_path
            ],
            # Simplest possible command
            [
                'ffmpeg', '-y', '-ss', str(seconds), '-i', video_path,
                '-frames:v', '1', output_path
            ]
        ]
        
        for i, cmd in enumerate(commands):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and os.path.exists(output_path):
                    return  # Success
                else:
                    print(f"Frame extraction approach {i+1} failed with return code {result.returncode}")
                    if result.stderr:
                        print(f"Error: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                print(f"Frame extraction approach {i+1} timed out")
            except Exception as e:
                print(f"Frame extraction approach {i+1} failed: {e}")
        
        # If all approaches failed, create a placeholder image
        print(f"All frame extraction methods failed, creating placeholder")
        create_placeholder_image(output_path)
        
    except Exception as e:
        print(f"Frame extraction error: {e}")
        # Create placeholder and continue
        create_placeholder_image(output_path)

def create_placeholder_image(output_path: str):
    """Create a simple placeholder image when frame extraction fails"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple placeholder image
        img = Image.new('RGB', (640, 360), color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Add text
        text = "Bild kunde inte extraheras"
        
        # Try to use a default font, fall back to basic if not available
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # Get text size and center it
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width, text_height = 200, 20
        
        x = (640 - text_width) // 2
        y = (360 - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        
        # Save the image
        img.save(output_path, 'JPEG')
        
    except Exception as e:
        print(f"Could not create placeholder image: {e}")
        # Create an empty file so the process can continue
        with open(output_path, 'w') as f:
            f.write("")

def clean_text_for_pdf(text: str) -> str:
    """Clean text to remove Unicode characters that cause PDF issues"""
    import unicodedata
    
    if not text:
        return ""
    
    # Replace various Unicode characters with ASCII equivalents
    replacements = {
        # Bullet points and list markers
        "•": "- ",
        "◦": "- ",
        "▪": "- ",
        "▫": "- ",
        "‣": "- ",
        "⁃": "- ",
        
        # Dashes and hyphens
        "–": "-",
        "—": "-",
        "―": "-",
        "‒": "-",
        
        # Quotes
        """: '"',
        """: '"',
        "'": "'",
        "'": "'",
        "‚": "'",
        "„": '"',
        "‹": "'",
        "›": "'",
        "«": '"',
        "»": '"',
        
        # Other punctuation
        "…": "...",
        "‰": "%",
        "‱": "%",
        
        # Symbols
        "°": " grader",
        "℃": "C",
        "℉": "F",
        "½": "1/2",
        "¼": "1/4",
        "¾": "3/4",
        "⅓": "1/3",
        "⅔": "2/3",
        "⅛": "1/8",
        "⅜": "3/8",
        "⅝": "5/8",
        "⅞": "7/8",
        
        # Currency
        "€": "EUR",
        "£": "GBP",
        "¥": "YEN",
        "¢": "cent",
        "₹": "INR",
        
        # Swedish characters (keep these for Swedish text)
        # "å": "a",
        # "ä": "a", 
        # "ö": "o",
        # "Å": "A",
        # "Ä": "A",
        # "Ö": "O",
        
        # Other accented characters
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "É": "E",
        "È": "E",
        "Ê": "E",
        "Ë": "E",
        "ü": "u",
        "ù": "u",
        "û": "u",
        "ú": "u",
        "Ü": "U",
        "Ù": "U",
        "Û": "U",
        "Ú": "U",
        "ñ": "n",
        "Ñ": "N",
        "ç": "c",
        "Ç": "C",
        "à": "a",
        "á": "a",
        "â": "a",
        "ã": "a",
        "À": "A",
        "Á": "A",
        "Â": "A",
        "Ã": "A",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "Ò": "O",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "Ì": "I",
        "Í": "I",
        "Î": "I",
        "Ï": "I",
        
        # Mathematical symbols
        "×": "x",
        "÷": "/",
        "±": "+/-",
        "≈": "~",
        "≠": "!=",
        "≤": "<=",
        "≥": ">=",
        
        # Arrows and symbols
        "→": "->",
        "←": "<-",
        "↑": "^",
        "↓": "v",
        "↔": "<->",
        "⇒": "=>",
        "⇐": "<=",
        "⇔": "<=>",
        
        # Other common problematic characters
        "\u00A0": " ",  # Non-breaking space
        "\u2000": " ",  # En quad
        "\u2001": " ",  # Em quad
        "\u2002": " ",  # En space
        "\u2003": " ",  # Em space
        "\u2004": " ",  # Three-per-em space
        "\u2005": " ",  # Four-per-em space
        "\u2006": " ",  # Six-per-em space
        "\u2007": " ",  # Figure space
        "\u2008": " ",  # Punctuation space
        "\u2009": " ",  # Thin space
        "\u200A": " ",  # Hair space
        "\u202F": " ",  # Narrow no-break space
        "\u205F": " ",  # Medium mathematical space
        "\u3000": " ",  # Ideographic space
    }
    
    cleaned_text = text
    for unicode_char, replacement in replacements.items():
        cleaned_text = cleaned_text.replace(unicode_char, replacement)
    
    # Try to normalize Unicode characters to ASCII equivalents
    try:
        # Normalize to decomposed form, then remove combining characters
        normalized = unicodedata.normalize('NFD', cleaned_text)
        ascii_text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        cleaned_text = ascii_text
    except Exception:
        pass
    
    # Remove any remaining problematic characters but preserve Swedish characters
    safe_chars = []
    for char in cleaned_text:
        char_code = ord(char)
        if char_code < 128:  # ASCII
            safe_chars.append(char)
        elif char in "åäöÅÄÖ":  # Keep Swedish characters
            safe_chars.append(char)
        else:
            # Replace other non-ASCII with safe equivalent or remove
            if char.isalpha():
                safe_chars.append('?')
            elif char.isdigit():
                safe_chars.append(char)
            elif char.isspace():
                safe_chars.append(' ')
            else:
                safe_chars.append('')  # Remove other problematic characters
    
    result = ''.join(safe_chars)
    
    # Clean up multiple spaces
    result = ' '.join(result.split())
    
    return result

def generate_pdf(video_content: VideoContent, job_id: str) -> str:
    """Generate a beautiful PDF with integrated text and images"""
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Add title page
        pdf.add_page()
        pdf.set_font("Arial", "B", 24)
        pdf.ln(20)
        pdf.cell(0, 15, clean_text_for_pdf(video_content.title), ln=True, align='C')
        
        pdf.ln(10)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Genererat av MakeItEasy", ln=True, align='C')
        pdf.cell(0, 10, f"Videotyp: {clean_text_for_pdf(video_content.video_type.title())}", ln=True, align='C')
        
        # Add materials/ingredients section
        pdf.ln(20)
        pdf.set_font("Arial", "B", 16)
        
        if video_content.video_type == "recipe":
            pdf.cell(0, 10, "Ingredienser:", ln=True)
        elif video_content.video_type == "building":
            pdf.cell(0, 10, "Verktyg och Material:", ln=True)
        else:
            pdf.cell(0, 10, "Du behover:", ln=True)
        
        pdf.set_font("Arial", "", 12)
        pdf.ln(5)
        
        for item in video_content.materials_or_ingredients:
            # Clean the text for PDF compatibility
            clean_item = clean_text_for_pdf(item)
            pdf.cell(0, 8, f"- {clean_item}", ln=True)
        
        # Add steps section
        pdf.ln(15)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Instruktioner:", ln=True)
        
        for step in video_content.steps:
            # Check if we need a new page (rough estimate)
            if pdf.get_y() > 200:  # If we're near the bottom of the page
                pdf.add_page()
            
            pdf.ln(10)
            
            # Step header
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, f"Steg {step.number}: {clean_text_for_pdf(step.action)}", ln=True)
            
            # Step details
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, f"Tid: {clean_text_for_pdf(step.timestamp)}", ln=True)
            
            # Step explanation
            pdf.set_font("Arial", "", 12)
            pdf.ln(3)
            
            # Clean and split long text into multiple lines
            clean_explanation = clean_text_for_pdf(step.explanation)
            explanation_lines = []
            words = clean_explanation.split()
            current_line = ""
            
            for word in words:
                if len(current_line + " " + word) < 80:  # Rough character limit per line
                    current_line += " " + word if current_line else word
                else:
                    if current_line:
                        explanation_lines.append(current_line)
                    current_line = word
            
            if current_line:
                explanation_lines.append(current_line)
            
            for line in explanation_lines:
                pdf.cell(0, 6, line, ln=True)
            
            # Add image if available
            if step.image_path and os.path.exists(step.image_path):
                pdf.ln(5)
                
                # Check if image fits on current page, if not start new page
                if pdf.get_y() > 150:
                    pdf.add_page()
                
                try:
                    # Add image with proper sizing
                    pdf.image(step.image_path, x=30, y=pdf.get_y(), w=150)
                    pdf.ln(80)  # Move down after image
                except Exception as e:
                    print(f"Could not add image for step {step.number}: {e}")
                    pdf.cell(0, 8, "[Bild kunde inte laddas]", ln=True)
            
            # Add separator line
            pdf.ln(5)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
        
        # Save PDF (outside the loop but inside try block)
        output_path = OUTPUT_DIR / f"{job_id}.pdf"
        pdf.output(str(output_path))
        return str(output_path)
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        # Create a simple fallback PDF
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "Fel vid PDF-generering", ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.ln(10)
            pdf.cell(0, 10, "Ett fel uppstod vid skapandet av PDF-filen.", ln=True)
            pdf.cell(0, 10, f"Felmeddelande: {str(e)}", ln=True)
            
            output_path = OUTPUT_DIR / f"{job_id}.pdf"
            pdf.output(str(output_path))
            return str(output_path)
        except Exception as fallback_error:
            print(f"Fallback PDF generation also failed: {fallback_error}")
            # Create empty file as last resort
            output_path = OUTPUT_DIR / f"{job_id}.pdf"
            with open(output_path, 'w') as f:
                f.write("")
            return str(output_path)

@app.post("/generate")
async def generate_instructions(video: VideoRequest, background_tasks: BackgroundTasks) -> dict:
    """Generate instructions from YouTube video"""
    global current_job_id, job_lock
    
    # Simple approach: Only allow one job at a time globally
    if job_lock or (current_job_id is not None and current_job_id in jobs and jobs[current_job_id]["status"] in ["processing", "transcribing", "analyzing", "extracting_frames", "generating_pdf"]):
        return {
            "error": "Ett jobb körs redan. Vänta tills det är klart innan du startar ett nytt.",
            "status": "busy",
            "active_job_id": current_job_id
        }
    
    # Set lock and create new job
    job_lock = True
    job_id = str(uuid.uuid4())
    current_job_id = job_id
    jobs[job_id] = {"status": "processing"}
    
    print(f"Starting new job: {job_id}")
    
    # Start background task
    background_tasks.add_task(process_video_task, str(video.youtube_url), job_id)
    return {"job_id": job_id, "status": "processing"}

def process_video_task(youtube_url: str, job_id: str):
    """Background task to process video"""
    global current_job_id, job_lock
    
    try:
        # Download video
        video_path = download_video(youtube_url, job_id)
        jobs[job_id]["status"] = "transcribing"
        
        # Transcribe audio
        transcript = transcribe_audio(video_path)
        jobs[job_id]["status"] = "analyzing"
        
        # Analyze content and get structured data
        video_content = analyze_video_content(transcript)
        jobs[job_id]["status"] = "extracting_frames"
        
        # Extract frames for each step
        for step in video_content.steps:
            frame_path = FRAMES_DIR / f"{job_id}_{step.number}.jpg"
            try:
                extract_frame(video_path, step.timestamp, str(frame_path))
                step.image_path = str(frame_path)
            except Exception as e:
                print(f"Failed to extract frame for step {step.number}: {e}")
                # Continue without image
                step.image_path = None
        
        # Generate PDF
        jobs[job_id]["status"] = "generating_pdf"
        pdf_path = generate_pdf(video_content, job_id)
        jobs[job_id].update({
            "status": "completed",
            "pdf_path": pdf_path
        })
        
        # Clear current job when completed
        if current_job_id == job_id:
            current_job_id = None
        job_lock = False
        
    except Exception as e:
        jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })
        print(f"Error processing video {job_id}: {e}")
        
        # Clear current job when failed
        if current_job_id == job_id:
            current_job_id = None
        job_lock = False

@app.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/result/{job_id}")
async def get_result(job_id: str) -> FileResponse:
    """Get generated PDF"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    return FileResponse(
        job["pdf_path"],
        media_type="application/pdf",
        filename=f"instructions_{job_id}.pdf"
    )

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main web interface"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read()) 