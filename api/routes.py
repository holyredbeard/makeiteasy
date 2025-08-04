import uuid
import traceback
import logging
from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, BackgroundTasks, Body
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.requests import Request
from models.types import User, RecipeContent, SavedRecipe, Recipe, SaveRecipeRequest, YouTubeVideo, YouTubeSearchRequest, Step
from core.auth import get_current_active_user
from core.database import db
from core.limiter import limiter
from logic.video_processing import (
    download_video,
    transcribe_audio,
    extract_text_from_frames,
    contains_ingredients,
    extract_video_metadata,
    download_thumbnail,
    extract_and_save_frames
)
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import json
import asyncio
from pydantic import BaseModel
import re
import os
import yt_dlp

router = APIRouter()
jobs = {}
logger = logging.getLogger(__name__)

# --- Job Management ---
class Job:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "queued"
        self.details = "Waiting to start..."
        self.pdf_url = None

    def update(self, status: str, details: str):
        self.status = status
        self.details = details
        logger.info(f"[Job {self.job_id}] Status: {status} - {details}")

    def complete(self, pdf_url: str):
        self.status = "completed"
        self.details = "PDF ready for download."
        self.pdf_url = pdf_url
        logger.info(f"[Job {self.job_id}] Completed. PDF at {pdf_url}")

    def fail(self, reason: str):
        self.status = "failed"
        self.details = reason
        logger.error(f"[Job {self.job_id}] Failed: {reason}")

def is_transcript_sufficient(transcript: Optional[str]) -> bool:
    """
    Validerar om en transkribering är tillräckligt bra för att fortsätta.
    Returnerar True om transkriberingen är godkänd, annars False.
    """
    if not transcript or not isinstance(transcript, str):
        logger.warning("[VALIDATION] Ingen transkribering tillgänglig.")
        return False

    # 1. Längdkontroll (grundläggande)
    # En rimlig transkribering bör ha minst 50 tecken.
    if len(transcript.strip()) < 50:
        logger.warning(f"[VALIDATION] Transkribering för kort ({len(transcript.strip())} tecken).")
        return False

    # 2. Kontroll av upprepande mönster (indikerar ofta fel)
    # Ser efter mönster som "....." eller "Thank you for watching..." som upprepas.
    # Denna regex letar efter en kort sekvens av tecken som upprepas många gånger.
    if re.search(r'(.+?)\1{4,}', transcript):
        logger.warning("[VALIDATION] Transkribering innehåller repetitiva mönster.")
        return False

    # 3. Kontroll av nonsens-ord (indikerar ofta dålig ljudkvalitet)
    # Räknar andelen ord som är väldigt korta (mindre än 3 tecken), vilket kan tyda på brus.
    words = transcript.strip().split()
    if len(words) > 10:  # Undvik delning med noll och kör bara på längre texter
        short_words = [word for word in words if len(word) < 3]
        if (len(short_words) / len(words)) > 0.6:  # Mer än 60% korta ord
            logger.warning("[VALIDATION] Transkribering har hög andel korta ord, kan vara brus.")
            return False

    # 4. Sök efter nyckelord relaterade till matlagning (BORTTAGEN)
    # En bra transkribering av ett recept bör innehålla några vanliga matlagningstermer.
    # cooking_keywords = [
    #     'recipe', 'ingredients', 'instructions', 'cup', 'teaspoon', 'tablespoon',
    #     'oven', 'bake', 'cook', 'mix', 'stir', 'fry', 'boil', 'chop', 'slice',
    #     'salt', 'pepper', 'sugar', 'flour', 'water', 'oil', 'onion', 'garlic'
    # ]
    # found_keywords = [word for word in cooking_keywords if word in transcript.lower()]
    # if len(found_keywords) < 2:  # Kräver minst två nyckelord
    #     logger.warning(f"[VALIDATION] Få matlagningsrelaterade nyckelord hittades ({len(found_keywords)} st).")
    #     return False

    logger.info("[VALIDATION] Transkribering bedöms vara tillräcklig.")
    return True

