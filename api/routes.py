import uuid
import traceback
import logging
from typing import Optional, Union
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from models.types import VideoRequest, Recipe, YouTubeSearchRequest, YouTubeVideo, User
from core.auth import get_current_active_user
from core.database import db
from logic.video_processing import (
    download_video,
    transcribe_audio,
    extract_text_from_frames,
    contains_ingredients,
    smart_frame_selection,
    get_video_duration,
    extract_thumbnail
)
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import os
import time
from datetime import datetime
from models.types import Step
import glob
import yt_dlp

# --- Globals ---
router = APIRouter()
jobs = {}
logger = logging.getLogger(__name__)

# Rate limiting for non-authenticated users
ip_usage = {}  # {ip: {"count": int, "last_reset": timestamp}}
DAILY_LIMIT_NO_AUTH = 2  # 2 PDFs per day without account
TEMP_PDF_LIFETIME = 24 * 3600  # 24 hours in seconds

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

def check_rate_limit(client_ip: str) -> bool:
    """Check if IP has exceeded daily limit for non-authenticated users"""
    current_time = time.time()
    
    if client_ip not in ip_usage:
        ip_usage[client_ip] = {"count": 0, "last_reset": current_time}
        return True
    
    # Reset count if it's a new day (24 hours)
    if current_time - ip_usage[client_ip]["last_reset"] > 24 * 3600:
        ip_usage[client_ip] = {"count": 0, "last_reset": current_time}
    
    return ip_usage[client_ip]["count"] < DAILY_LIMIT_NO_AUTH

def increment_ip_usage(client_ip: str):
    """Increment usage count for IP"""
    current_time = time.time()
    if client_ip not in ip_usage:
        ip_usage[client_ip] = {"count": 1, "last_reset": current_time}
    else:
        ip_usage[client_ip]["count"] += 1

def get_optional_user(request: Request) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    try:
        # Try to get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        # Import here to avoid circular imports
        from core.auth import verify_token
        
        token = auth_header.split(" ")[1]
        token_data = verify_token(token)
        if not token_data or not token_data.email:
            return None
        
        user = db.get_user_by_email(token_data.email)
        if not user:
            return None
        
        # Convert UserInDB to User
        return User(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at
        )
    except Exception:
        return None

