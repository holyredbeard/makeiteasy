from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from models.types import VideoRequest, YouTubeSearchRequest, YouTubeVideo, VideoContent
from logic.video_processing import (
    download_video, transcribe_audio, smart_frame_selection,
    get_video_duration, ModelManager
)
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import uuid
from typing import Dict, Any
import os
import traceback

router = APIRouter()

# In-memory storage for jobs.
jobs: Dict[str, Dict[str, Any]] = {}

def update_status(job_id: str, status: str, message: str, pdf_path: str = None):
    jobs[job_id]['status'] = status
    jobs[job_id]['message'] = message
    if pdf_path:
        jobs[job_id]['pdf_path'] = pdf_path

def process_video_task(youtube_url: str, job_id: str, language: str = "en"):
    """The main background task."""
    try:
        update_status(job_id, 'processing', 'Downloading video...')
        video_path = download_video(youtube_url, job_id)

        update_status(job_id, 'processing', 'Transcribing audio...')
        transcript = transcribe_audio(video_path, job_id)

        update_status(job_id, 'processing', 'Analyzing content...')
        video_content = analyze_video_content(transcript, language)
        if not video_content:
            raise Exception("Failed to analyze video content.")

        video_duration = get_video_duration(video_path)
        for step in video_content.steps:
            smart_frame_selection(video_path, step, job_id, video_duration, len(video_content.steps))
        
        update_status(job_id, 'processing', 'Generating PDF...')
        pdf_path = generate_pdf(video_content, job_id, language)

        update_status(job_id, 'completed', 'Job completed!', pdf_path=pdf_path)

    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        traceback.print_exc()
        update_status(job_id, 'failed', str(e))

@router.post("/generate")
async def generate_instructions(video: VideoRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'starting', 'message': 'Job started.'}
    background_tasks.add_task(process_video_task, str(video.youtube_url), job_id, video.language)
    return {"job_id": job_id}

@router.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/result/{job_id}")
async def get_result(job_id: str) -> FileResponse:
    job = jobs.get(job_id)
    if not job or job.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="Result not ready or job failed")
    
    pdf_path = job.get('pdf_path')
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
        
    return FileResponse(pdf_path, media_type='application/pdf', filename=f"{job_id}.pdf")