# --- Background Task for PDF Generation ---
async def stream_recipe_generation(video_url: str, language: str, show_top_image: bool, show_step_images: bool):
    job_id = str(uuid.uuid4())

    async def send_event(status: str, message: str = None, recipe: dict = None, is_error: bool = False):
        data = {"status": status, "message": message}
        if recipe:
            data["recipe"] = recipe
        if is_error:
            data["status"] = "error"
        return f"data: {json.dumps(data)}\n\n"

    try:
        yield await send_event("processing", "Extracting video metadata...")
        metadata = await asyncio.to_thread(extract_video_metadata, video_url)
        if not metadata:
            yield await send_event("error", "Could not retrieve video metadata. URL might be invalid.", is_error=True)
            return

        yield await send_event("processing", f'Processing: {metadata.get("title", "video")[:50]}...')
        
        thumbnail_path = await asyncio.to_thread(download_thumbnail, video_url, job_id)
        
        yield await send_event("downloading", "Downloading audio...")
        audio_file_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=True)
        if not audio_file_path:
            yield await send_event("error", "Failed to download audio from video.", is_error=True)
            return

        yield await send_event("transcribing", "Transcribing audio...")
        transcript = await asyncio.to_thread(transcribe_audio, audio_file_path, language)
        transcript = transcript or ""

        final_transcript = transcript
        if not is_transcript_sufficient(transcript):
            yield await send_event("analyzing", "Audio unclear, analyzing video frames for text...")
            video_file_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=False)
            
            frame_paths = []
            if video_file_path:
                # Always extract OCR for recipe text
                ocr_text = await asyncio.to_thread(extract_text_from_frames, video_file_path, job_id)
                
                # Extract frames for images if requested
                if show_step_images:
                    frame_paths = await asyncio.to_thread(extract_and_save_frames, video_file_path, job_id)
                
                if ocr_text:
                    # Combine transcripts manually
                    description = metadata.get('description', '')
                    combined = []
                    if description and len(description) > 50:
                        combined.append(f"Video Description:\n{description}")
                    if ocr_text and len(ocr_text) > 20:
                        combined.append(f"Text found in video (OCR):\n{ocr_text}")
                    if transcript and len(transcript) > 20:
                        combined.append(f"Audio Transcript:\n{transcript}")
                    final_transcript = "\n\n---\n\n".join(combined)
                
                Path(video_file_path).unlink(missing_ok=True)
            else:
                yield await send_event("warning", "Could not download video for frame analysis.")
        
        if len(final_transcript.strip()) < 50:
            yield await send_event("error", "Could not find enough text in the video to create a recipe.", is_error=True)
            return

        yield await send_event("generating_recipe", "Generating recipe with AI...")
        
        # Pass frame_paths to the recipe generator
        recipe_data = await asyncio.to_thread(
            analyze_video_content, 
            final_transcript, 
            language, 
            stream=True, 
            thumbnail_path=thumbnail_path,
            frame_paths=frame_paths
        )

        async for chunk in recipe_data:
            yield await send_event("streaming_recipe", "Receiving recipe data...", recipe=chunk)

        # The analyze_video_content should yield a final 'done' message with the full recipe.
        # Assuming the last chunk is the full recipe.
        
        # Let's get the final recipe from the last yielded data if it's not passed explicitly
        # This part is a bit tricky without knowing the exact output of analyze_video_content
        # For now, let's assume the frontend aggregates the chunks.
        
        yield await send_event("done", "Recipe generation complete.")

    except Exception as e:
        logger.error(f"Error in stream for job {job_id}: {e}\n{traceback.format_exc()}")
        yield await send_event("error", f"An unexpected server error occurred: {e}", is_error=True)
    finally:
        # Cleanup temp files
        if 'audio_file_path' in locals() and audio_file_path: 
            Path(audio_file_path).unlink(missing_ok=True)
        logger.info(f"Stream finished for job {job_id}")

