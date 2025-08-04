import uuid
import traceback
import logging
import requests
import tempfile
import time
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

@router.get("/generate-stream")
async def generate_stream_endpoint(request: Request, video_url: str, language: str = "en", show_top_image: bool = True, show_step_images: bool = True):
    job_id = str(uuid.uuid4())
    base_url = str(request.base_url)

    async def send_event(status: str, message: str = None, recipe: dict = None, is_error: bool = False, debug_info: dict = None):
        data = {"status": status, "message": message, "timestamp": int(time.time() * 1000)}
        if recipe: data["recipe"] = recipe
        if is_error: data["status"] = "error"
        if debug_info: data["debug_info"] = debug_info
        
        # Logga alltid vad som skickas till frontend
        log_message = f"Sending to frontend: {status}"
        if message: log_message += f" - {message}"
        logger.info(f"[FRONTEND_EVENT] {log_message}", extra={"data": data})
        
        return f"data: {json.dumps(data)}\n\n"

    async def generator():
        temp_files = []
        thumbnail_url = None
        try:
            logger.info(f"[JOB {job_id}] ===== STARTAR RECEPTGENERERING =====")
            logger.info(f"[JOB {job_id}] Video URL: {video_url}")
            logger.info(f"[JOB {job_id}] Språk: {language}")
            logger.info(f"[JOB {job_id}] Visa toppbild: {show_top_image}")
            logger.info(f"[JOB {job_id}] Visa stegbilder: {show_step_images}")
            
            # Metadata and Thumbnail
            yield await send_event("processing", "Extracting video metadata...", debug_info={"step": "metadata_extraction", "job_id": job_id})
            logger.info(f"[JOB {job_id}] Extraherar metadata...")
            
            metadata = await asyncio.to_thread(extract_video_metadata, video_url)
            if not metadata:
                logger.error(f"[JOB {job_id}] Misslyckades att hämta metadata")
                yield await send_event("error", "Could not retrieve video metadata.", is_error=True, debug_info={"step": "metadata_extraction", "error": "no_metadata"})
                return
                
            logger.info(f"[JOB {job_id}] Metadata hämtad: {metadata.get('title', 'Okänd titel')[:100]}")
            yield await send_event("processing", f'Processing: {metadata.get("title", "video")[:50]}...', debug_info={"metadata": metadata})
            if show_top_image:
                logger.info(f"[JOB {job_id}] Laddar ner thumbnail...")
                yield await send_event("processing", "Downloading thumbnail...", debug_info={"step": "thumbnail_download"})
                thumbnail_path = await asyncio.to_thread(download_thumbnail, video_url, job_id)
                if thumbnail_path:
                    temp_files.append(thumbnail_path)
                    thumbnail_url = f"{base_url.strip('/')}/{thumbnail_path.strip('/')}"
                    logger.info(f"[JOB {job_id}] Thumbnail nedladdad: {thumbnail_url}")
                else:
                    logger.warn(f"[JOB {job_id}] Kunde inte ladda ner thumbnail")
            else:
                logger.info(f"[JOB {job_id}] Hoppar över thumbnail (show_top_image=False)")

            # Content Extraction
            logger.info(f"[JOB {job_id}] ===== CONTENT EXTRACTION PHASE =====")
            text_for_analysis, frame_paths = "", []
            description = metadata.get("description", "")
            description_length = len(description) if description else 0
            
            logger.info(f"[JOB {job_id}] Videobeskrivning längd: {description_length} tecken")
            
            if contains_ingredients(description):
                logger.info(f"[JOB {job_id}] ✅ Beskrivning innehåller ingredienser - använder den direkt")
                yield await send_event("processing", "Description contains recipe. Using it.", debug_info={"step": "using_description", "description_length": description_length})
                text_for_analysis = description
            else:
                logger.info(f"[JOB {job_id}] ❌ Beskrivning innehåller inte ingredienser - använder ljud/video")
                yield await send_event("downloading", "Downloading audio...", debug_info={"step": "audio_download"})
                logger.info(f"[JOB {job_id}] Laddar ner ljud...")
                
                audio_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=True)
                if audio_path:
                    temp_files.append(audio_path)
                    logger.info(f"[JOB {job_id}] Ljud nedladdat: {audio_path}")
                    
                    yield await send_event("transcribing", "Transcribing audio...", debug_info={"step": "transcription", "audio_file": audio_path})
                    logger.info(f"[JOB {job_id}] Transkriberar ljud...")
                    
                    transcript = await asyncio.to_thread(transcribe_audio, audio_path, job_id, language)
                    transcript_length = len(transcript) if transcript else 0
                    logger.info(f"[JOB {job_id}] Transkription klar: {transcript_length} tecken")
                    
                    if is_transcript_sufficient(transcript):
                        logger.info(f"[JOB {job_id}] ✅ Transkription godkänd")
                        text_for_analysis = f"Title: {metadata.get('title', '')}\nDescription: {description}\nTranscript: {transcript}"
                    else:
                        logger.warn(f"[JOB {job_id}] ❌ Transkription otillräcklig - behöver video")
                if not text_for_analysis:
                     yield await send_event("warning", "Audio analysis insufficient. Switching to video.")
                     yield await send_event("downloading", "Downloading video...")
                     video_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=False)
                     if not video_path:
                         yield await send_event("error", "Failed to download video.", is_error=True)
                         return
                     temp_files.append(video_path)
                     yield await send_event("analyzing", "Analyzing video frames...")
                     ocr_text = await asyncio.to_thread(extract_text_from_frames, video_path, job_id)
                     text_for_analysis = ocr_text or ""
                     if show_step_images:
                         yield await send_event("processing", "Extracting key frames...")
                         frame_paths = await asyncio.to_thread(extract_and_save_frames, video_path, job_id)
                         temp_files.extend(frame_paths)
            
            if len(text_for_analysis.strip()) < 100:
                yield await send_event("error", "Could not extract enough information for a recipe.", is_error=True)
                return

            # AI Generation with detailed status updates
            logger.info(f"[JOB {job_id}] Starting recipe generation with status updates")
            yield await send_event("generating", "Starting AI recipe generation...")
            
            # Create a task for the recipe generation
            logger.info(f"[JOB {job_id}] Creating async task for analyze_video_content")
            recipe_task = asyncio.create_task(
                analyze_video_content(
                    text_for_analysis, 
                    language, 
                    stream=False,  # We want the complete recipe
                    thumbnail_path=thumbnail_url if show_top_image else None,
                    frame_paths=[f"{base_url.strip('/')}/{p.strip('/')}" for p in frame_paths] if frame_paths else None
                )
            )
            logger.info(f"[JOB {job_id}] Async task created, will now send status updates while waiting")
            
            # Send status updates while waiting for the recipe
            status_steps = [
                {"status": "analyzing", "message": "Analyzing ingredients..."},
                {"status": "generating", "message": "Creating recipe structure..."},
                {"status": "generating", "message": "Generating title..."},
                {"status": "generating", "message": "Creating ingredient list..."},
                {"status": "generating", "message": "Writing cooking instructions..."},
                {"status": "generating", "message": "Adding chef tips..."},
                {"status": "generating", "message": "Finalizing recipe..."}
            ]
            
            for i, step in enumerate(status_steps):
                # Check if recipe is done
                if recipe_task.done():
                    logger.info(f"[JOB {job_id}] Recipe task completed before all status steps were shown")
                    break
                    
                # Send status update and wait a bit
                logger.info(f"[JOB {job_id}] Sending status update {i+1}/{len(status_steps)}: {step['status']} - {step['message']}")
                yield await send_event(step["status"], step["message"])
                await asyncio.sleep(1.5)  # Wait between status updates
                
                # If recipe still not done, send a keep-alive
                if not recipe_task.done():
                    logger.info(f"[JOB {job_id}] Recipe still processing, sending keep-alive for step {i+1}")
                    yield await send_event(step["status"], f"{step['message']} (still working...)")
                    await asyncio.sleep(1.5)
            
            # If recipe still not done after all steps, send generic updates
            logger.info(f"[JOB {job_id}] All status steps shown but recipe task still running, entering keep-alive loop")
            dot_count = 1
            loop_count = 0
            while not recipe_task.done():
                message = f"AI is finalizing your recipe...{'.' * dot_count}"
                loop_count += 1
                logger.info(f"[JOB {job_id}] Keep-alive loop iteration {loop_count}: {message}")
                yield await send_event("generating", message)
                dot_count = (dot_count % 3) + 1
                await asyncio.sleep(2)
                
            # Get the result
            try:
                logger.info(f"[JOB {job_id}] Recipe task completed, retrieving results")
                final_recipe = await recipe_task
                if not final_recipe:
                    logger.error(f"[JOB {job_id}] Recipe task returned empty result")
                    yield await send_event("error", "Recipe generation failed - empty result", is_error=True)
                    return
                elif "error" in final_recipe:
                    error_msg = final_recipe.get("error", "Failed to generate recipe")
                    logger.error(f"[JOB {job_id}] Recipe task returned error: {error_msg}")
                    yield await send_event("error", error_msg, is_error=True)
                    return
                else:
                    logger.info(f"[JOB {job_id}] Recipe successfully generated with {len(final_recipe.get('ingredients', []))} ingredients and {len(final_recipe.get('instructions', []))} steps")
            except Exception as e:
                logger.error(f"[JOB {job_id}] Recipe task failed with exception: {e}\n{traceback.format_exc()}")
                yield await send_event("error", f"Recipe generation failed: {str(e)}", is_error=True)
                return

            # This condition is now handled above

            if not show_top_image:
                logger.info(f"[JOB {job_id}] show_top_image is false, removing thumbnail_path")
                final_recipe['thumbnail_path'] = None
            elif 'thumbnail_path' in final_recipe:
                logger.info(f"[JOB {job_id}] Recipe includes thumbnail: {final_recipe['thumbnail_path']}")
            else:
                logger.info(f"[JOB {job_id}] Recipe does not include a thumbnail")
            
            logger.info(f"[JOB {job_id}] Sending completed event with recipe")
            yield await send_event("completed", "Recipe generation complete!", recipe=final_recipe)

        except Exception as e:
            logger.error(f"Error in stream for job {job_id}: {e}\n{traceback.format_exc()}")
            yield await send_event("error", f"An unexpected server error occurred: {e}", is_error=True)
        finally:
            logger.info(f"Stream finished for job {job_id}")

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/generate-pdf")
@limiter.limit("10/minute")
async def generate_pdf_endpoint(request: Request, recipe_content: RecipeContent):
    """
    Generates a PDF from the provided recipe content.
    It can now handle a thumbnail URL by downloading it temporarily.
    """
    job_id = str(uuid.uuid4())
    temp_thumbnail_path = None

    try:
        # If a thumbnail_url is provided, download it to a temporary file
        if recipe_content.thumbnail_path and recipe_content.thumbnail_path.startswith('http'):
            try:
                response = requests.get(recipe_content.thumbnail_path, stream=True)
                response.raise_for_status()
                
                # Create a temporary file to store the image
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_thumbnail_path = temp_file.name
                
                # Update the recipe content to use the local temporary path
                recipe_content.thumbnail_path = temp_thumbnail_path

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download thumbnail from {recipe_content.thumbnail_path}: {e}")
                recipe_content.thumbnail_path = None # Set to None if download fails

        # The rest of the function remains the same, using the local path
        from logic.pdf_generator import convert_recipe_content_to_recipe
        
        recipe_for_pdf = await convert_recipe_content_to_recipe(recipe_content)

        template_name = getattr(recipe_content, 'template_name', "modern")
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
    finally:
        # Clean up the temporary file if it was created
        if temp_thumbnail_path and os.path.exists(temp_thumbnail_path):
            os.unlink(temp_thumbnail_path)



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
    try:
        recipes = db.get_user_saved_recipes(current_user.id)
        return recipes
    except Exception as e:
        logger.error(f"Failed to get recipes for user {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch recipes.")

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
