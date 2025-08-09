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
from core.auth import get_current_active_user
from logic.video_processing import (
    download_video,
    transcribe_audio,
    extract_text_from_frames,
    contains_ingredients,
    extract_video_metadata,
    download_thumbnail,
    extract_and_save_frames,
    analyze_frames_with_blip
)
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import json
import asyncio
from pydantic import BaseModel
import re
import os
import yt_dlp

# --- Tag DTOs ---
class TagAction(BaseModel):
    keywords: List[str]

router = APIRouter()
# --- Roles admin endpoint ---
@router.post("/admin/users/{user_id}/roles")
@limiter.limit("30/minute")
async def set_user_roles(user_id: int, request: Request, payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    if not current_user or (not getattr(current_user, 'is_admin', False) and 'admin' not in getattr(current_user, 'roles', [])):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        roles = payload.get('roles') or []
        from core.database import db
        db.set_roles_for_user(user_id, roles)
        return {"ok": True, "data": {"userId": user_id, "roles": roles}}
    except Exception as e:
        logger.error(f"Failed to set roles for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not update roles.")
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
    if not transcript or not isinstance(transcript, str):
        logger.warning("[VALIDATION] Ingen transkribering tillgänglig.")
        return False
    if len(transcript.strip()) < 50:
        logger.warning(f"[VALIDATION] Transkribering för kort ({len(transcript.strip())} tecken).")
        return False
    if re.search(r'(.+?)\1{4,}', transcript):
        logger.warning("[VALIDATION] Transkribering innehåller repetitiva mönster.")
        return False
    words = transcript.strip().split()
    if len(words) > 10:
        short_words = [word for word in words if len(word) < 3]
        if (len(short_words) / len(words)) > 0.6:
            logger.warning("[VALIDATION] Transkribering har hög andel korta ord, kan vara brus.")
            return False
    logger.info("[VALIDATION] Transkribering bedöms vara tillräcklig.")
    return True

@router.get("/generate-stream")
async def generate_stream_endpoint(request: Request, video_url: str, language: str = "en", show_top_image: bool = True, show_step_images: bool = True):
    job_id = str(uuid.uuid4())
    base_url = str(request.base_url)

    async def send_event(status: str, message: str = None, recipe: dict = None, is_error: bool = False, debug_info: dict = None):
        data = {"status": status, "message": message, "timestamp": int(time.time() * 1000)}
        if recipe: data["recipe"] = recipe
        if is_error: data["status"] = "error"
        if debug_info: data["debug_info"] = debug_info
        log_message = f"Sending to frontend: {status}"
        if message: log_message += f" - {message}"
        logger.info(f"[FRONTEND_EVENT] {log_message}", extra={"data": data})
        return f"data: {json.dumps(data)}\n\n"

    async def generator():
        temp_files = []
        thumbnail_url = None
        try:
            logger.info(f"[JOB {job_id}] ===== STARTAR RECEPTGENERERING =====")
            logger.info(f"[JOB {job_id}] Video URL: {video_url}, Språk: {language}, Toppbild: {show_top_image}, Stegbilder: {show_step_images}")
            
            yield await send_event("processing", "Extracting video metadata...", debug_info={"step": "metadata_extraction"})
            metadata = await asyncio.to_thread(extract_video_metadata, video_url)
            if not metadata:
                logger.error(f"[JOB {job_id}] Misslyckades att hämta metadata")
                yield await send_event("error", "Could not retrieve video metadata.", is_error=True)
                return
            
            logger.info(f"[JOB {job_id}] Metadata hämtad: {metadata.get('title', 'Okänd titel')[:100]}")
            yield await send_event("processing", f'Processing: {metadata.get("title", "video")[:50]}...', debug_info={"metadata": metadata})

            if show_top_image:
                yield await send_event("processing", "Downloading thumbnail...", debug_info={"step": "thumbnail_download"})
                thumbnail_path = await asyncio.to_thread(download_thumbnail, video_url, job_id)
                if thumbnail_path:
                    temp_files.append(thumbnail_path)
                    thumbnail_url = f"{base_url.strip('/')}/{thumbnail_path.strip('/')}"
                    logger.info(f"[JOB {job_id}] Thumbnail nedladdad: {thumbnail_url}")
            
            logger.info(f"[JOB {job_id}] ===== CONTENT EXTRACTION PHASE =====")
            text_for_analysis, frame_paths = "", []
            description = metadata.get("description", "")
            
            if contains_ingredients(description):
                logger.info(f"[JOB {job_id}] Beskrivning innehåller ingredienser.")
                yield await send_event("processing", "Description contains recipe. Using it.")
                text_for_analysis = description
            else:
                logger.info(f"[JOB {job_id}] Beskrivning saknar ingredienser, fortsätter med ljud/video.")
                yield await send_event("downloading", "Downloading audio...")
                audio_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=True)
                if audio_path:
                    temp_files.append(audio_path)
                    yield await send_event("transcribing", "Transcribing audio...")
                    transcript = await asyncio.to_thread(transcribe_audio, audio_path, job_id, language)
                    if is_transcript_sufficient(transcript):
                        text_for_analysis = f"Title: {metadata.get('title', '')}\nDescription: {description}\nTranscript: {transcript}"
                
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
                     
                     frame_paths = await asyncio.to_thread(extract_and_save_frames, video_path, job_id)
                     temp_files.extend(frame_paths)
                     
                     if len(text_for_analysis.strip()) < 50 and frame_paths:
                         yield await send_event("analyzing", "Using AI to analyze video content...")
                         blip_analysis = await asyncio.to_thread(analyze_frames_with_blip, frame_paths, job_id)
                         if blip_analysis:
                             text_for_analysis = f"Title: {metadata.get('title', '')}\nDescription: {description}\nVideo Analysis: {blip_analysis}"
            
            if len(text_for_analysis.strip()) < 30:
                yield await send_event("error", "Could not extract enough information for a recipe.", is_error=True)
                return

            yield await send_event("generating", "Starting AI recipe generation...")
            recipe_task = asyncio.create_task(
                analyze_video_content(text_for_analysis, language, stream=False, thumbnail_path=thumbnail_url if show_top_image else None, frame_paths=[f"{base_url.strip('/')}/{p.strip('/')}" for p in frame_paths] if frame_paths else None)
            )
            
            status_steps = [
                {"status": "analyzing", "message": "Analyzing ingredients..."},
                {"status": "generating", "message": "Creating recipe structure..."},
                {"status": "generating", "message": "Writing cooking instructions..."},
                {"status": "generating", "message": "Finalizing recipe..."}
            ]
            
            while not recipe_task.done():
                for step in status_steps:
                    if recipe_task.done(): break
                    yield await send_event(step["status"], step["message"])
                    await asyncio.sleep(2)

            final_recipe = await recipe_task
            if not final_recipe or "error" in final_recipe:
                yield await send_event("error", final_recipe.get("error", "Recipe generation failed."), is_error=True)
                return
            
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
    job_id = str(uuid.uuid4())
    temp_thumbnail_path = None
    try:
        if recipe_content.thumbnail_path and recipe_content.thumbnail_path.startswith('http'):
            try:
                response = requests.get(recipe_content.thumbnail_path, stream=True)
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_thumbnail_path = temp_file.name
                recipe_content.thumbnail_path = temp_thumbnail_path
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download thumbnail: {e}")
                recipe_content.thumbnail_path = None

        from logic.pdf_generator import convert_recipe_content_to_recipe
        recipe_for_pdf = await convert_recipe_content_to_recipe(recipe_content)
        
        pdf_path = await asyncio.to_thread(
            generate_pdf, recipe=recipe_for_pdf, job_id=job_id,
            template_name=getattr(recipe_content, 'template_name', "modern"),
            video_title=recipe_for_pdf.title,
            show_top_image=getattr(recipe_content, 'show_top_image', True),
            show_step_images=getattr(recipe_content, 'show_step_images', True),
            language=getattr(recipe_content, 'language', 'en')
        )

        if not Path(pdf_path).exists():
            raise HTTPException(status_code=500, detail="PDF file was not created.")
        
        return FileResponse(path=pdf_path, filename=f"{recipe_content.title.replace(' ', '_')}.pdf", media_type="application/pdf")
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
    finally:
        if temp_thumbnail_path and os.path.exists(temp_thumbnail_path):
            os.unlink(temp_thumbnail_path)