@router.get("/generate-stream")
async def generate_stream_endpoint(video_url: str, language: str = "en", show_top_image: bool = True, show_step_images: bool = True):
    """
    Streams the recipe generation process from a video URL.
    Returns server-sent events with status updates and the final recipe.
    """
    async def stream_recipe_generation(video_url: str, language: str, show_top_image: bool, show_step_images: bool):
        job_id = str(uuid.uuid4())
        
        async def send_event(status: str, message: str = None, recipe: dict = None, is_error: bool = False):
            data = {"status": status, "message": message}
            if recipe:
                data["recipe"] = recipe
            if is_error:
                data["status"] = "error"
            return f"data: {json.dumps(data)}\n\n"
        
        try:
            # Extract metadata
            yield await send_event("processing", "Extracting video metadata...")
            metadata = await asyncio.to_thread(extract_video_metadata, video_url)
            if not metadata:
                yield await send_event("error", "Could not retrieve video metadata. URL might be invalid.", is_error=True)
                return
                
            yield await send_event("processing", f'Processing: {metadata.get("title", "video")[:50]}...')
            
            thumbnail_path = await asyncio.to_thread(download_thumbnail, video_url, job_id)
            
            # Download audio
            yield await send_event("downloading", "Downloading audio...")
            audio_path = await asyncio.to_thread(
                download_video, 
                video_url=video_url, 
                job_id=job_id, 
                audio_only=True
            )
            
            frame_paths = []
            text_for_analysis = ""

            if audio_path:
                # Transcribe audio
                yield await send_event("transcribing", "Transcribing audio...")
                transcript = await asyncio.to_thread(transcribe_audio, audio_path, job_id, language)
                
                if is_transcript_sufficient(transcript):
                    description = metadata.get("description", "")
                    text_for_analysis = f"Video Title: {metadata.get('title', '')}\n\n"
                    if description:
                        text_for_analysis += f"Video Description: {description}\n\n"
                    text_for_analysis += f"Transcript: {transcript}"
                else:
                    yield await send_event("processing", "Audio transcription insufficient. Trying video frames...")
                    audio_path = None # Force video download path

            if not audio_path:
                # Try video download if audio failed or was insufficient
                video_path = await asyncio.to_thread(
                    download_video, 
                    video_url=video_url, 
                    job_id=job_id, 
                    audio_only=False
                )
                
                if not video_path:
                    yield await send_event("error", "Failed to download video content.", is_error=True)
                    return
                
                if show_step_images:
                    frame_paths = await asyncio.to_thread(extract_and_save_frames, video_path, job_id)
                    
                # Extract text from video frames
                yield await send_event("processing", "Analyzing video frames...")
                ocr_text = await asyncio.to_thread(extract_text_from_frames, video_path, job_id)
                
                # Use video description if OCR fails
                if not ocr_text or len(ocr_text) < 50:
                    description = metadata.get("description", "")
                    if len(description) > 100:
                        yield await send_event("processing", "Using video description...")
                        text_for_analysis = description
                    else:
                        yield await send_event("error", "Could not extract enough text from the video.", is_error=True)
                        return
                else:
                    text_for_analysis = ocr_text

            # Generate recipe
            yield await send_event("generating", "Generating recipe with AI...")
            
            # Process with AI
            recipe_generator = analyze_video_content(text_for_analysis, language, stream=True, thumbnail_path=thumbnail_path, frame_paths=frame_paths)
            async for recipe_data in recipe_generator:
                if "error" in recipe_data:
                    yield await send_event("error", recipe_data["error"], is_error=True)
                    return
                else:
                    # Send the complete recipe
                    yield await send_event("done", "Recipe generation complete!", recipe=recipe_data)
                    logger.info(f"Stream finished for job {job_id}")
                    return
                    
        except Exception as e:
            logger.error(f"Error in stream: {str(e)}")
            yield await send_event("error", f"An error occurred: {str(e)}", is_error=True)
    
    return StreamingResponse(stream_recipe_generation(video_url, language, show_top_image, show_step_images), media_type="text/event-stream")