# --- API Endpoints ---
@router.post("/generate", summary="Process a video to generate a recipe PDF")
async def generate_endpoint(video_request: VideoRequest, background_tasks: BackgroundTasks, request: Request):
    # Check if user is authenticated
    current_user = get_optional_user(request)
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limiting for non-authenticated users
    if not current_user:
        if not check_rate_limit(client_ip):
            remaining_time = 24 * 3600 - (time.time() - ip_usage[client_ip]["last_reset"])
            hours_left = int(remaining_time // 3600)
            raise HTTPException(
                status_code=429, 
                detail=f"Daily limit reached. You can create {DAILY_LIMIT_NO_AUTH} PDFs per day without an account. "
                       f"Try again in {hours_left} hours or create a free account for unlimited access."
            )
        increment_ip_usage(client_ip)
    
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    video_url = str(video_request.youtube_url)
    language = video_request.language or "en"
    
    update_job_status(job_id, "processing", "Job has been received and is scheduled to start.")

    def process_video_task(job_id: str, video_url: str, language: str, user_id: Optional[int]):
        try:
            # 1. Download Video
            # Detect platform for better user messaging
            if "tiktok.com" in video_url.lower():
                platform = "TikTok"
            elif "youtube.com" in video_url.lower() or "youtu.be" in video_url.lower():
                platform = "YouTube"
            else:
                platform = "video"
            
            update_status(job_id, "processing", f"Downloading video from {platform}...")
            download_result = download_video(video_url, job_id)
            if isinstance(download_result, tuple) and len(download_result) == 3:
                video_path, video_title, metadata = download_result
            elif isinstance(download_result, tuple) and len(download_result) == 2:
                video_path, video_title = download_result
                metadata = {'title': 'Unknown Title', 'description': '', 'is_recipe_description': False}
            else:
                video_path = download_result
                video_title = None
                metadata = {'title': 'Unknown Title', 'description': '', 'is_recipe_description': False}
            
            if not video_path:
                raise ValueError("Failed to download video. Please check the URL and try again.")

            # 2. Extract Text (Smart approach)
            update_status(job_id, "transcribing", "Extracting text from audio...")
            
            # Get text from audio first (Whisper)
            audio_transcript = transcribe_audio(video_path, job_id)
            
            # Check if audio transcript is good enough
            transcript = audio_transcript or ""
            
            # Run OCR if audio transcript is poor, empty, or lacks ingredients
            ocr_text = ""
            if not transcript.strip() or len(transcript.strip()) < 50 or "theatre這裡doesmos" in transcript or not contains_ingredients(transcript):
                update_status(job_id, "transcribing", "Audio unclear or lacks ingredients, extracting text from images...")
                ocr_text = extract_text_from_frames(video_path, job_id)
                if ocr_text:
                    transcript = f"Audio transcript:\n{audio_transcript or 'No clear audio'}\n\nText from images:\n{ocr_text}"
                else:
                    transcript = f"Audio transcript:\n{audio_transcript or 'No clear audio'}"
            
            if not transcript.strip():
                raise ValueError("Failed to extract any text from video (neither audio nor visual text found).")
            
            # 3. Analyze Content
            update_status(job_id, "analyzing", "Analyzing content...")
            recipe = analyze_video_content(
                transcript, 
                language, 
                metadata.get('description', ''), 
                metadata.get('is_recipe_description', False),
                ocr_text
            )
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
                update_status(job_id, "frames", f"Creating step {i+1}...")
                success = smart_frame_selection(video_path, step, job_id, video_duration, total_steps)
                if not success:
                    logger.warning(f"Could not find a suitable frame for step {step.step_number} in job {job_id}.")
            
            # 6. Generate PDF
            update_status(job_id, "generating_pdf", "Generating PDF instructions...")
            pdf_path = generate_pdf(recipe, job_id, template_name="professional", video_url=video_url, video_title=video_title)
            if not pdf_path:
                raise ValueError("Failed to generate PDF.")

            # 7. Link PDF to user (only if user is logged in)
            if user_id:
                db.link_pdf_to_user(user_id, job_id, pdf_path)

            # 8. Complete Job
            update_status(job_id, "completed", "Job finished successfully!", pdf_url=f"/api/v1/result/{job_id}")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            update_status(job_id, "failed", f"An error occurred: {e}")

    background_tasks.add_task(process_video_task, job_id, video_url, language, current_user.id if current_user else None)
    
    return JSONResponse(status_code=202, content={
        "job_id": job_id, 
        "session_id": session_id,
        "status": "processing", 
        "details": "Job started."
    })

@router.get("/usage-status", summary="Get current usage status for anonymous users")
async def get_usage_status(request: Request):
    """Get remaining usage for non-authenticated users"""
    client_ip = request.client.host if request.client else "unknown"
    current_user = get_optional_user(request)
    
    if current_user:
        # Authenticated users have unlimited usage
        return {
            "is_authenticated": True,
            "remaining_usage": -1,  # -1 means unlimited
            "daily_limit": -1,
            "message": "Unlimited usage with account"
        }
    else:
        # Non-authenticated users have limited usage
        remaining = DAILY_LIMIT_NO_AUTH
        if client_ip in ip_usage:
            current_time = time.time()
            # Reset count if it's a new day (24 hours)
            if current_time - ip_usage[client_ip]["last_reset"] > 24 * 3600:
                ip_usage[client_ip] = {"count": 0, "last_reset": current_time}
            remaining = max(0, DAILY_LIMIT_NO_AUTH - ip_usage[client_ip]["count"])
        
        return {
            "is_authenticated": False,
            "remaining_usage": remaining,
            "daily_limit": DAILY_LIMIT_NO_AUTH,
            "message": f"You can create {remaining} more PDFs today without an account"
        }

@router.post("/reset", summary="Reset IP rate limiting (temporary admin function)")
async def reset_rate_limiting(request: Request):
    """Reset rate limiting for the current IP address"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Clear the IP from rate limiting
    if client_ip in ip_usage:
        del ip_usage[client_ip]
        logger.info(f"Rate limiting reset for IP: {client_ip}")
        return {"message": f"Rate limiting reset for IP {client_ip}", "ip": client_ip}
    else:
        return {"message": f"No rate limiting data found for IP {client_ip}", "ip": client_ip}

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
async def get_result(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet.")
    
    # Look for PDF files in the output directory that match the job_id
    output_dir = Path("output")
    pdf_files = list(output_dir.glob(f"*{job_id}*.pdf")) + list(output_dir.glob(f"{job_id}.pdf"))
    
    if not pdf_files:
        # Try to find any PDF file that might have been generated with video title
        pdf_files = list(output_dir.glob("*-recipe-guide.pdf"))
        if pdf_files:
            # Sort by modification time to get the most recent one
            pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF file not found.")
    
    pdf_path = pdf_files[0]  # Use the first (most recent) matching file
    
    # Extract filename for download
    download_filename = pdf_path.name
    
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=download_filename)

@router.post("/search", summary="Search for videos on YouTube or TikTok")
async def search_videos(request: YouTubeSearchRequest):
    """Search for videos and return a list of results."""
    query = request.query
    source = request.source or 'youtube'

    if "recipe" not in query.lower():
        query = f"{query} recipe"

    try:
        search_prefix = "ytsearch10:" if source == 'youtube' else "tiktoksearch10:"
        search_query = f"{search_prefix}{query}"

        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # Speeds up search
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(search_query, download=False)
            
            videos = []
            if 'entries' in search_results:
                for entry in search_results.get('entries', []):
                    if not entry:
                        continue
                    
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    
                    # Robust thumbnail extraction
                    thumb = entry.get('thumbnail')
                    if not thumb and entry.get('thumbnails'):
                        thumb = entry['thumbnails'][-1].get('url')

                    videos.append(YouTubeVideo(
                        video_id=video_id,
                        title=entry.get('title', 'No Title'),
                        thumbnail_url=thumb,
                        channel_title=entry.get('uploader', 'Unknown Channel'),
                        duration=str(entry.get('duration', 0)),
                        view_count=str(entry.get('view_count', 0)),
                        published_at=entry.get('upload_date'),
                        description=entry.get('description')
                    ))
            
            unique_videos = {v.video_id: v for v in videos}.values()
            return JSONResponse(content={"results": [v.dict() for v in list(unique_videos)[:10]]})

    except Exception as e:
        logger.error(f"Search failed for query '{query}' on source '{source}': {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during the search: {str(e)}"
        )

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
        download_result = download_video(video_url, job_id)
        if isinstance(download_result, tuple) and len(download_result) == 3:
            video_path, video_title, metadata = download_result
        elif isinstance(download_result, tuple) and len(download_result) == 2:
            video_path, video_title = download_result
            metadata = {'title': 'Unknown Title', 'description': '', 'is_recipe_description': False}
        else:
            video_path = download_result
            metadata = {'title': 'Unknown Title', 'description': '', 'is_recipe_description': False}
        
        if not video_path:
            raise ValueError("Failed to download video.")

        # 2. Extract Text (Smart approach)
        logger.info(f"[{job_id}] Step 2/6: Extracting text from audio...")
        
        # Get text from audio first (Whisper)
        audio_transcript = transcribe_audio(video_path, job_id)
        
        # Check if audio transcript is good enough
        transcript = audio_transcript or ""
        
        # Run OCR if audio transcript is poor, empty, or lacks ingredients
        ocr_text = ""
        if not transcript.strip() or len(transcript.strip()) < 50 or "theatre這裡doesmos" in transcript or not contains_ingredients(transcript):
            logger.info(f"[{job_id}] Audio unclear or lacks ingredients, extracting text from images...")
            ocr_text = extract_text_from_frames(video_path, job_id)
            if ocr_text:
                transcript = f"Audio transcript:\n{audio_transcript or 'No clear audio'}\n\nText from images:\n{ocr_text}"
            else:
                transcript = f"Audio transcript:\n{audio_transcript or 'No clear audio'}"
        
        if not transcript.strip():
            raise ValueError("Failed to extract any text from video (neither audio nor visual text found).")
        
        # 3. Analyze Content
        logger.info(f"[{job_id}] Step 3/6: Analyzing recipe content...")
        recipe = analyze_video_content(
            transcript, 
            language, 
            metadata.get('description', ''), 
            metadata.get('is_recipe_description', False),
            ocr_text
        )
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
            logger.info(f"[{job_id}] Creating step {i+1}/{total_steps}...")
            success = smart_frame_selection(video_path, step, job_id, video_duration, total_steps)
            if not success:
                logger.warning(f"[{job_id}] Could not find frame for step {step.step_number}.")
        
        # 6. Generate PDF
        logger.info(f"[{job_id}] Step 6/6: Generating final PDF...")
        pdf_path = generate_pdf(recipe, job_id, template_name="professional", video_url=video_url)
        if not pdf_path:
            raise ValueError("Failed to generate PDF.")

        logger.info(f"[{job_id}] Job finished successfully! PDF at {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"[{job_id}] Error processing job: {e}", exc_info=True)
        return None

@router.post("/test-pdf")
async def generate_test_pdf(
    template_name: str = Form(..., description="CSS template name (default, modern, professional)"),
    image_orientation: str = Form(..., description="Image orientation (landscape, portrait)"),
    current_user: User = Depends(get_current_active_user)
):
    """Generate a test PDF with predefined data and test images"""
    
    # Check if user is admin
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=403, # Changed from status.HTTP_403_FORBIDDEN to 403
            detail="Admin access required"
        )
    
    try:
        # Create test recipe data
        test_recipe = Recipe(
            title="Test Recipe - Layout Preview",
            description="This is a test recipe to preview the PDF layout and styling.",
            serves="4 people",
            prep_time="15 minutes",
            cook_time="30 minutes",
            ingredients=[
                "2 cups flour",
                "1 cup sugar",
                "3 eggs",
                "1/2 cup butter",
                "1 tsp vanilla extract",
                "1 cup milk",
                "2 tsp baking powder"
            ],
            steps=[
                Step(
                    step_number=1,
                    description="Preheat your oven to 350°F (175°C). Grease and flour a 9-inch round cake pan.",
                    image_path=f"static/test_images/test_{image_orientation}.jpg"
                ),
                Step(
                    step_number=2,
                    description="In a large bowl, cream together the butter and sugar until light and fluffy. Beat in eggs one at a time, then stir in vanilla.",
                    image_path=f"static/test_images/test_{image_orientation}.jpg"
                ),
                Step(
                    step_number=3,
                    description="Combine flour and baking powder in a separate bowl. Gradually add to creamed mixture alternately with milk, beating well after each addition.",
                    image_path=f"static/test_images/test_{image_orientation}.jpg"
                ),
                Step(
                    step_number=4,
                    description="Pour batter into prepared pan. Bake for 30-35 minutes or until a toothpick inserted in center comes out clean.",
                    image_path=f"static/test_images/test_{image_orientation}.jpg"
                ),
                Step(
                    step_number=5,
                    description="Cool in pan for 10 minutes before removing to wire rack. Serve warm or at room temperature.",
                    image_path=f"static/test_images/test_{image_orientation}.jpg"
                )
            ],
            thumbnail_path=f"static/test_images/test_{image_orientation}.jpg"
        )
        
        # Generate unique job ID for test
        job_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{image_orientation}"
        
        # Create PDF using the existing PDF generator
        pdf_path = generate_pdf(
            recipe=test_recipe,
            job_id=job_id,
            template_name=template_name
        )
        
        # Return the PDF file
        if os.path.exists(pdf_path):
            return FileResponse(
                path=pdf_path,
                media_type='application/pdf',
                filename=f"test-{template_name}-{image_orientation}.pdf"
            )
        else:
            raise HTTPException(
                status_code=500, # Changed from status.HTTP_500_INTERNAL_SERVER_ERROR to 500
                detail="Failed to generate test PDF"
            )
            
    except Exception as e:
        logger.error(f"Error generating test PDF: {str(e)}")
        raise HTTPException(
            status_code=500, # Changed from status.HTTP_500_INTERNAL_SERVER_ERROR to 500
            detail=f"Failed to generate test PDF: {str(e)}"
        )

@router.get("/templates")
async def get_pdf_templates(current_user: User = Depends(get_current_active_user)):
    """Get list of available PDF templates"""
    
    # Check if user is admin
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=403, # Changed from status.HTTP_403_FORBIDDEN to 403
            detail="Admin access required"
        )
    
    try:
        templates_dir = "static/templates/pdf"
        templates = []
        
        if os.path.exists(templates_dir):
            for file in os.listdir(templates_dir):
                if file.endswith('.css'):
                    template_name = file.replace('.css', '')
                    templates.append(template_name)
        
        return {"templates": templates}
        
    except Exception as e:
        logger.error(f"Error getting templates: {str(e)}")
        raise HTTPException(
            status_code=500, # Changed from status.HTTP_500_INTERNAL_SERVER_ERROR to 500
            detail=f"Failed to get templates: {str(e)}"
        )