@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "status": job.status, "details": job.details, "pdf_url": job.pdf_url}

@router.get("/usage-status", tags=["Usage"])
@limiter.limit("20/minute")
async def check_usage_status(request: Request, current_user: User = Depends(get_current_active_user)):
    pass

@router.post("/recipes/save", response_model=SavedRecipe, tags=["Recipes"])
@limiter.limit("30/minute")
async def save_user_recipe(request: Request, payload: SaveRecipeRequest, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # The recipe_content is now expected as a dict, not a Pydantic model instance
        recipe_dict = payload.recipe_content if isinstance(payload.recipe_content, dict) else payload.recipe_content.dict()
        
        saved_recipe = db.save_recipe(
            user_id=current_user.id, 
            source_url=payload.source_url, 
            recipe_content=recipe_dict
        )
        if not saved_recipe:
            raise HTTPException(status_code=500, detail="Failed to save recipe.")
        return saved_recipe
    except Exception as e:
        logger.error(f"Failed to save recipe for user {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Could not save recipe.")

@router.get("/recipes", response_model=List[SavedRecipe], tags=["Recipes"])
@limiter.limit("60/minute")
async def get_user_recipes(request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        return []
    try:
        sort = request.query_params.get('sort') or 'latest'
        recipes = db.get_user_saved_recipes(current_user.id, sort=sort)
        return recipes
    except Exception as e:
        logger.error(f"Failed to get recipes for user {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch recipes.")

@router.post("/scrape-recipe", tags=["Recipes"])
@limiter.limit("20/minute")
async def scrape_recipe(request: Request, url_payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    url = url_payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    try:
        from logic.web_scraper_new import scrape_recipe_from_url
        recipe_data = await scrape_recipe_from_url(url)
        if not recipe_data:
            raise HTTPException(status_code=500, detail="The scraper failed to extract recipe data. This is likely due to an unusual website structure or anti-scraping measures.")
        return JSONResponse(content={"status": "success", "recipe": recipe_data})
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error scraping URL {url}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# --- Ratings Endpoints ---
@router.get("/recipes/{recipe_id}/ratings")
@limiter.limit("120/minute")
async def get_recipe_ratings(recipe_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    try:
        user_id = current_user.id if current_user else None
        summary = db.get_ratings_summary(recipe_id, user_id)
        return JSONResponse(content={"ok": True, "data": summary})
    except Exception as e:
        logger.error(f"Failed to get ratings for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch ratings.")

@router.put("/recipes/{recipe_id}/ratings")
@limiter.limit("5/minute")
async def put_recipe_rating(recipe_id: int, request: Request, payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    value = int(payload.get("value", 0))
    if value < 1 or value > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    try:
        result = db.upsert_rating(recipe_id, current_user.id, value)
        return {"ok": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to set rating for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not set rating.")

@router.delete("/recipes/{recipe_id}/ratings")
@limiter.limit("5/minute")
async def delete_recipe_rating(recipe_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        result = db.delete_rating(recipe_id, current_user.id)
        return {"ok": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to delete rating for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete rating.")

# --- Comments Endpoints ---
@router.get("/recipes/{recipe_id}/comments")
@limiter.limit("240/minute")
async def list_recipe_comments(recipe_id: int, request: Request, after: str = None, limit: int = 20, sort: str = 'newest', current_user: User = Depends(get_current_active_user)):
    try:
        limit = max(1, min(limit, 50))
        viewer_id = current_user.id if current_user else None
        page = db.list_comments(recipe_id, after_cursor=after, limit=limit, sort=sort, viewer_user_id=viewer_id)
        return {"ok": True, "data": page}
    except Exception as e:
        logger.error(f"Failed to list comments for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch comments.")

@router.post("/recipes/{recipe_id}/comments")
@limiter.limit("5/minute")
async def create_recipe_comment(recipe_id: int, request: Request, payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        body = (payload.get("body") or "").strip()
        if len(body) < 1 or len(body) > 2000:
            raise HTTPException(status_code=400, detail="Comment must be 1-2000 characters")
        parent_id = payload.get("parentId")
        dto = db.create_comment(recipe_id, current_user.id, body=body, parent_id=parent_id)
        return {"ok": True, "data": dto}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create comment for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not create comment.")

@router.patch("/comments/{comment_id}")
@limiter.limit("60/minute")
async def update_comment(comment_id: int, request: Request, payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        body = (payload.get("body") or "").strip()
        dto = db.update_comment(comment_id, current_user.id, body=body, is_admin=getattr(current_user, 'is_admin', False))
        return {"ok": True, "data": dto}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to update comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not update comment.")

@router.delete("/comments/{comment_id}")
@limiter.limit("60/minute")
async def delete_comment(comment_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        dto = db.soft_delete_comment(comment_id, current_user.id, is_admin=getattr(current_user, 'is_admin', False))
        return {"ok": True, "data": dto}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to delete comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete comment.")

@router.post("/comments/{comment_id}/like")
@limiter.limit("120/minute")
async def toggle_comment_like(comment_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        res = db.toggle_comment_like(comment_id, current_user.id)
        return {"ok": True, "data": res}
    except Exception as e:
        logger.error(f"Failed to toggle like for comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not like comment.")

@router.post("/comments/{comment_id}/report")
@limiter.limit("60/minute")
async def report_comment(comment_id: int, request: Request, payload: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        reason = (payload.get("reason") or "").strip()
        db.report_comment(comment_id, current_user.id, reason)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to report comment {comment_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not report comment.")

@router.post("/search")
@limiter.limit("20/minute")
async def search_videos(request: Request, search_request: YouTubeSearchRequest = Body(...)):
    query = search_request.query
    page = search_request.page
    results_per_page = 10
    source = search_request.source or 'youtube'
    if "recipe" not in query.lower():
        query = f"{query} recipe"
    try:
        search_prefix = f"ytsearch{page * results_per_page}:{query}"
        ydl_opts = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': False}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(search_prefix, download=False)
            if not results or 'entries' not in results:
                return JSONResponse(content={"results": []})
            videos = []
            for entry in results['entries']:
                if not entry: continue
                video_id = entry.get('id')
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                videos.append(YouTubeVideo(
                    video_id=video_id, title=entry.get('title', 'Unknown Title'),
                    channel_title=entry.get('channel', 'Unknown Channel'), thumbnail_url=thumbnail,
                    duration="", view_count="", published_at=None, description=None
                ))
            unique_videos = list({v.video_id: v for v in videos}.values())
            paginated_results = unique_videos[(page - 1) * results_per_page : page * results_per_page]
            return JSONResponse(content={"results": [v.dict() for v in paginated_results]})
    except Exception as e:
        logger.error(f"General search failed for query '{query}': {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# --- Tagging Endpoints ---
def _can_edit_tags(current_user: Optional[User], recipe_id: int) -> (bool, bool):
    if not current_user:
        return (False, False)
    roles = set(getattr(current_user, 'roles', []) or ([]))
    is_admin = getattr(current_user, 'is_admin', False) or ('admin' in roles)
    is_moderator = 'moderator' in roles
    is_trusted = 'trusted' in roles
    owner_id = db.get_recipe_owner_id(recipe_id)
    is_creator = owner_id == current_user.id
    can_direct = is_admin or is_moderator or is_creator or is_trusted
    return (can_direct, is_admin or is_moderator)

@router.get("/recipes/{recipe_id}/tags")
async def list_recipe_tags_endpoint(recipe_id: int):
    return {"ok": True, "data": db.list_recipe_tags(recipe_id)}

@router.get("/tags/search")
async def search_tags_endpoint(q: str = None):
    return {"ok": True, "data": db.search_tags(q)}

@router.post("/recipes/{recipe_id}/tags")
@limiter.limit("30/minute")
async def add_recipe_tags_endpoint(recipe_id: int, request: Request, payload: TagAction = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    keywords = payload.keywords or []
    if db.is_tag_edit_locked(recipe_id):
        _, can_moderate = _can_edit_tags(current_user, recipe_id)
        if not can_moderate:
            raise HTTPException(status_code=423, detail="Tags are locked for this recipe")
    can_direct, _ = _can_edit_tags(current_user, recipe_id)
    direct = can_direct
    user_id = current_user.id if current_user else 0
    result = db.add_recipe_tags(recipe_id, user_id, keywords, direct)
    return {"ok": True, "data": result}

@router.delete("/recipes/{recipe_id}/tags")
@limiter.limit("30/minute")
async def remove_recipe_tag_endpoint(recipe_id: int, request: Request, keyword: str, current_user: Optional[User] = Depends(get_current_active_user)):
    can_direct, can_moderate = _can_edit_tags(current_user, recipe_id)
    if not (can_direct or can_moderate):
        raise HTTPException(status_code=403, detail="Forbidden")
    res = db.remove_recipe_tag(recipe_id, current_user.id if current_user else 0, keyword)
    return {"ok": True, "data": res}

@router.post("/recipes/{recipe_id}/tags/approve")
@limiter.limit("60/minute")
async def approve_tag_endpoint(recipe_id: int, request: Request, keyword: str = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    _, can_moderate = _can_edit_tags(current_user, recipe_id)
    if not can_moderate:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ok": True, "data": db.approve_recipe_tag(recipe_id, current_user.id, keyword)}

@router.post("/recipes/{recipe_id}/tags/reject")
@limiter.limit("60/minute")
async def reject_tag_endpoint(recipe_id: int, request: Request, keyword: str = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    _, can_moderate = _can_edit_tags(current_user, recipe_id)
    if not can_moderate:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ok": True, "data": db.reject_recipe_tag(recipe_id, current_user.id, keyword)}

@router.post("/recipes/{recipe_id}/tags/lock")
@limiter.limit("30/minute")
async def lock_tags_endpoint(recipe_id: int, request: Request, payload: dict = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    _, can_moderate = _can_edit_tags(current_user, recipe_id)
    if not can_moderate:
        raise HTTPException(status_code=403, detail="Forbidden")
    locked = bool(payload.get('locked', True))
    reason = payload.get('reason')
    db.set_tag_lock(recipe_id, locked, current_user.id, reason)
    return {"ok": True}