@router.post("/generate-pdf")
@limiter.limit("10/minute")
async def generate_pdf_endpoint(request: Request, recipe_content: RecipeContent):
    """
    Generates a PDF from the provided recipe content.
    """
    try:
        job_id = str(uuid.uuid4())
        
        # Import the convert_recipe_content_to_recipe function from pdf_generator
        from logic.pdf_generator import convert_recipe_content_to_recipe
        
        recipe_for_pdf = await convert_recipe_content_to_recipe(recipe_content)

        # Get template parameters from request if available
        template_name = getattr(recipe_content, 'template_name', "modern")
        image_orientation = getattr(recipe_content, 'image_orientation', "landscape")
        show_top_image = getattr(recipe_content, 'show_top_image', True)
        show_step_images = getattr(recipe_content, 'show_step_images', True)
        
        pdf_path = await asyncio.to_thread(
            generate_pdf,
            recipe=recipe_for_pdf,
            job_id=job_id,
            template_name=template_name,
            video_title=recipe_for_pdf.title,
            show_top_image=show_top_image,
            show_step_images=show_step_images,
            language=getattr(recipe_content, 'language', 'en')
        )

        if not Path(pdf_path).exists():
            raise HTTPException(status_code=500, detail="PDF file was not created.")

        return FileResponse(
            path=pdf_path,
            filename=f"{recipe_content.title.replace(' ', '_')}.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# --- API Endpoints ---

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "status": job.status, "details": job.details, "pdf_url": job.pdf_url}

@router.get("/usage-status", tags=["Usage"])
@limiter.limit("20/minute")
async def check_usage_status(request: Request, current_user: User = Depends(get_current_active_user)):
    # This remains as is
    pass

@router.post("/recipes/save", response_model=SavedRecipe, tags=["Recipes"])
@limiter.limit("30/minute")
async def save_user_recipe(request: Request, payload: SaveRecipeRequest, current_user: User = Depends(get_current_active_user)):
    # This remains as is
    pass

@router.get("/recipes", response_model=List[SavedRecipe], tags=["Recipes"])
@limiter.limit("60/minute")
async def get_user_recipes(request: Request, current_user: User = Depends(get_current_active_user)):
    # This remains as is
    pass

@router.post("/search")
@limiter.limit("20/minute")
async def search_videos(request: Request, search_request: YouTubeSearchRequest = Body(...)):
    """Search for videos and return a list of results."""
    query = search_request.query
    page = search_request.page
    results_per_page = 10
    
    # TikTok search is currently not supported by yt-dlp's search functionality
    source = search_request.source or 'youtube'

    if "recipe" not in query.lower():
        query = f"{query} recipe"

    try:
        # Fetch a larger batch of results at once to support pagination without re-searching
        search_prefix = f"ytsearch{page * results_per_page}:"
        search_query = f"{search_prefix}{query}"

        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(search_query, download=False)
            
            if not results or 'entries' not in results:
                logger.warning(f"No search results for query '{query}'")
                return JSONResponse(content={"results": []})
                
            videos = []
            for entry in results['entries']:
                if not entry:
                    continue
                    
                video_id = entry.get('id')
                title = entry.get('title', 'Unknown Title')
                channel = entry.get('channel', 'Unknown Channel')
                # Skapa en thumbnail URL baserat på video-ID
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                
                videos.append(YouTubeVideo(
                    video_id=video_id,
                    title=title,
                    channel_title=channel,
                    thumbnail_url=thumbnail,
                    duration="",  # Not available in extract_flat mode
                    view_count="",  # Not available in extract_flat mode
                    published_at=None,
                    description=None
                ))
            
            unique_videos = {v.video_id: v for v in videos}.values()
            
            # Paginate the results
            start_index = (page - 1) * results_per_page
            end_index = start_index + results_per_page
            paginated_results = list(unique_videos)[start_index:end_index]
            
            return JSONResponse(content={"results": [v.dict() for v in paginated_results]})

    except Exception as e:
        logger.error(f"General search failed for query '{query}' on source '{source}': {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
