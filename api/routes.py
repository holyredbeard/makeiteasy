import uuid
import traceback
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from models.types import VideoRequest, Recipe, YouTubeSearchRequest, YouTubeVideo
from logic.video_processing import (
    download_video,
    transcribe_audio,
    smart_frame_selection,
    get_video_duration,
    extract_thumbnail
)
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import os

# --- Globals ---
router = APIRouter()
jobs = {}
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def update_job_status(job_id: str, status: str, details: str, pdf_url: Optional[str] = None):
    """Update the status of a job."""
    jobs[job_id] = {"status": status, "details": details}
    if pdf_url:
        jobs[job_id]["pdf_url"] = pdf_url
    logger.info(f"Job {job_id} status updated: {status} - {details}")

def update_status(job_id: str, status: str, details: str, pdf_url: Optional[str] = None):
    """Update the status of a job (alias for compatibility)."""
    update_job_status(job_id, status, details, pdf_url)

# --- API Endpoints ---
@router.post("/generate", summary="Process a video to generate a recipe PDF")
async def generate_endpoint(request: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    video_url = str(request.youtube_url)
    language = request.language or "en"
    
    update_job_status(job_id, "processing", "Job has been received and is scheduled to start.")

    def process_video_task(job_id: str, video_url: str, language: str):
        try:
            # 1. Download Video
            update_status(job_id, "processing", "Downloading video from YouTube...")
            video_path = download_video(video_url, job_id)
            if not video_path:
                raise ValueError("Failed to download video. Please check the URL and try again.")

            # 2. Transcribe Video
            update_status(job_id, "transcribing", "Transcribing audio content...")
            transcript = transcribe_audio(video_path, job_id)
            if not transcript:
                raise ValueError("Failed to transcribe video. The video may not contain speech.")
            
            # 3. Analyze Content
            update_status(job_id, "analyzing", "Analyzing content with AI...")
            recipe = analyze_video_content(transcript, language)
            if not recipe:
                raise Exception("Failed to analyze video content.")
            
            # 4. Extract Thumbnail
            thumbnail_path = extract_thumbnail(video_path, job_id)
            if thumbnail_path:
                recipe.thumbnail_path = thumbnail_path

            # 5. Extract Step Images
            update_status(job_id, "extracting_frames", "Extracting key frames...")
            total_steps = len(recipe.steps)
            video_duration = get_video_duration(video_path)

            for i, step in enumerate(recipe.steps):
                update_status(job_id, "frames", f"Processing frame {i+1}...")
                success = smart_frame_selection(video_path, step, job_id, video_duration, total_steps)
                if not success:
                    logger.warning(f"Could not find a suitable frame for step {step.step_number} in job {job_id}.")
            
            # 6. Generate PDF
            update_status(job_id, "generating_pdf", "Generating PDF instructions...")
            pdf_path = generate_pdf(recipe, job_id, template_name="professional")
            if not pdf_path:
                raise ValueError("Failed to generate PDF.")

            # 7. Complete Job
            update_status(job_id, "completed", "Job finished successfully!", pdf_url=f"/result/{job_id}")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            update_status(job_id, "failed", f"An error occurred: {e}")

    background_tasks.add_task(process_video_task, job_id, video_url, language)
    
    return JSONResponse(status_code=202, content={
        "job_id": job_id, 
        "session_id": session_id,
        "status": "processing", 
        "details": "Job started."
    })

@router.get("/status/{job_id}", summary="Get the status of a processing job")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    response = {
        "job_id": job_id, 
        "status": job.get("status"), 
        "details": job.get("details"),
        "logs": []  # Add empty logs array for compatibility
    }
    if "pdf_url" in job:
        response["pdf_url"] = job.get("pdf_url")
        
    return JSONResponse(content=response)

@router.get("/result/{job_id}", summary="Download the generated PDF")
async def get_result(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet.")
    
    pdf_path = f"output/{job_id}.pdf"
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found.")
    
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"recipe_{job_id}.pdf")

@router.post("/search", summary="Search YouTube for videos")
async def search_youtube(request: YouTubeSearchRequest):
    # Mock search results for now
    mock_videos = [
        YouTubeVideo(
            video_id="dQw4w9WgXcQ",
            title="Test Recipe Video",
            channel_title="Test Channel",
            thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
            duration="5:30",
            view_count="1M views",
            published_at="1 day ago",
            description="A test recipe video for demonstration purposes."
        )
    ]
    
    return JSONResponse(content={"videos": [video.dict() for video in mock_videos]})

# Legacy endpoint for compatibility
@router.post("/process-video/", summary="Process a video to generate a recipe PDF (legacy)")
async def process_video_endpoint(request: VideoRequest, background_tasks: BackgroundTasks):
    return await generate_endpoint(request, background_tasks)

async def process_video_request(request: VideoRequest):
    job_id = request.job_id or str(uuid.uuid4())
    video_url = str(request.youtube_url)
    language = request.language or "en"
    
    try:
        # 1. Download Video
        logger.info(f"[{job_id}] Step 1/6: Downloading video...")
        video_path = download_video(video_url, job_id)
        if not video_path:
            raise ValueError("Failed to download video.")

        # 2. Transcribe Video
        logger.info(f"[{job_id}] Step 2/6: Transcribing video...")
        transcript = transcribe_audio(video_path, job_id)
        if not transcript:
            raise ValueError("Failed to transcribe video.")
        
        # 3. Analyze Content
        logger.info(f"[{job_id}] Step 3/6: Analyzing recipe content...")
        recipe = analyze_video_content(transcript, language)
        if not recipe:
            raise ValueError("Failed to analyze video content.")
        
        # 4. Extract Thumbnail
        logger.info(f"[{job_id}] Step 4/6: Extracting thumbnail...")
        thumbnail_path = extract_thumbnail(video_path, job_id)
        if thumbnail_path:
            recipe.thumbnail_path = thumbnail_path
        else:
            logger.warning(f"[{job_id}] Could not extract thumbnail. A placeholder will be used.")

        # 5. Extract Step Images
        logger.info(f"[{job_id}] Step 5/6: Extracting step images...")
        total_steps = len(recipe.steps)
        video_duration = get_video_duration(video_path)

        for i, step in enumerate(recipe.steps):
            logger.info(f"[{job_id}] Processing step {i+1}/{total_steps}...")
            success = smart_frame_selection(video_path, step, job_id, video_duration, total_steps)
            if not success:
                logger.warning(f"[{job_id}] Could not find frame for step {step.step_number}.")
        
        # 6. Generate PDF
        logger.info(f"[{job_id}] Step 6/6: Generating final PDF...")
        pdf_path = generate_pdf(recipe, job_id, template_name="professional")
        if not pdf_path:
            raise ValueError("Failed to generate PDF.")

        logger.info(f"[{job_id}] Job finished successfully! PDF at {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"[{job_id}] Error processing job: {e}", exc_info=True)
        return None

