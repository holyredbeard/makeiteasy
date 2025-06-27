from fastapi import FastAPI, HTTPException, BackgroundTasks
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

# Job status storage
jobs: Dict[str, Dict] = {}

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
        "max_tokens": 2000
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

def parse_steps(text: str) -> List[Step]:
    """Parse steps from Deepseek API response"""
    # Handle cases where transcription failed
    if "Unable to transcribe" in text or "No clear audio content" in text:
        return [
            Step(number=1, action="Audio transcription failed", timestamp="00:00", 
                 explanation=text),
            Step(number=2, action="Try with a different video", timestamp="01:00", 
                 explanation="Please try uploading a video with clearer audio content or speech."),
            Step(number=3, action="Check video quality", timestamp="02:00", 
                 explanation="Ensure the video has audible speech and is not too short.")
        ]
    
    prompt = f"""
    Analyze this video transcript and break it down into clear, sequential steps.
    You MUST respond with ONLY a valid JSON array. No extra text, no explanation.
    
    Format: [
      {{"number": 1, "action": "action description", "timestamp": "MM:SS", "explanation": "detailed explanation"}},
      {{"number": 2, "action": "action description", "timestamp": "MM:SS", "explanation": "detailed explanation"}}
    ]
    
    Transcript:
    {text}
    """
    
    try:
        response = call_deepseek_api(prompt)
        content = response['choices'][0]['message']['content'].strip()
        
        # Try to extract JSON from the response
        try:
            steps_data = json.loads(content)
            return [Step(**step) for step in steps_data]
        except json.JSONDecodeError:
            # If direct parsing fails, try to extract from markdown code block
            import re
            # Look for ```json ... ``` blocks
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                try:
                    steps_data = json.loads(json_match.group(1))
                    return [Step(**step) for step in steps_data]
                except json.JSONDecodeError:
                    pass
            
            # If that fails, try to find any JSON array in the text
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    steps_data = json.loads(json_match.group())
                    return [Step(**step) for step in steps_data]
                except json.JSONDecodeError:
                    pass
            
            # If still fails, create a simple fallback
            return [
                Step(number=1, action="Prepare ingredients", timestamp="00:00", explanation="Start by preparing all necessary ingredients"),
                Step(number=2, action="Follow video instructions", timestamp="01:00", explanation="Follow the detailed instructions shown in the video"),
                Step(number=3, action="Complete the task", timestamp="02:00", explanation="Finish the task as demonstrated")
            ]
    except Exception as e:
        print(f"Error calling Deepseek API: {e}")
        return [
            Step(number=1, action="API Error occurred", timestamp="00:00", 
                 explanation=f"There was an error processing the video: {str(e)}"),
            Step(number=2, action="Try again later", timestamp="01:00", 
                 explanation="Please try processing the video again in a few moments."),
            Step(number=3, action="Check video format", timestamp="02:00", 
                 explanation="Ensure the video is a valid YouTube URL and contains clear speech.")
        ]

def extract_frame(video_path: str, timestamp: str, output_path: str):
    """Extract a frame from the video at the given timestamp"""
    try:
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(output_path, vframes=1, format='image2', update=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to extract frame: {e.stderr.decode()}")

def generate_pdf(steps: List[Step], job_id: str) -> str:
    """Generate PDF with steps and images"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for step in steps:
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"Step {step.number}", ln=True)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, step.action, ln=True)
        
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Timestamp: {step.timestamp}", ln=True)
        
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, step.explanation)
        
        if step.image_path and os.path.exists(step.image_path):
            pdf.image(step.image_path, x=10, y=None, w=190)
    
    output_path = OUTPUT_DIR / f"{job_id}.pdf"
    pdf.output(str(output_path))
    return str(output_path)

@app.post("/generate")
async def generate_instructions(video: VideoRequest, background_tasks: BackgroundTasks) -> dict:
    """Generate instructions from YouTube video"""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing"}
    
    # Start background task
    background_tasks.add_task(process_video_task, str(video.youtube_url), job_id)
    return {"job_id": job_id, "status": "processing"}

def process_video_task(youtube_url: str, job_id: str):
    """Background task to process video"""
    try:
        # Download video
        video_path = download_video(youtube_url, job_id)
        jobs[job_id]["status"] = "transcribing"
        
        # Transcribe audio
        transcript = transcribe_audio(video_path)
        jobs[job_id]["status"] = "analyzing"
        
        # Parse steps
        steps = parse_steps(transcript)
        jobs[job_id]["status"] = "extracting_frames"
        
        # Extract frames for each step
        for step in steps:
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
        pdf_path = generate_pdf(steps, job_id)
        jobs[job_id].update({
            "status": "completed",
            "pdf_path": pdf_path
        })
        
    except Exception as e:
        jobs[job_id].update({
            "status": "failed",
            "error": str(e)
        })
        print(f"Error processing video {job_id}: {e}")

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