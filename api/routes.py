import uuid
import traceback
import logging
import requests
import tempfile
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, BackgroundTasks, Body, File
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.requests import Request
from models.types import User, RecipeContent, SavedRecipe, Recipe, SaveRecipeRequest, YouTubeVideo, YouTubeSearchRequest, Step, Collection
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
from logic.nutrition_calculator import NutritionCalculator
from core.database import db
from logic.job_queue import enqueue_nutrition_compute

router = APIRouter()

@router.get("/nutrition/admin/summary")
async def nutrition_admin_summary():
    try:
        from core.database import db as _db
        con = _db.get_connection()
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM nutrition_snapshots WHERE status='ready'")
        ready = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM nutrition_snapshots WHERE status='pending'")
        pending = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM nutrition_snapshots WHERE status='error'")
        error = int(cur.fetchone()[0] or 0)
        con.close()
        return {"ready": ready, "pending": pending, "error": error, "lastRun": None}
    except Exception as e:
        logger.error(f"nutrition_admin_summary error: {e}")
        raise HTTPException(status_code=500, detail="summary failed")

@router.get("/nutrition/admin/list")
async def nutrition_admin_list(status: Optional[str] = None, q: Optional[str] = None):
    try:
        from core.database import db as _db
        con = _db.get_connection()
        cur = con.cursor()
        base = "SELECT sr.id, ns.status, ns.updated_at, sr.source_url FROM saved_recipes sr LEFT JOIN nutrition_snapshots ns ON ns.recipe_id = sr.id"
        where = []
        params = []
        if status:
            where.append("ns.status = ?")
            params.append(status)
        if q:
            where.append("sr.source_url LIKE ?")
            params.append(f"%{q}%")
        sql = base + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY sr.id DESC"
        cur.execute(sql, tuple(params))
        rows = []
        for rid, st, upd, title in cur.fetchall():
            # quick skipped count
            meta = _db.get_nutrition_snapshot(rid) or {}
            skipped_count = len((meta.get('meta') or {}).get('skipped') or [])
            rows.append({"id": rid, "title": title, "status": st or 'pending', "updated_at": upd, "anomaly": 0, "skipped_count": skipped_count})
        con.close()
        return rows
    except Exception as e:
        logger.error(f"nutrition_admin_list error: {e}")
        raise HTTPException(status_code=500, detail="list failed")

@router.post("/nutrition/admin/recompute-errors")
async def nutrition_recompute_errors():
    try:
        from core.database import db as _db
        con = _db.get_connection()
        cur = con.cursor()
        cur.execute("SELECT recipe_id FROM nutrition_snapshots WHERE status='error'")
        ids = [r[0] for r in cur.fetchall()]
        con.close()
        import asyncio
        for rid in ids:
            try:
                await enqueue_nutrition_compute(int(rid))
            except Exception:
                continue
        return {"queued": len(ids)}
    except Exception as e:
        logger.error(f"nutrition_recompute_errors error: {e}")
        raise HTTPException(status_code=500, detail="recompute-errors failed")

@router.get("/nutrition/{recipe_id}/meta")
async def get_nutrition_meta(recipe_id: int):
    try:
        snap = db.get_nutrition_snapshot(recipe_id)
        return snap or {}
    except Exception as e:
        logger.error(f"get_nutrition_meta error: {e}")
        raise HTTPException(status_code=500, detail="meta failed")
from logic.translator import resolve, translate_canonical
from backend.transcribe.faster_whisper_engine import transcribe_audio_stream
from logic.recipe_parser import analyze_video_content
from logic.pdf_generator import generate_pdf
import json
import asyncio
from pydantic import BaseModel
import re
import asyncio
import json as _json
import os
import yt_dlp
import httpx
from datetime import datetime, timezone
import hashlib as _hashlib
import unicodedata as _unicodedata
import re as _re2

# --- Tag DTOs ---
class TagAction(BaseModel):
    keywords: List[str]

# --- Nutrition DTOs ---
class NutritionCalcRequest(BaseModel):
    recipeId: str
    servings: int
    ingredients: List[Dict[str, str]]

class NutritionResult(BaseModel):
    perServing: Dict[str, Optional[float]]
    total: Dict[str, Optional[float]]
    needsReview: List[str] = []
    # Optional diagnostics/trace fields from calculator (not required for UI but useful)
    warnings: List[str] = []
    translationStats: Optional[Dict[str, int]] = None
    explanations: Optional[List[Dict[str, Any]]] = None
    debugEntries: Optional[List[Dict[str, Any]]] = None
    implausibleItems: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = None
    
class ImageGenRequest(BaseModel):
    recipe_id: Optional[int] = None
    seed: Optional[int] = None
    # Optional hint; if omitted we infer from recipe (if no original image → allow placeholder)
    allow_placeholder: Optional[bool] = None
    # Preview-driven fields
    title: Optional[str] = None
    ingredients: Optional[list] = None  # list[str|dict]
    constraints: Optional[Dict[str, Any]] = None
    aspect: Optional[str] = None  # '1:1','4:3','3:2','16:9'
    fast_mode: Optional[bool] = None
    mode: Optional[str] = None  # 'auto'|'img2img'|'txt2img'
    image_url: Optional[str] = None  # original image to condition on (optional)

from typing import Optional as _Optional

def _build_image_prompt(recipe_title: str, ingredients: list, presets: _Optional[list] = None, *, aspect: str = '1:1', seed: Optional[int] = None, fast_mode: bool = False) -> dict:
    """Builds a plain text prompt for image generation (provider-agnostic).
    Returns a minimal dict with prompt, negative_prompt, width, height.
    """
    try:
        ingredient_names: list[str] = []
        stop_words = {'water', 'salt', 'pepper', 'oil', 'olive oil', 'sugar'}
        for item in (ingredients or [])[:7]:
            name = ''
            if isinstance(item, dict):
                name = (item.get('name') or item.get('ingredient') or '').strip()
            elif isinstance(item, str):
                name = item.strip()
            if name and name.lower() not in stop_words:
                ingredient_names.append(name)
    except Exception:
        ingredient_names = []

    ing_str = ', '.join(ingredient_names[:7])
    style = (
        "professional food photography, appetizing, single plated dish, close-up, "
        "natural soft studio lighting, shallow depth of field, realistic textures, clean background, no collage"
    )

    # Diet tags
    diet_tags: list[str] = []
    pset = set((presets or []))
    if 'vegan' in pset or 'plant-based' in pset:
        diet_tags.append('vegan, plant-based')
    if 'vegetarian' in pset:
        diet_tags.append('vegetarian')
    if 'gluten-free' in pset:
        diet_tags.append('gluten-free')
    if 'dairy-free' in pset or 'lactose-free' in pset:
        diet_tags.append('dairy-free')
    diet = (', '.join(diet_tags)).strip()
    diet_part = f", {diet}" if diet else ''

    base_prompt = f"photo of {recipe_title}, {ing_str}{diet_part}, {style}"
    negative_prompt = (
        "abstract, pattern, fractal, mosaic, collage, grid, panels, tiles, triptych, diptych, six images, "
        "multiple images, frame, border, text, logo, watermark, deformed, duplicate, oversaturated, unrealistic colors, blurry"
    )

    # Aspect mapping (keep compact sizes for speed)
    width, height = 384, 384
    if aspect == '4:3':
        width, height = 512, 384
    elif aspect == '3:2':
        width, height = 576, 384
    elif aspect == '16:9':
        width, height = 640, 360

    return {
        'prompt': base_prompt,
        'negative_prompt': negative_prompt,
        'width': width,
        'height': height,
        'seed': seed,
        'fast_mode': bool(fast_mode),
    }

# ---- Update existing recipe (owner only) ----
class UpdateRecipeRequest(BaseModel):
    recipe_content: Dict[str, Any]

@router.put("/recipes/{recipe_id}", tags=["Recipes"])
@limiter.limit("30/minute")
async def update_saved_recipe_api(request: Request, recipe_id: int, payload: UpdateRecipeRequest, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    owner_id = db.get_recipe_owner_id(recipe_id)
    if owner_id != current_user.id and not getattr(current_user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        from models.types import RecipeContent
        validated = RecipeContent.model_validate(payload.recipe_content or {})
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE saved_recipes SET recipe_content = ? WHERE id = ? AND user_id = ?", (validated.model_dump_json(), recipe_id, owner_id))
            conn.commit()
        updated = db.get_saved_recipe(recipe_id)
        # attempt: if collection id provided as query param and collection has no image, adopt
        try:
            col = request.query_params.get('collectionId')
            if col and updated and updated.recipe_content and not (await _has_collection_image(int(col))):
                await _adopt_collection_cover_from_recipe(int(col), updated)
        except Exception:
            pass
        return jsonable_encoder(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not update recipe")

@router.post("/images/generate")
async def generate_recipe_image(payload: ImageGenRequest):
    try:
        rc = {}
        has_original_image = False
        if payload.recipe_id is not None:
            base = db.get_saved_recipe(payload.recipe_id)
            if not base:
                raise HTTPException(status_code=404, detail="Recipe not found")
            rc = base.recipe_content.model_dump()
            has_original_image = bool((rc.get('image_url') or rc.get('thumbnail_path')))
        allow_placeholder = payload.allow_placeholder if payload.allow_placeholder is not None else (not has_original_image)
        # include presets from payload or conversion metadata
        conv_presets = []
        try:
            conv_presets = (payload.constraints or ((rc.get('conversion') or {}).get('constraints') or {})).get('presets') or []
        except Exception:
            conv_presets = []
        title_for_prompt = (payload.title or rc.get('title') or 'Dish')
        ingredients_for_prompt = payload.ingredients or (rc.get('ingredients') or [])
        aspect = (payload.aspect or '1:1')
        fast_mode = bool(payload.fast_mode)
        prompt_info = _build_image_prompt(
            title_for_prompt,
            ingredients_for_prompt,
            conv_presets,
            aspect=aspect,
            seed=(int(payload.seed) if payload.seed is not None else None),
            fast_mode=fast_mode,
        )

        # --- Replicate.com (or compatible) image generation ---
        api_token = os.getenv('REPLICATE_API_TOKEN') or os.getenv('REPLICA_API_KEY')
        if not api_token:
            raise HTTPException(status_code=500, detail="Missing REPLICATE_API_TOKEN/REPLICA_API_KEY on server")

        headers = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json',
        }
        timeout = httpx.Timeout(90.0, connect=10.0, read=90.0)

        # Decide mode
        requested_mode = (payload.mode or 'auto')
        do_img2img = False
        if requested_mode == 'img2img':
            do_img2img = True
        elif requested_mode == 'auto':
            do_img2img = bool(has_original_image or payload.image_url)

        # Try image-to-image first (SDXL img2img) using data URI so no public URL is required
        if do_img2img:
            try:
                # Prepare source image bytes
                source_bytes = None
                src_url = payload.image_url
                if not src_url:
                    src_url = (rc.get('image_url') or rc.get('thumbnail_path'))
                if src_url:
                    if isinstance(src_url, str) and src_url.startswith('http'):
                        async with httpx.AsyncClient(timeout=timeout) as _hc:
                            ir = await _hc.get(src_url)
                            ir.raise_for_status()
                            source_bytes = ir.content
                    else:
                        # Local path served under /images
                        local_path = None
                        if isinstance(src_url, str) and src_url.startswith('/'):
                            local_path = os.path.join('public', src_url.lstrip('/')) if src_url.startswith('/images') else src_url.lstrip('/')
                        if local_path and os.path.exists(local_path):
                            with open(local_path, 'rb') as f:
                                source_bytes = f.read()
                if not source_bytes:
                    raise RuntimeError('No source image bytes for img2img')
                import base64 as _b64
                data_uri = 'data:image/png;base64,' + _b64.b64encode(source_bytes).decode('utf-8')

                # Try multiple img2img providers on Replicate
                width = int(prompt_info.get('width') or 384)
                height = int(prompt_info.get('height') or 384)
                # Strengthen composition preservation: favor baking tray casserole, disallow plates
                # Derive style hints dynamically from constraints (no hardcoding diet): if constraints include
                # baked/casserole keywords, strengthen composition; otherwise keep general.
                base_prompt_img2img = prompt_info['prompt']
                neg_base = (prompt_info.get('negative_prompt') or '')
                compost_prompt = base_prompt_img2img
                neg_common = neg_base
                img2img_candidates = [
                    ('stability-ai/stable-diffusion', {
                        'image': data_uri,
                        'prompt': compost_prompt,
                        'negative_prompt': neg_common,
                        'width': width,
                        'height': height,
                        'strength': 0.18,
                        'num_inference_steps': 28,
                        'guidance_scale': 4.0
                    }),
                    ('stability-ai/stable-diffusion-2-1', {
                        'image': data_uri,
                        'prompt': compost_prompt,
                        'negative_prompt': neg_common,
                        'width': width,
                        'height': height,
                        'strength': 0.2,
                        'num_inference_steps': 28,
                        'guidance_scale': 4.0
                    })
                ]

                async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                    # Replicate predictions endpoint for stable-diffusion-img2img (versioned)
                    predictions_url = 'https://api.replicate.com/v1/predictions'
                    # Ensure external URL: upload to Replicate files if needed
                    image_input = src_url if (src_url and src_url.startswith('http')) else None
                    if not image_input:
                        try:
                            # Request presigned file slot
                            fmeta = await client.post('https://api.replicate.com/v1/files', json={'filename': 'input.png'})
                            fmeta.raise_for_status()
                            info = fmeta.json()
                            upload_url = info.get('upload_url'); serving_url = info.get('serving_url')
                            if not upload_url or not serving_url:
                                raise RuntimeError('Missing upload_url/serving_url')
                            # Upload original bytes
                            putr = await client.put(upload_url, content=source_bytes, headers={'Content-Type': 'application/octet-stream'})
                            putr.raise_for_status()
                            image_input = serving_url
                        except Exception as _uerr:
                            logger.warning(f"Replicate upload failed: {_uerr}; trying data URI")
                            image_input = data_uri
                    # Minimal, validated payload first to avoid 422
                    sd_payload = {
                        'version': '15a3689ee13bd02616e98280eca31d4c3abcd3672df6afce5cb6feb1d66087d',
                        'input': {
                            'image': image_input,
                            'num_inference_steps': 25
                        }
                    }
                    try:
                        create = await client.post(predictions_url, json=sd_payload)
                        create.raise_for_status()
                    except httpx.HTTPStatusError as he:
                        body = (he.response.text or '')
                        logger.error(f"Replicate predictions error {he.response.status_code}: {body[:500]}")
                        raise HTTPException(status_code=he.response.status_code, detail=f"Replicate predictions error: {body[:500]}")
                    pred = create.json()
                    get_url = (pred.get('urls') or {}).get('get')
                    if not get_url:
                        raise HTTPException(status_code=502, detail='Replicate did not return a status URL')
                    status = pred.get('status')
                    started = time.time()
                    while status not in ('succeeded','failed','canceled'):
                        if time.time() - started > 120:
                            raise HTTPException(status_code=504, detail='Replicate timeout')
                        await asyncio.sleep(1.0)
                        r = await client.get(get_url)
                        r.raise_for_status()
                        pred = r.json()
                        status = pred.get('status')
                    if status != 'succeeded':
                        raise RuntimeError(f'img2img stable-diffusion status={status}')
                    output = pred.get('output')
                    image_url = output[0] if isinstance(output, list) else output
                    if not image_url:
                        raise RuntimeError('Replicate returned no output image')
                    ir = await client.get(image_url)
                    ir.raise_for_status()
                    img_bytes = ir.content
                    import uuid as _uuid, os as _os
                    uid = str(_uuid.uuid4())
                    rel_dir = os.path.join('public', 'images', 'recipes')
                    os.makedirs(rel_dir, exist_ok=True)
                    path = os.path.join(rel_dir, f"{uid}.png")
                    with open(path, 'wb') as f:
                        f.write(img_bytes)
                    url = f"/images/recipes/{uid}.png"
                    return {'url': url}
            except Exception as e:
                logger.warning(f"img2img attempt failed, falling back to txt2img: {e}")

        # Fallback to fast txt2img (Flux Schnell)
        create_url = 'https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions'
        replicate_input = {'prompt': prompt_info['prompt']}
        if prompt_info.get('width') and prompt_info.get('height'):
            replicate_input['width'] = int(prompt_info['width'])
            replicate_input['height'] = int(prompt_info['height'])

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            try:
                create = await client.post(create_url, json={'input': replicate_input})
                try:
                    create.raise_for_status()
                except httpx.HTTPStatusError as he:
                    body = (he.response.text or '')[:500]
                    logger.error(f"Replicate create error: {he} body: {body}")
                    raise
                pred = create.json()
                get_url = (pred.get('urls') or {}).get('get')
                if not get_url:
                    raise HTTPException(status_code=502, detail="Replicate did not return a status URL")

                # Poll for completion
                status = pred.get('status')
                started = time.time()
                while status not in ('succeeded', 'failed', 'canceled'):
                    if time.time() - started > 60:
                        raise HTTPException(status_code=504, detail="Replicate timeout")
                    await asyncio.sleep(1.0)
                    r = await client.get(get_url)
                    r.raise_for_status()
                    pred = r.json()
                    status = pred.get('status')

                if status != 'succeeded':
                    detail = pred.get('error') or f"status={status}"
                    if not allow_placeholder:
                        raise HTTPException(status_code=503, detail="AI image unavailable; use original image")
                    # Placeholder flow (scrape/no-image)
                    from PIL import Image, ImageDraw, ImageFont
                    import io, base64
                    w, h = prompt_info.get('width') or 384, prompt_info.get('height') or 384
                    img = Image.new('RGB', (w, h), (242, 244, 246))
                    draw = ImageDraw.Draw(img)
                    text = (title_for_prompt or 'Recipe')[:28]
                    try:
                        font = ImageFont.truetype('static/fonts/DejaVuSans-Bold.ttf', 22)
                    except Exception:
                        font = ImageFont.load_default()
                    try:
                        l, t0, r, b = draw.textbbox((0, 0), text, font=font)
                        tw, th = (r - l), (b - t0)
                    except Exception:
                        tw, th = draw.textsize(text, font=font)
                    draw.text(((w - tw) / 2, (h - th) / 2), text, fill=(60, 60, 60), font=font)
                    bio = io.BytesIO()
                    img.save(bio, format='PNG')
                    img_bytes = bio.getvalue()
                else:
                    output = pred.get('output')
                    if isinstance(output, list) and output:
                        image_url = output[0]
                    elif isinstance(output, str):
                        image_url = output
                    else:
                        raise HTTPException(status_code=502, detail="Replicate returned no output image")

                    # Download the image bytes
                    ir = await client.get(image_url)
                    ir.raise_for_status()
                    img_bytes = ir.content

                # Save to local static path
                import uuid as _uuid, os as _os
                uid = str(_uuid.uuid4())
                rel_dir = os.path.join('public', 'images', 'recipes')
                os.makedirs(rel_dir, exist_ok=True)
                path = os.path.join(rel_dir, f"{uid}.png")
                with open(path, 'wb') as f:
                    f.write(img_bytes)
                url = f"/images/recipes/{uid}.png"
                return {'url': url}
            except HTTPException:
                raise
            except httpx.HTTPError as e:
                # Convert to 504 to signal transient upstream issue
                raise HTTPException(status_code=504, detail=f"Image backend timeout/unavailable: {e}")
            except Exception as e:
                logger.error(f"Replicate generation failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise

@router.post("/images/upload")
async def upload_recipe_image(file: UploadFile = File(...)):
    try:
        if not file or not getattr(file, 'content_type', '').startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image uploads are allowed")
        # Determine extension
        import os as _os, uuid as _uuid
        ext = 'png'
        try:
            name = file.filename or ''
            if '.' in name:
                ext = name.rsplit('.', 1)[-1].lower()
                if len(ext) > 5: ext = 'png'
        except Exception:
            ext = 'png'

        uid = str(_uuid.uuid4())
        rel_dir = _os.path.join('public', 'images', 'recipes')
        _os.makedirs(rel_dir, exist_ok=True)
        out_path = _os.path.join(rel_dir, f"{uid}.{ext}")

        # Save in chunks; enforce simple size cap (~12MB)
        size = 0
        with open(out_path, 'wb') as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 12 * 1024 * 1024:
                    try:
                        _os.remove(out_path)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail="Image too large (max 12MB)")
                out.write(chunk)
        url = f"/images/recipes/{uid}.{ext}"
        return { 'url': url }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/proxy-image")
async def proxy_image(url: str):
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content_type = r.headers.get("content-type", "image/jpeg")
            return StreamingResponse(iter([r.content]), media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        logger.error(f"Proxy image failed for {url}: {e}")
        raise HTTPException(status_code=404, detail="Image not found")
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

_SUBS_CACHE: dict = {}

async def _deepseek_classify_ingredient(text: str, locale: str = 'sv', timeout_s: float = 6.0, mode: str = 'vegan'):
    key = os.getenv('DEEPSEEK_API_KEY') or ''
    if not key:
        return None
    cache_key = (text.strip().lower(), locale)
    if cache_key in _SUBS_CACHE:
        return _SUBS_CACHE[cache_key]
    system = "You are a culinary diet checker. Output strict JSON only."
    if mode == 'vegan':
        rule = "contains any animal-derived product for a vegan diet"
        repl_hint = "vegan replacement"
    elif mode == 'vegetarian':
        rule = "is meat or poultry (fish/seafood allowed) for a vegetarian diet"
        repl_hint = "vegetarian replacement"
    else:
        rule = "is meat or poultry (fish/seafood allowed) for a pescetarian diet"
        repl_hint = "pescetarian replacement"
    user = (
        f"Classify if this ingredient {rule}. "
        f"Respond as JSON object: {{\"animal\": boolean, \"replacement\": string }}. "
        f"Ingredient: {text}. Locale={locale}. If animal=false, set replacement to empty string. "
        f"If animal=true, propose a realistic Nordic-available {repl_hint} phrase."
    )
    payload = {
        "model": os.getenv('DEEPSEEK_MODEL', 'deepseek-chat'),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 120,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
            resp = await client.post("https://api.deepseek.com/v1/chat/completions", headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = (data.get('choices') or [{}])[0].get('message', {}).get('content', '')
            # Extract JSON
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                obj = _json.loads(content[start:end+1])
                _SUBS_CACHE[cache_key] = obj
                return obj
    except Exception:
        return None

    return None

async def _enforce_diet_constraints(parsed: dict, constraints: dict) -> dict:
    try:
        presets = set((constraints or {}).get('presets') or [])
        if not presets.intersection({'vegan','plant-based','vegetarian','pescetarian'}):
            return parsed
        ingredients = list(parsed.get('ingredients') or [])
        subs = list(parsed.get('substitutions') or [])
        banned_map = {
            'vegan': [
                # Swedish
                'bacon','korv','skinka','kött','nötfärs','fläsk','kyckling','lax','torsk','fisk','räkor','tonfisk','ägg','mjölk','ost','grädde','smör','yoghurt','gelatin','honung',
                # English/common
                'beef','pork','chicken','turkey','steak','ground beef','minced beef','minced meat','ham','sausage','salami','anchovy','anchovies','shrimp','prawn','tuna','salmon','cod','fish','gelatin','honey',
                # Named dishes/phrases that imply animal protein
                'carne asada','al pastor','barbacoa','tinga','chorizo'
            ],
            'vegetarian': [
                # Meat/fish only (allow dairy/eggs)
                'bacon','korv','skinka','kött','nötfärs','fläsk','kyckling','lax','torsk','fisk','räkor','tonfisk',
                'beef','pork','chicken','turkey','steak','ground beef','ham','sausage','salami','anchovy','anchovies','shrimp','prawn','tuna','salmon','cod','fish','carne asada','al pastor','barbacoa','tinga','chorizo'
            ],
            'pesc': [
                # Ban meat/poultry; allow fish/seafood
                'bacon','korv','skinka','kött','nötfärs','fläsk','kyckling',
                'beef','pork','chicken','turkey','steak','ground beef','ham','sausage','salami','carne asada','al pastor','barbacoa','tinga','chorizo'
            ]
        }
        repl = {
            # Swedish
            'bacon':'rökt tofu','korv':'vegokorv','skinka':'växtbaserad skinka','kött':'sojafärs','nötfärs':'sojafärs','fläsk':'sojabitar','kyckling':'sojabitar','lax':'fiskfri ersättning','torsk':'fiskfri ersättning','fisk':'fiskfri ersättning','räkor':'tofuräkor','tonfisk':'kikärtsröra','ägg':'kikärtsmjöl','mjölk':'havredryck','ost':'vegansk ost','grädde':'havregrädde','smör':'växtsmör','yoghurt':'sojayoghurt','gelatin':'pektin','honung':'lönnsirap',
            # English/common
            'beef':'sojafärs','ground beef':'sojafärs','minced beef':'sojafärs','minced meat':'sojafärs','pork':'sojabitar','chicken':'sojabitar','turkey':'sojabitar','steak':'portabello eller sojabitar',
            'ham':'växtbaserad skinka','sausage':'vegokorv','salami':'vegosalami','anchovy':'kapris','anchovies':'kapris','shrimp':'tofuräkor','prawn':'tofuräkor','tuna':'kikärtsröra','salmon':'fiskfri ersättning','cod':'fiskfri ersättning','fish':'fiskfri ersättning',
            # Phrases
            'carne asada':'svamp/soja-asada','al pastor':'svamp/soja al pastor','barbacoa':'svamp/soja barbacoa','tinga':'pulled jackfruit tinga','chorizo':'veganchorizo'
        }
        if 'vegan' in presets or 'plant-based' in presets:
            mode = 'vegan'
        elif 'vegetarian' in presets:
            mode = 'vegetarian'
        elif 'pescetarian' in presets:
            mode = 'pesc'
        else:
            mode = 'vegetarian'
        banned_list = banned_map.get(mode, banned_map['vegetarian'])
        cleaned = []
        to_check_llm = []
        for item in ingredients:
            # Accept dict ingredients and collapse to a single text field for matching
            if isinstance(item, dict):
                name = str(item.get('name') or item.get('ingredient') or '')
                qty = str(item.get('quantity') or '')
                text = (name if qty == '' else f"{qty} {name}").strip()
            else:
                text = str(item)
            low = text.lower()
            replaced_flag = False
            for b in banned_list:
                if b in low:
                    to = repl.get(b, 'växtbaserat alternativ')
                    cleaned.append(re.sub(b, to, text, flags=re.IGNORECASE))
                    subs.append({'from': b, 'to': to, 'reason': f'{mode} preset'})
                    replaced_flag = True
                    break
            if not replaced_flag:
                # Skip obviously plant-based words to reduce unnecessary checks
                if mode == 'vegan' and not any(tok in low for tok in ['tofu','soja','soy','svamp','mushroom','tempeh','seitan','quorn','vegansk','plant','växt']):
                    to_check_llm.append((len(cleaned), text))
                cleaned.append(text)
        # LLM fallback for up to 5 questionable items
        if mode in ('vegan','vegetarian','pesc') and to_check_llm:
            limited = to_check_llm[:5]
            results = await asyncio.gather(*[
                _deepseek_classify_ingredient(txt, 'sv', mode=mode) for _, txt in limited
            ], return_exceptions=True)
            for (idx, original), res in zip(limited, results):
                try:
                    if isinstance(res, dict) and res.get('animal') is True:
                        replacement = str(res.get('replacement') or 'växtbaserat alternativ')
                        cleaned[idx] = re.sub(re.escape(original), replacement, cleaned[idx], flags=re.IGNORECASE) if isinstance(cleaned[idx], str) else replacement
                        subs.append({'from': original, 'to': replacement, 'reason': f'{mode} LLM check'})
                except Exception:
                    pass
        parsed['ingredients'] = cleaned
        
        # Also normalize instructions text (strings or dicts with 'description')
        try:
            instr = list(parsed.get('instructions') or [])
            norm = []
            for item in instr:
                if isinstance(item, dict):
                    text = str(item.get('description') or '')
                    low = text.lower()
                    for b in banned_list:
                        if b in low:
                            to = repl.get(b, 'växtbaserat alternativ')
                            text = re.sub(b, to, text, flags=re.IGNORECASE)
                            low = text.lower()
                    item['description'] = text
                    norm.append(item)
                else:
                    text = str(item)
                    low = text.lower()
                    for b in banned_list:
                        if b in low:
                            to = repl.get(b, 'växtbaserat alternativ')
                            text = re.sub(b, to, text, flags=re.IGNORECASE)
                            low = text.lower()
                    norm.append(text)
            parsed['instructions'] = norm
        except Exception:
            pass
        parsed['substitutions'] = subs
    except Exception:
        return parsed
    return parsed

@router.get("/generate-stream")
async def generate_stream_endpoint(request: Request, video_url: str, language: str = "en", show_top_image: bool = True, show_step_images: bool = True):
    job_id = str(uuid.uuid4())
    base_url = str(request.base_url)
    timings = {}

    async def send_event(status: str, message: str = None, recipe: dict = None, is_error: bool = False, debug_info: dict = None):
        data = {"status": status, "message": message, "timestamp": int(time.time() * 1000)}
        if recipe: data["recipe"] = recipe
        if is_error: data["status"] = "error"
        if debug_info: data["debug_info"] = debug_info
        log_message = f"Sending to frontend: {status}"
        if message: log_message += f" - {message}"
        logger.info(f"[FRONTEND_EVENT] {log_message}", extra={"data": data})
        return f"data: {json.dumps(data)}\n\n"

    async def send_struct_event(ev_type: str, payload: dict):
        """Send structured events with jobId, type, payload format"""
        body = {"jobId": job_id, "type": ev_type, "payload": payload}
        logger.info(f"[FRONTEND_EVENT_STRUCT] {ev_type}")
        return f"data: {json.dumps(body)}\n\n"

    async def generator():
        temp_files = []
        thumbnail_url = None
        try:
            timings['t_init'] = int(time.time() * 1000)
            logger.info(f"[JOB {job_id}] ===== STARTAR RECEPTGENERERING =====")
            logger.info(f"[JOB {job_id}] Video URL: {video_url}, Språk: {language}, Toppbild: {show_top_image}, Stegbilder: {show_step_images}")

            # Metadata extraction
            yield await send_event("processing", "Extracting video metadata...", debug_info={"step": "metadata_extraction"})
            metadata = await asyncio.to_thread(extract_video_metadata, video_url)
            if not metadata:
                yield await send_event("error", "Could not retrieve video metadata.", is_error=True)
                return
            yield await send_event("processing", f'Processing: {metadata.get("title", "video")[:50]}...', debug_info={"metadata": metadata})

            # Thumbnail (Stage A needs thumbnail quickly)
            if show_top_image:
                yield await send_event("processing", "Downloading thumbnail...", debug_info={"step": "thumbnail_download"})
                thumbnail_path = await asyncio.to_thread(download_thumbnail, video_url, job_id)
                if thumbnail_path:
                    temp_files.append(thumbnail_path)
                    thumbnail_url = f"{base_url.strip('/')}/{thumbnail_path.strip('/')}"
                    timings['t_image_ready'] = int(time.time() * 1000)
                    yield await send_struct_event('image_ready', {"thumbnail_url": thumbnail_url})

            # Stage A: description -> captions -> faster-whisper (audio-only)
            video_id = None
            try:
                video_id = re.search(r"(?<=v=)[^&#]+", video_url) or re.search(r"(?<=be/)[^&#]+", video_url)
                video_id = video_id.group(0) if video_id else None
            except Exception:
                video_id = None

            pipeline_version = os.getenv('PIPELINE_VERSION', 'fw_v1')
            cache_key_a = f"stageA:{video_id or job_id}:{pipeline_version}"
            cached_a = None
            try:
                from logic.video_processing import cache_get, cache_set, try_fetch_captions
                cached_a = cache_get(cache_key_a)
            except Exception:
                cached_a = None

            yield await send_struct_event('recipe_init', {"title": metadata.get('title', ''), "description": metadata.get('description', '')})

            if cached_a:
                # Fast path: send cached Stage A
                timings['t_first_patch'] = int(time.time() * 1000)
                yield await send_struct_event('recipe_patch', cached_a.get('recipe_patch', {}))
                yield await send_struct_event('stageA_done', {"cached": True})
            else:
                # Attempt captions first
                captions = None
                try:
                    captions = try_fetch_captions(video_url, job_id)
                except Exception:
                    captions = None

                transcript_text = ''
                timeline = []

                if captions and captions.get('confidence', 0) >= 0.75:
                    transcript_text = captions.get('text', '')
                    timings['t_first_patch'] = int(time.time() * 1000)
                    # Start streaming recipe LLM from captions
                    async for chunk in analyze_video_content(transcript_text, language, stream=True, thumbnail_path=thumbnail_url):
                        if isinstance(chunk, dict) and 'error' not in chunk:
                            yield await send_struct_event('recipe_patch', chunk)
                    timings['t_stageA_done'] = int(time.time() * 1000)
                    cache_set(cache_key_a, {"recipe_patch": chunk, "transcript": transcript_text})
                else:
                    # No good captions -> do audio download + streaming ASR
                    yield await send_event('downloading', 'Downloading audio...')
                    audio_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=True)
                    if audio_path:
                        temp_files.append(audio_path)
                        yield await send_event('transcribing', 'Transcribing audio...')

                        # Set up queues for segments and recipe patches
                        seg_q = asyncio.Queue()
                        recipe_q = asyncio.Queue()

                        loop = asyncio.get_running_loop()

                        def _blocking_transcribe_and_stream():
                            wav_tmp = None
                            try:
                                import tempfile, subprocess, os
                                wav_tmpf = tempfile.NamedTemporaryFile(prefix=f"{job_id}_", suffix=".wav", delete=False)
                                wav_tmp = wav_tmpf.name
                                wav_tmpf.close()
                                ffmpeg_cmd = ["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "16000", "-vn", "-f", "wav", wav_tmp]
                                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                for seg in transcribe_audio_stream(wav_tmp, lang_hint=language):
                                    loop.call_soon_threadsafe(seg_q.put_nowait, seg)
                                loop.call_soon_threadsafe(seg_q.put_nowait, None)
                            except Exception as e:
                                logger.error(f"[STREAM_ASR] error: {e}")
                                loop.call_soon_threadsafe(seg_q.put_nowait, None)
                            finally:
                                try:
                                    if wav_tmp and os.path.exists(wav_tmp):
                                        os.unlink(wav_tmp)
                                except Exception:
                                    pass

                        _ = loop.run_in_executor(None, _blocking_transcribe_and_stream)

                        # Background coroutine to run LLM when enough transcript accumulated
                        analyze_started = False
                        collected_parts = []
                        first_seg_start = None
                        last_seg_end = None

                        async def _analyze_from_text(text_snippet: str):
                            async for chunk in analyze_video_content(text_snippet, language, stream=True, thumbnail_path=thumbnail_url):
                                await recipe_q.put(chunk)
                            await recipe_q.put(None)

                        analyze_task = None

                        # Main loop: consume seg_q and recipe_q
                        recipe_first_sent = False
                        while True:
                            get_seg = asyncio.create_task(seg_q.get())
                            get_patch = asyncio.create_task(recipe_q.get())
                            done, pending = await asyncio.wait({get_seg, get_patch}, return_when=asyncio.FIRST_COMPLETED)
                            
                            if get_patch in done:
                                patch = get_patch.result()
                                if patch is None:
                                    # recipe stream finished
                                    pass
                                else:
                                    # forward recipe patch
                                    timings.setdefault('t_first_patch', int(time.time() * 1000))
                                    yield await send_struct_event('recipe_patch', patch)
                                    recipe_first_sent = True
                                # cancel seg task if pending
                                if get_seg in pending:
                                    get_seg.cancel()
                                    
                            if get_seg in done:
                                seg = get_seg.result()
                                if seg is None:
                                    # transcription finished
                                    # ensure analyze finishes
                                    if analyze_task:
                                        # wait for recipe queue to drain
                                        while True:
                                            p = await recipe_q.get()
                                            if p is None:
                                                break
                                    break
                                # process segment
                                collected_parts.append(seg.get('text',''))
                                if first_seg_start is None:
                                    first_seg_start = seg.get('start')
                                last_seg_end = seg.get('end')
                                # stream raw transcribe segment to frontend as progress
                                yield await send_struct_event('transcribe_segment', {"text": seg.get('text'), "start": seg.get('start'), "end": seg.get('end')})
                                # decide to start analyze when we have ~30s audio or >=250 chars
                                cur_text = ' '.join([p for p in collected_parts if p])
                                cur_dur = (last_seg_end - first_seg_start) if (first_seg_start is not None and last_seg_end is not None) else 0
                                if (not analyze_started) and (cur_dur >= 30 or len(cur_text) > 250):
                                    analyze_started = True
                                    analyze_task = asyncio.create_task(_analyze_from_text(cur_text))
                                # cancel patch task if pending
                                if get_patch in pending:
                                    get_patch.cancel()

                        # after transcription loop
                        # collect final transcript
                        transcript_text = ' '.join([p for p in collected_parts if p])
                        timings['t_stageA_done'] = int(time.time() * 1000)
                        # cache stage A
                        try:
                            cache_set(cache_key_a, {"recipe_patch": None, "transcript": transcript_text})
                        except Exception:
                            pass

            # Stage B: alignment + enrich
            timings['t_video_ready'] = int(time.time() * 1000)
            # ensure video downloaded for any further processing
            video_path = await asyncio.to_thread(download_video, video_url, job_id, audio_only=False)
            if video_path:
                temp_files.append(video_path)
                from logic.video_processing import get_media_duration
                duration = await asyncio.to_thread(get_media_duration, video_path, False)
                yield await send_struct_event('video_ready', {"videoId": video_id or job_id, "durationSec": duration or 0})

            # Alignment: simple fuzzy matching of steps to transcript segments
            # retrieve Stage A recipe from cache if present
            stageA = None
            try:
                stageA = cache_get(cache_key_a)
            except Exception:
                stageA = None

            timestamps = []
            if stageA and 'transcript' in stageA and 'recipe_patch' in stageA:
                recipe_obj = stageA.get('recipe_patch')
                transcript_full = stageA.get('transcript')
            else:
                # fallback: use transcript_text if available
                recipe_obj = None
                transcript_full = locals().get('transcript_text', '')

            # For accept criteria, align quickly (<2s). We'll use a heuristic over timeline if available.
            try:
                from difflib import SequenceMatcher
                steps = []
                if recipe_obj and isinstance(recipe_obj, dict) and 'instructions' in recipe_obj:
                    steps = recipe_obj['instructions']
                # naive: split transcript into words and map approximate positions by searching substrings in collected segments
                # Here we attempt to find each step in transcript_full and approximate times using timeline segments
                if transcript_full and 'timeline' in locals():
                    # build concatenated text with segment boundaries
                    concat = ''
                    seg_map = []
                    for seg in timeline:
                        seg_map.append((len(concat), seg))
                        concat += ' ' + seg.get('text','')
                    for i, step in enumerate(steps):
                        step_text = step.get('description') if isinstance(step, dict) else str(step)
                        # fuzzy search by sliding window over concat
                        best = (0, 0, 0.0)
                        for j, (pos, seg) in enumerate(seg_map):
                            window = concat[pos:pos+max(200, len(step_text)+50)]
                            ratio = SequenceMatcher(None, step_text.lower(), window.lower()).ratio()
                            if ratio > best[2]:
                                best = (j, j, ratio)
                        if best[2] > 0:
                            segc = seg_map[best[0]][1]
                            timestamps.append({"index": i, "start_sec": segc.get('start'), "end_sec": segc.get('end'), "confidence": round(best[2], 2)})
                timings['t_timestamps_ready'] = int(time.time() * 1000)
                yield await send_struct_event('timestamps_ready', {"steps": timestamps})
            except Exception as e:
                logger.warning(f"Alignment failed: {e}")

            # Enrich: attach timestamps to recipe and send enrich_patch
            enrich_payload = {"timestamps": timestamps}
            yield await send_struct_event('enrich_patch', enrich_payload)
            timings['t_done'] = int(time.time() * 1000)
            yield await send_struct_event('enrich_done', {"timings": timings})

        except Exception as e:
            logger.error(f"Error in structured stream for job {job_id}: {e}\n{traceback.format_exc()}")
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
    try:
        sort = request.query_params.get('sort') or 'latest'
        scope = request.query_params.get('scope') or 'mine'
        if scope == 'all':
            recipes = db.get_all_saved_recipes(sort=sort)
        else:
            if current_user:
                recipes = db.get_user_saved_recipes(current_user.id, sort=sort)
            else:
                recipes = db.get_all_saved_recipes(sort=sort)
        return recipes
    except Exception as e:
        logger.error("Failed to get recipes: %s", e)
        raise HTTPException(status_code=500, detail="Could not fetch recipes.")

# Lightweight single-recipe fetch (public for now; used by modals/navigation)
@router.get("/recipes/{recipe_id}", response_model=SavedRecipe, tags=["Recipes"])
@limiter.limit("120/minute")
async def get_recipe_by_id(request: Request, recipe_id: int):
    try:
        item = db.get_saved_recipe(recipe_id)
        if not item:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch recipe")

# --- Public user profile endpoints ---
@router.get("/users/{username}", response_model=User, tags=["Users"])
@limiter.limit("120/minute")
async def get_public_user(username: str, request: Request):
    u = db.get_user_by_username(username)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    # enrich with followed_by_me if viewer is logged in
    viewer = await get_current_active_user(request)
    try:
        if viewer:
            with db.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM user_follows WHERE follower_id = ? AND followee_id = ?", (viewer.id, u.id))
                fbm = c.fetchone() is not None
            u.followed_by_me = fbm
        else:
            u.followed_by_me = False
    except Exception:
        u.followed_by_me = False
    return u

@router.get("/users/{username}/recipes", response_model=List[SavedRecipe], tags=["Users"])
@limiter.limit("120/minute")
async def list_public_user_recipes(username: str, request: Request):
    try:
        u = db.get_user_by_username(username)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        sort = request.query_params.get('sort') or 'latest'
        return db.get_user_saved_recipes(u.id, sort=sort)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list recipes for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch user's recipes")

@router.post("/users/{username}/follow", tags=["Users"]) 
@limiter.limit("120/minute")
async def toggle_user_follow(username: str, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        u = db.get_user_by_username(username)
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        if u.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM user_follows WHERE follower_id = ? AND followee_id = ?", (current_user.id, u.id))
            exists = c.fetchone() is not None
            if exists:
                c.execute("DELETE FROM user_follows WHERE follower_id = ? AND followee_id = ?", (current_user.id, u.id))
                following = False
            else:
                c.execute("INSERT OR IGNORE INTO user_follows (follower_id, followee_id) VALUES (?, ?)", (current_user.id, u.id))
                following = True
            conn.commit()
        return {"ok": True, "data": {"following": following}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle follow for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Could not update follow state")

@router.get("/users/{username}/collections", response_model=List[Collection], tags=["Users"]) 
@limiter.limit("120/minute")
async def list_public_user_collections(username: str, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    try:
        viewer_id = current_user.id if current_user else None
        items = db.list_user_public_collections(username, viewer_id)
        return items
    except Exception as e:
        logger.error(f"Failed to list collections for user {username}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch user's collections")

# --- Collections endpoints ---
@router.get("/collections", response_model=List[Collection], tags=["Collections"])
@limiter.limit("60/minute")
async def list_collections(request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    viewer_id = current_user.id if current_user else None
    return db.list_collections(viewer_id)

@router.post("/collections", tags=["Collections"]) 
@limiter.limit("20/minute")
async def create_collection(request: Request, payload: dict = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    title = (payload.get('title') or '').strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    description = payload.get('description')
    visibility = payload.get('visibility') or 'public'
    image_url = payload.get('image_url')
    cid = db.create_collection(current_user.id, title, description, visibility, image_url)
    return {"ok": True, "id": cid}

@router.get("/collections/{collection_id}/like", tags=["Collections"])
@limiter.limit("240/minute")
async def get_collection_like_status(collection_id: int, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM collection_likes WHERE collection_id = ? AND user_id = ?", (collection_id, current_user.id))
            liked = c.fetchone() is not None
            c.execute("SELECT likes_count FROM collections WHERE id = ?", (collection_id,))
            result = c.fetchone()
            likes_count = result[0] if result else 0
        return {"ok": True, "data": {"liked": liked, "likes_count": likes_count}}
    except Exception as e:
        logger.error(f"Failed to get like status for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not get like status")

@router.post("/collections/{collection_id}/like", tags=["Collections"])
@limiter.limit("120/minute")
async def toggle_collection_like(collection_id: int, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM collection_likes WHERE collection_id = ? AND user_id = ?", (collection_id, current_user.id))
            exists = c.fetchone() is not None
            if exists:
                c.execute("DELETE FROM collection_likes WHERE collection_id = ? AND user_id = ?", (collection_id, current_user.id))
                liked = False
                c.execute("UPDATE collections SET likes_count = CASE WHEN likes_count > 0 THEN likes_count - 1 ELSE 0 END WHERE id = ?", (collection_id,))
            else:
                c.execute("INSERT OR IGNORE INTO collection_likes (collection_id, user_id) VALUES (?, ?)", (collection_id, current_user.id))
                liked = True
                c.execute("UPDATE collections SET likes_count = likes_count + 1 WHERE id = ?", (collection_id,))
            conn.commit()
        return {"ok": True, "data": {"liked": liked}}
    except Exception as e:
        logger.error(f"Failed to toggle like for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not toggle like")

@router.post("/collections/{collection_id}/follow", tags=["Collections"])
@limiter.limit("120/minute")
async def toggle_collection_follow(collection_id: int, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM collection_follows WHERE collection_id = ? AND user_id = ?", (collection_id, current_user.id))
            exists = c.fetchone() is not None
            if exists:
                c.execute("DELETE FROM collection_follows WHERE collection_id = ? AND user_id = ?", (collection_id, current_user.id))
                following = False
                c.execute("UPDATE collections SET followers_count = CASE WHEN followers_count > 0 THEN followers_count - 1 ELSE 0 END WHERE id = ?", (collection_id,))
            else:
                c.execute("INSERT OR IGNORE INTO collection_follows (collection_id, user_id) VALUES (?, ?)", (collection_id, current_user.id))
                following = True
                c.execute("UPDATE collections SET followers_count = followers_count + 1 WHERE id = ?", (collection_id,))
            conn.commit()
        return {"ok": True, "data": {"following": following}}
    except Exception as e:
        logger.error(f"Failed to toggle follow for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not toggle follow")

@router.post("/collections/{collection_id}/recipes", tags=["Collections"]) 
@limiter.limit("60/minute")
async def add_recipe_to_collection(request: Request, collection_id: int, payload: dict = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    recipe_id = int(payload.get('recipe_id'))
    return db.add_recipe_to_collection(collection_id, recipe_id)

async def _has_collection_image(collection_id: int) -> bool:
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT image_url FROM collections WHERE id = ?", (collection_id,))
            row = c.fetchone()
            return bool(row and row[0])
    except Exception:
        return False

async def _adopt_collection_cover_from_recipe(collection_id: int, saved_recipe):
    try:
        image = (saved_recipe.recipe_content or {}).get('image_url')
        if image:
            with db.get_connection() as conn:
                c = conn.cursor()
                c.execute("UPDATE collections SET image_url = ? WHERE id = ? AND (image_url IS NULL OR image_url = '')", (image, collection_id))
                conn.commit()
    except Exception:
        return

@router.get("/collections/{collection_id}/recipes", response_model=List[SavedRecipe], tags=["Collections"]) 
@limiter.limit("60/minute")
async def list_collection_recipes(request: Request, collection_id: int, current_user: Optional[User] = Depends(get_current_active_user)):
    user_id = current_user.id if current_user else None
    return db.list_collection_recipes(collection_id, user_id)

class UpdateCollectionPayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    image_url: Optional[str] = None

@router.put("/collections/{collection_id}", tags=["Collections"])
@limiter.limit("30/minute")
async def update_collection(collection_id: int, request: Request, payload: UpdateCollectionPayload, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        ok = db.update_collection(collection_id, **{k: v for k, v in payload.model_dump().items() if v is not None})
        if not ok:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not update collection")

class ReorderPayload(BaseModel):
    recipe_ids: List[int]

@router.post("/collections/{collection_id}/reorder", tags=["Collections"])
@limiter.limit("60/minute")
async def reorder_collection(collection_id: int, request: Request, payload: ReorderPayload, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        ok = db.reorder_collection_recipes(collection_id, payload.recipe_ids or [])
        if not ok:
            raise HTTPException(status_code=400, detail="Reorder failed")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder recipes for collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not reorder collection")

@router.delete("/collections/{collection_id}/recipes/{recipe_id}", tags=["Collections"])
@limiter.limit("60/minute")
async def remove_recipe_from_collection(collection_id: int, recipe_id: int, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        ok = db.remove_recipe_from_collection(collection_id, recipe_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Remove failed")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove recipe {recipe_id} from collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not remove from collection")

@router.delete("/recipes/{recipe_id}", tags=["Recipes"])
@limiter.limit("30/minute")
async def delete_user_recipe(recipe_id: int, request: Request, current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from core.database import db
        owner_id = db.get_recipe_owner_id(recipe_id)
        if owner_id != current_user.id and not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Forbidden")
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM saved_recipes WHERE id=? AND user_id=?", (recipe_id, current_user.id))
            conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete recipe {recipe_id} for user {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Could not delete recipe.")

@router.get("/recipes/{recipe_id}/variants", tags=["Recipes"])
@limiter.limit("60/minute")
async def list_recipe_variants(recipe_id: int, request: Request, sort: str = 'newest', page: int = 1, limit: int = 12, presets: str = None):
    try:
        page = max(1, int(page))
        limit = max(1, min(50, int(limit)))
        preset_list = []
        if presets:
            try:
                preset_list = [p.strip() for p in presets.split(',') if p.strip()]
            except Exception:
                preset_list = []

        items = []
        with db.get_connection() as conn:
            c = conn.cursor()
            # Fetch candidates; filter in Python by conversion metadata
            c.execute("SELECT id, user_id, created_at, recipe_content, rating_average, rating_count FROM saved_recipes ORDER BY created_at DESC")
            rows = c.fetchall()
            for rid, uid, created_at, rc_json, ravg, rcount in rows:
                try:
                    rc = json.loads(rc_json)
                except Exception:
                    continue
                conv = (rc or {}).get('conversion') or {}
                if not isinstance(conv, dict):
                    continue
                if not conv.get('isVariant'):
                    continue
                if int(conv.get('parentRecipeId') or 0) != int(recipe_id):
                    continue
                if (conv.get('visibility') or 'private') != 'public':
                    continue
                # score for closest
                score = 0
                if preset_list:
                    vpresets = set((conv.get('constraints') or {}).get('presets') or [])
                    score += len(vpresets.intersection(set(preset_list)))
                items.append({
                    'id': rid,
                    'userId': uid,
                    'createdAt': created_at,
                    'title': conv.get('displayTitle') or rc.get('title') or 'Variant',
                    'constraints': (conv.get('constraints') or {}),
                    'ratingAverage': float(ravg or 0),
                    'ratingCount': int(rcount or 0),
                    'score': score
                })

        # sort
        if sort == 'popular':
            items.sort(key=lambda x: (x['ratingCount'], x['ratingAverage'], x['createdAt']), reverse=True)
        elif sort == 'closest' and preset_list:
            items.sort(key=lambda x: (x['score'], x['ratingAverage'], x['ratingCount'], x['createdAt']), reverse=True)
        else:
            items.sort(key=lambda x: x['createdAt'], reverse=True)

        start = (page - 1) * limit
        sliced = items[start:start + limit]

        # attach owner display name
        for it in sliced:
            try:
                c = db.get_connection().cursor()
                c.execute("SELECT username, full_name FROM users WHERE id = ?", (it['userId'],))
                row = c.fetchone()
                it['owner'] = {'id': it['userId'], 'username': row[0] if row and row[0] else None, 'displayName': (row[0] or (row[1] if row else None))}
            except Exception:
                it['owner'] = {'id': it['userId'], 'username': None, 'displayName': None}

        return { 'ok': True, 'data': { 'items': sliced, 'total': len(items), 'page': page, 'limit': limit } }
    except Exception as e:
        logger.error(f"Failed to list variants for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch variants.")

# --- Visibility toggle for variants ---
@router.put("/recipes/{variant_id}/visibility", tags=["Recipes"])
@limiter.limit("20/minute")
async def set_variant_visibility(variant_id: int, request: Request, payload: dict = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        desired = (payload.get('visibility') or 'private').lower()
        if desired not in ('private','public'):
            raise HTTPException(status_code=400, detail="visibility must be 'private' or 'public'")
        # ensure ownership
        owner_id = db.get_recipe_owner_id(variant_id)
        if owner_id != current_user.id and not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Forbidden")
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT recipe_content FROM saved_recipes WHERE id = ?", (variant_id,))
            row = c.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Variant not found")
            try:
                rc = json.loads(row[0])
            except Exception:
                rc = {}
            conv = rc.get('conversion') or {}
            conv['visibility'] = desired
            rc['conversion'] = conv
            from models.types import RecipeContent
            # validate output before save
            rc_valid = RecipeContent.model_validate(rc)
            rc_json = rc_valid.model_dump_json()
            c.execute("UPDATE saved_recipes SET recipe_content = ? WHERE id = ?", (rc_json, variant_id))
            conn.commit()
        updated = db.get_saved_recipe(variant_id)
        return jsonable_encoder(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set visibility for variant {variant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/scrape-recipe-stream", tags=["Recipes"])
@limiter.limit("30/minute")
async def scrape_recipe_stream(request: Request, url: str):
    """Server-Sent Events: streamar progressiv scraping med tidiga patchar.
    Events:
      - struct 'recipe_init': { title?, source_url, placeholder_image? }
      - struct 'status': { message }
      - struct 'recipe_patch': { any fields: title, description, ingredients, instructions, image_url, servings, times }
      - struct 'image_ready': { image_url }
      - struct 'done': { recipe }
      - struct 'error': { message }
    """
    job_id = str(uuid.uuid4())

    async def send_struct(ev_type: str, payload: dict) -> str:
        body = {"jobId": job_id, "type": ev_type, "payload": payload}
        return f"data: {json.dumps(body)}\n\n"

    async def generator():
        try:
            from logic.web_scraper_new import FlexibleWebCrawler
            crawler = FlexibleWebCrawler()
            base_url = str(request.base_url)

            # 1) Init + skeleton
            yield await send_struct('status', {"message": "Initierar..."})
            title_guess = None
            image_guess = None
            try:
                html = await crawler._fetch_html_simple(url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                # Title guess from H1
                try:
                    h1 = soup.find('h1')
                    if h1:
                        t = h1.get_text(strip=True)
                        if t and len(t) >= 3:
                            title_guess = t
                except Exception:
                    pass
                # Early OG image
                try:
                    image_guess = crawler.content_extractor.find_image_url(soup, url)
                except Exception:
                    image_guess = None
            except Exception:
                soup = None

            yield await send_struct('recipe_init', {
                "title": title_guess or '',
                "source_url": url,
                "image_url": image_guess or None,
            })

            # 2) Quick sources
            yield await send_struct('status', {"message": "Extraherar snabbdatastrukturer..."})
            result = None
            if soup is not None:
                try:
                    result = await crawler._extract_quick_sources(soup, url)
                except Exception:
                    result = None
            if result:
                # Send patch immediately
                patch = {k: v for k, v in result.items() if k in (
                    'title','description','ingredients','instructions','image_url','servings','prep_time_minutes','cook_time_minutes','total_time_minutes','lang'
                )}
                yield await send_struct('recipe_patch', patch)
                yield await send_struct('status', {"message": "Normaliserar..."})
                try:
                    normalized = await crawler._normalize_and_enrich(result, url, soup)
                except Exception:
                    normalized = result
                # Diff image
                try:
                    if (normalized.get('image_url') and normalized.get('image_url') != result.get('image_url')):
                        yield await send_struct('image_ready', {"image_url": normalized.get('image_url')})
                except Exception:
                    pass
                # Final done
                yield await send_struct('done', {"recipe": normalized})
                return

            # 3) Playwright fallback
            yield await send_struct('status', {"message": "Renderar sida (JS)..."})
            soup2 = None
            try:
                html2 = await crawler._fetch_html_with_playwright(url)
                from bs4 import BeautifulSoup
                soup2 = BeautifulSoup(html2, 'html.parser')
            except Exception:
                soup2 = None
            result2 = None
            if soup2 is not None:
                try:
                    result2 = await crawler._extract_quick_sources(soup2, url)
                except Exception:
                    result2 = None
            if result2:
                patch = {k: v for k, v in result2.items() if k in (
                    'title','description','ingredients','instructions','image_url','servings','prep_time_minutes','cook_time_minutes','total_time_minutes','lang'
                )}
                yield await send_struct('recipe_patch', patch)
                yield await send_struct('status', {"message": "Normaliserar..."})
                try:
                    normalized = await crawler._normalize_and_enrich(result2, url, soup2)
                except Exception:
                    normalized = result2
                try:
                    if (normalized.get('image_url') and normalized.get('image_url') != result2.get('image_url')):
                        yield await send_struct('image_ready', {"image_url": normalized.get('image_url')})
                except Exception:
                    pass
                yield await send_struct('done', {"recipe": normalized})
                return

            # 4) AI fallback
            yield await send_struct('status', {"message": "Kör AI-parser..."})
            final = None
            try:
                # choose soup2 if available
                work_soup = soup2 or soup
                if work_soup is None and url:
                    html3 = await crawler._fetch_html_simple(url)
                    from bs4 import BeautifulSoup
                    work_soup = BeautifulSoup(html3, 'html.parser')
                final = await crawler._extract_recipe_from_soup(work_soup, url)
            except Exception:
                final = None
            if not final:
                # Fallback: minst titel + bild + källa
                fallback_title = title_guess or ''
                fallback_img = image_guess or None
                try:
                    if not fallback_title or not fallback_img:
                        # Best-effort hämta snabbt
                        html4 = await crawler._fetch_html_simple(url)
                        from bs4 import BeautifulSoup
                        s4 = BeautifulSoup(html4, 'html.parser')
                        if not fallback_title:
                            h1 = s4.find('h1')
                            if h1:
                                t = h1.get_text(strip=True)
                                if t and len(t) >= 3:
                                    fallback_title = t
                        if not fallback_img:
                            try:
                                fallback_img = crawler.content_extractor.find_image_url(s4, url)
                            except Exception:
                                fallback_img = None
                except Exception:
                    pass
                minimal = {
                    "title": fallback_title or "",
                    "image_url": fallback_img or None,
                    "source_url": url,
                    "ingredients": [],
                    "instructions": []
                }
                yield await send_struct('done', {"recipe": minimal})
                return
            # Already normalized in that flow, but ensure
            try:
                final = await crawler._normalize_and_enrich(final, url, soup2 or soup)
            except Exception:
                pass
            yield await send_struct('done', {"recipe": final})
        except Exception as e:
            logger.error(f"scrape_recipe_stream error: {e}")
            try:
                yield await send_struct('error', {"message": str(e)})
            except Exception:
                pass

    from starlette.responses import StreamingResponse
    return StreamingResponse(generator(), media_type='text/event-stream')

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

# --- Recipe Likes Endpoints ---
@router.get("/recipes/{recipe_id}/like")
@limiter.limit("240/minute")
async def get_recipe_like_status(recipe_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM recipe_likes WHERE recipe_id = ? AND user_id = ?", (recipe_id, current_user.id))
            liked = c.fetchone() is not None
            c.execute("SELECT likes_count FROM saved_recipes WHERE id = ?", (recipe_id,))
            result = c.fetchone()
            likes_count = result[0] if result else 0
        return {"ok": True, "data": {"liked": liked, "likes_count": likes_count}}
    except Exception as e:
        logger.error(f"Failed to get like status for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not get like status")

@router.post("/recipes/{recipe_id}/like")
@limiter.limit("120/minute")
async def toggle_recipe_like(recipe_id: int, request: Request, current_user: User = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM recipe_likes WHERE recipe_id = ? AND user_id = ?", (recipe_id, current_user.id))
            exists = c.fetchone() is not None
            if exists:
                c.execute("DELETE FROM recipe_likes WHERE recipe_id = ? AND user_id = ?", (recipe_id, current_user.id))
                liked = False
                c.execute("UPDATE saved_recipes SET likes_count = CASE WHEN likes_count > 0 THEN likes_count - 1 ELSE 0 END WHERE id = ?", (recipe_id,))
            else:
                c.execute("INSERT OR IGNORE INTO recipe_likes (recipe_id, user_id) VALUES (?, ?)", (recipe_id, current_user.id))
                liked = True
                c.execute("UPDATE saved_recipes SET likes_count = likes_count + 1 WHERE id = ?", (recipe_id,))
            conn.commit()
        return {"ok": True, "data": {"liked": liked}}
    except Exception as e:
        logger.error(f"Failed to toggle like for recipe {recipe_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not toggle like")

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

# --- Conversion Variant Endpoint (frontend-driven DeepSeek) ---
@router.post("/recipes/{recipe_id}/convert")
@limiter.limit("12/minute")
async def convert_recipe_variant(recipe_id: int, request: Request, payload: dict = Body(...), current_user: Optional[User] = Depends(get_current_active_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        base = db.get_saved_recipe(recipe_id)
        if not base:
            raise HTTPException(status_code=404, detail="Recipe not found")

        result = payload.get('result') or {}
        constraints = payload.get('constraints') or {}
        # Nutrition feasibility + tolerance
        tol = int((constraints.get('nutrition') or {}).get('tolerance') or constraints.get('tolerance') or 5)
        status, reason = _feasibility_check(constraints.get('nutrition') or {}, tol)
        if status == 'impossible':
            raise HTTPException(status_code=400, detail=f"Impossible nutrition targets: {reason}")
        # Normalize and validate presets using same logic as frontend
        presets = constraints.get('presets') or []
        normalized, adjustments = _normalize_presets_backend(presets)
        constraints['presets'] = normalized
        deepseek_model = payload.get('deepseekModel') or payload.get('model')

        if not isinstance(result, dict):
            raise HTTPException(status_code=400, detail="Invalid conversion payload: result must be object")

        # Normalize incoming result before save
        base_content = base.recipe_content.model_dump()

        def _is_nonempty_list(value):
            return isinstance(value, list) and len(value) > 0

        ingredients_raw = result.get('ingredients') if _is_nonempty_list(result.get('ingredients')) else base_content.get('ingredients')
        instructions_raw = result.get('instructions') if _is_nonempty_list(result.get('instructions')) else base_content.get('instructions')

        # Map to backend schema: Ingredient objects and Instruction objects
        def _to_ingredients(items):
            mapped = []
            for item in items or []:
                if isinstance(item, dict) and ('name' in item or 'quantity' in item):
                    mapped.append({
                        'name': (item.get('name') or '').strip() or (item.get('ingredient') or ''),
                        'quantity': (item.get('quantity') or '').strip(),
                        'notes': (item.get('notes') or None)
                    })
                else:
                    text = str(item).strip()
                    if not text:
                        continue
                    mapped.append({'name': text, 'quantity': '', 'notes': None})
            return mapped

        def _to_instructions(items):
            mapped = []
            for idx, item in enumerate(items or [], start=1):
                if isinstance(item, dict) and ('description' in item or 'step' in item):
                    mapped.append({
                        'step': int(item.get('step') or idx),
                        'description': (item.get('description') or '').strip() or f'Step {idx}',
                        'image_path': item.get('image_path')
                    })
                else:
                    text = str(item).strip()
                    if not text:
                        continue
                    mapped.append({'step': idx, 'description': text, 'image_path': None})
            return mapped

        ingredients = _to_ingredients(ingredients_raw)
        instructions = _to_instructions(instructions_raw)

        # Nutrition normalization: align to our schema field
        nutrition = result.get('nutritionPerServing') or result.get('nutritional_information') or base_content.get('nutritional_information')

        # Build conversion metadata
        desired_visibility = (payload.get('visibility') or 'public').lower()
        if desired_visibility not in ('public','private'):
            desired_visibility = 'public'
        conversion_meta = {
            'isVariant': True,
            'parentRecipeId': recipe_id,
            'basedOnTitle': base_content.get('title'),
            'constraints': constraints,
            'substitutions': result.get('substitutions'),
            'notes': result.get('notes'),
            'compliance': result.get('compliance'),
            'deepseekModel': deepseek_model,
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'visibility': desired_visibility
        }

        # --- Variant titling & slug ---
        def _slugify(text: str) -> str:
            try:
                text = _unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
            except Exception:
                pass
            text = _re2.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
            text = _re2.sub(r'[\s-]+', '-', text)
            return (text or 'variant')[:80].strip('-')

        def _diet_label(presets_list):
            order = ['vegan','plant-based','vegetarian','pescetarian','omnivore']
            for p in order:
                if p in (presets_list or []):
                    return 'Plant-based' if p == 'plant-based' else p.capitalize()
            return None

        def _constraint_labels(cons):
            labels = []
            p = cons.get('presets') or []
            n = cons.get('nutrition') or {}
            for key in ['gluten-free','dairy-free','lactose-free','nut-free','soy-free','egg-free','fish-free','shellfish-free','low-fat','high-protein','low-sodium','low-carb','keto','Mediterranean','Whole30','paleo']:
                if key in p and len(labels) < 2:
                    labels.append(key.replace('-', ' '))
            if len(labels) < 2 and n.get('maxCalories') is not None:
                labels.append(f"≤{int(n['maxCalories'])} kcal")
            if len(labels) < 2 and n.get('minProtein') is not None:
                labels.append(f"≥{int(n['minProtein'])} g protein")
            return labels[:2]

        def _neutralize_for_diet(text: str, presets_list):
            if not text:
                return text
            if 'vegan' in (presets_list or []) or 'plant-based' in (presets_list or []):
                banned = ['biff','nöt','nötkött','oxfile','fläsk','bacon','skinka','kyckling','chicken','fågel','lax','torsk','fisk','räka','räkor','tonfisk','ål','kött','korv']
                for w in banned:
                    text = _re2.sub(rf"\b{w}\b", f"{w}-style", text, flags=_re2.IGNORECASE)
            return text

        presets_list = constraints.get('presets') or []
        diet_lbl = _diet_label(presets_list) or ''
        suffix_parts = [diet_lbl] if diet_lbl else []
        suffix_parts.extend(_constraint_labels(constraints))
        suffix = f" ({' · '.join([s for s in suffix_parts if s])})" if suffix_parts else ''
        # Allow client-provided custom title as base
        custom_title = (payload.get('customTitle') or '').strip()
        base_title_text = (custom_title or result.get('title') or base_content.get('title') or '').strip()
        base_title_text = _neutralize_for_diet(base_title_text, presets_list)
        display_title = (base_title_text + suffix)[:70] if base_title_text else (base_content.get('title','Recipe') + suffix)[:70]
        slug = _slugify(display_title)

        conversion_meta.update({ 'displayTitle': display_title, 'slug': slug, 'ownerUserId': current_user.id })

        # New full content
        new_content = {
            **base_content,
            'title': display_title,
            'ingredients': ingredients,
            'instructions': instructions,
            'nutritional_information': nutrition or None,
            'conversion': conversion_meta,
        }

        # Duplicate check: same parent, same owner, same constraints JSON
        import json
        constraints_key = json.dumps(constraints, sort_keys=True, ensure_ascii=False)
        existing_variant = None
        try:
            with db.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id, recipe_content FROM saved_recipes WHERE user_id = ?", (current_user.id,))
                for rid, rc_json in c.fetchall():
                    try:
                        rc = json.loads(rc_json)
                    except Exception:
                        continue
                    conv = (rc or {}).get('conversion') or {}
                    if conv.get('isVariant') and conv.get('parentRecipeId') == recipe_id:
                        c_json = json.dumps(conv.get('constraints') or [], sort_keys=True, ensure_ascii=False)
                        if c_json == constraints_key:
                            existing_variant = db.get_saved_recipe(rid)
                            break
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")

        if existing_variant:
            payload_json = jsonable_encoder(existing_variant)
            return JSONResponse(content={**payload_json, 'adjustments': adjustments})

        # optional image override from client
        img = (payload.get('image') or {})
        src = (img.get('source') or '').lower()
        url_override = img.get('url')
        if src == 'ai' and url_override:
            new_content['image_url'] = url_override
            new_content['thumbnail_path'] = url_override
            new_content['conversion']['image'] = {
                'source': 'ai', 'url': url_override,
                'meta': {
                    'provider': 'replicate',
                    'model': 'black-forest-labs/flux-schnell',
                    'size': 'auto'
                }
            }

        saved = db.save_recipe(current_user.id, base.source_url or '', new_content)
        if not saved:
            raise HTTPException(status_code=500, detail="Variant save failed: DB save returned None")
        saved_json = jsonable_encoder(saved)
        return JSONResponse(content={**saved_json, 'adjustments': adjustments})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/convert failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def _normalize_presets_backend(selected):
    # Backend mirror of preset rules to ensure consistency
    selected = list(dict.fromkeys(selected or []))
    groups = {
        'dietStyle': ['vegan','vegetarian','pescetarian'],
        'addOns': ['add-meat','add-fish','add-dairy'],
        'exclusions': ['dairy-free','lactose-free','gluten-free','nut-free','soy-free','egg-free','fish-free','shellfish-free','halal','kosher','paleo'],
        'macros': ['low-carb','keto','low-fat','high-protein'],
        'programs': ['Mediterranean','Whole30']
    }
    diet_priority = ['vegan','vegetarian','pescetarian']
    macro_priority = ['keto','low-carb']
    resolved = set(selected)
    auto_unselected, auto_added, auto_disabled = set(), set(), set()

    chosen_diet = next((p for p in diet_priority if p in resolved), None)
    if chosen_diet:
        for d in groups['dietStyle']:
            if d != chosen_diet and d in resolved:
                resolved.discard(d)
                auto_unselected.add(d)

    chosen_macro = next((m for m in macro_priority if m in resolved), None)
    if chosen_macro == 'keto' and 'low-carb' in resolved:
        resolved.discard('low-carb'); auto_unselected.add('low-carb'); auto_added.add('keto')

    if chosen_diet == 'vegan':
        for d in ['vegetarian','pescetarian']:
            if d in resolved: resolved.discard(d); auto_unselected.add(d); auto_disabled.add(d)
        for p in ['add-meat','add-fish','add-dairy']:
            if p in resolved: resolved.discard(p); auto_unselected.add(p)
            auto_disabled.add(p)
        # Auto-add and lock exclusions for vegan (locking is UI-side; backend just adds)
        for ex in ['dairy-free','egg-free','fish-free','shellfish-free']:
            if ex not in resolved:
                resolved.add(ex)
                auto_added.add(ex)
    elif chosen_diet == 'plant-based':
        for p in ['add-meat','add-fish']:
            if p in resolved: resolved.discard(p); auto_unselected.add(p)
            auto_disabled.add(p)
    elif chosen_diet == 'vegetarian':
        for p in ['pescetarian','add-meat']:
            if p in resolved: resolved.discard(p); auto_unselected.add(p)
            auto_disabled.add(p)
    elif chosen_diet == 'pescetarian':
        if 'add-meat' in resolved: resolved.discard('add-meat'); auto_unselected.add('add-meat'); auto_disabled.add('add-meat')

    if 'dairy-free' in resolved and 'add-dairy' in resolved:
        resolved.discard('add-dairy'); auto_unselected.add('add-dairy'); auto_disabled.add('add-dairy')
    if 'fish-free' in resolved and 'add-fish' in resolved:
        resolved.discard('add-fish'); auto_unselected.add('add-fish'); auto_disabled.add('add-fish')

    # Programs
    if 'Whole30' in resolved and 'vegan' in resolved:
        resolved.discard('vegan'); auto_unselected.add('vegan'); auto_disabled.add('vegan')

    return list(resolved), { 'autoUnselected': list(auto_unselected), 'autoAdded': list(auto_added), 'autoDisabled': list(auto_disabled) }

def _feasibility_check(nutrition: dict, tolerance_pct: int = 5):
    try:
        n = nutrition or {}
        kcal_min = n.get('minCalories')
        kcal_max = n.get('maxCalories')
        prot_min = float(n.get('minProtein') or 0)
        carb_min = float(n.get('minCarbs') or 0)
        fat_min  = float(n.get('minFat') or 0)
        prot_max = n.get('maxProtein')
        carb_max = n.get('maxCarbs')
        fat_max  = n.get('maxFat')
        lowest_possible = 4*(prot_min + carb_min) + 9*fat_min
        highest_possible = None
        if prot_max is None and carb_max is None and fat_max is None:
            highest_possible = float('inf')
        else:
            highest_possible = 4*float(prot_max or 0) + 4*float(carb_max or 0) + 9*float(fat_max or 0)
        if kcal_max is not None and lowest_possible > float(kcal_max):
            return ('impossible', 'min macros exceed kcal max')
        if kcal_min is not None and highest_possible != float('inf') and highest_possible < float(kcal_min):
            return ('impossible', 'max macros below kcal min')
        tol = max(0, int(tolerance_pct or 0))/100.0
        tight = False
        if kcal_max is not None:
            margin = max(0.0, float(kcal_max) - lowest_possible)
            if margin <= float(kcal_max) * tol:
                tight = True
        if not tight and kcal_min is not None and highest_possible != float('inf'):
            margin = max(0.0, highest_possible - float(kcal_min))
            if margin <= float(kcal_min) * tol:
                tight = True
        return ('tight' if tight else 'possible', '')
    except Exception as e:
        return ('possible', '')

# --- LLM proxy: DeepSeek convert (server-side to avoid CORS and key exposure) ---
@router.post("/llm/deepseek/convert")
@limiter.limit("30/minute")
async def deepseek_convert_proxy(request: Request, payload: dict = Body(...)):
    # Lightweight in-memory cache and de-duplication to speed up repeated conversions
    # Keyed by hash of (model, base_url, fast flag, userPayload JSON, truncated system prompt hash)
    global _CONVERT_CACHE, _CONVERT_INFLIGHT
    try:
        _CONVERT_CACHE
    except NameError:
        _CONVERT_CACHE = {}
    try:
        _CONVERT_INFLIGHT
    except NameError:
        _CONVERT_INFLIGHT = {}
    _CONVERT_TTL = 600  # seconds
    _CONVERT_MAX = 128

    def _cache_get(key: str):
        entry = _CONVERT_CACHE.get(key)
        if not entry:
            return None
        if (time.time() - entry['t']) > _CONVERT_TTL:
            _CONVERT_CACHE.pop(key, None)
            return None
        return entry['data']

    def _cache_set(key: str, data: dict):
        _CONVERT_CACHE[key] = {'t': time.time(), 'data': data}
        if len(_CONVERT_CACHE) > _CONVERT_MAX:
            # Evict oldest
            oldest_key = min(_CONVERT_CACHE.items(), key=lambda kv: kv[1]['t'])[0]
            _CONVERT_CACHE.pop(oldest_key, None)

    try:
        api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing DEEPSEEK_API_KEY on server")
        system_prompt = payload.get('systemPrompt') or ''
        user_payload = payload.get('userPayload') or {}
        model = payload.get('model') or 'deepseek-chat'
        base_url = payload.get('baseURL') or 'https://api.deepseek.com'
        fast = bool(payload.get('fast'))

        # Compute cache key
        try:
            up_str = json.dumps(user_payload, sort_keys=True, ensure_ascii=False)
        except Exception:
            up_str = str(user_payload)
        sp_hash = _hashlib.sha1((system_prompt or '').encode('utf-8')).hexdigest()[:10]
        key_raw = f"{model}|{base_url}|fast={int(fast)}|{sp_hash}|{up_str}"
        key = _hashlib.sha1(key_raw.encode('utf-8')).hexdigest()

        # Serve from cache if available
        cached = _cache_get(key)
        if cached is not None:
            return JSONResponse(cached)

        # If an identical request is already in-flight, await it
        inflight = _CONVERT_INFLIGHT.get(key)
        if inflight is not None:
            try:
                data = await inflight
                return JSONResponse(data)
            except Exception:
                # Fall through to perform our own call
                pass

        # Create a future placeholder to deduplicate subsequent callers
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        _CONVERT_INFLIGHT[key] = future
        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)}
        ]
        logger.info(f"DeepSeek proxy call model={model} base={base_url} fast={fast} len_system={len(system_prompt or '')} bytes_user={len(json.dumps(user_payload) or '')}")
        async def _call(messages, *, max_tokens: Optional[int] = None, temperature: float = 0.7, timeout_s: float = 60.0):
            # Longer server-side timeout to avoid ReadTimeout for bigger recipes
            timeout = httpx.Timeout(timeout_s, connect=10.0, read=timeout_s, write=timeout_s/2)
            async with httpx.AsyncClient(timeout=timeout, base_url=base_url) as client:
                try:
                    r = await client.post('/v1/chat/completions', headers={
                        'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'
                    }, json={
                        'model': model, 'messages': messages,
                        'temperature': temperature,
                        **({'max_tokens': max_tokens} if max_tokens is not None else {})
                    })
                    r.raise_for_status()
                except httpx.HTTPStatusError as he:
                    body = (he.response.text or '')
                    logger.error(f"DeepSeek HTTP error {he.response.status_code}: {body[:500]}")
                    # Retry once without any extra params (some providers reject unknown fields)
                    r = await client.post('/v1/chat/completions', headers={
                        'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'
                    }, json={
                        'model': model, 'messages': messages,
                        **({'max_tokens': max_tokens} if max_tokens is not None else {})
                    })
                    try:
                        r.raise_for_status()
                    except httpx.HTTPStatusError as he2:
                        body2 = (he2.response.text or '')
                        logger.error(f"DeepSeek HTTP error (retry) {he2.response.status_code}: {body2[:500]}")
                        raise HTTPException(status_code=502, detail=f"DeepSeek upstream error {he2.response.status_code}: {body2[:300]}")
                except (httpx.ReadTimeout, httpx.TimeoutException) as te:
                    logger.error(f"DeepSeek timeout: {te}")
                    raise
                data = r.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return content
        def _extract_json(text: str):
            # Strip code fences if present
            t = text.strip()
            if t.startswith("```"):
                # remove first fence line and last fence
                lines = t.splitlines()
                # drop first line (``` or ```json)
                if lines:
                    lines = lines[1:]
                # drop trailing fence if exists
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                t = "\n".join(lines).strip()
            # naive brace extraction
            start = t.find('{')
            end = t.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = t[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
            # last attempt parse whole
            try:
                return json.loads(t)
            except Exception:
                return None

        # First attempt: if fast-mode, use compact instructions and tighter budget up-front
        try:
            if fast:
                compact_system = "Return STRICT JSON only. Keys: title, substitutions, ingredients, instructions, notes, nutritionPerServing, compliance. No markdown. Keep output concise."
                msgs_fast = [
                    {"role": "system", "content": compact_system},
                    {"role": "user", "content": json.dumps(user_payload)}
                ]
                content = await _call(msgs_fast, max_tokens=550, temperature=0.2, timeout_s=40.0)
            else:
                content = await _call(msgs, max_tokens=900, temperature=0.2, timeout_s=65.0)
        except (httpx.ReadTimeout, httpx.TimeoutException):
            # Fallback: compact instructions to force short, fast JSON
            compact_system = "Return STRICT JSON only. Keys: title, substitutions, ingredients, instructions, notes, nutritionPerServing, compliance. No markdown. Keep output concise."
            compact_msgs = [
                {"role": "system", "content": compact_system},
                {"role": "user", "content": json.dumps(user_payload)}
            ]
            content = await _call(compact_msgs, max_tokens=700, temperature=0.2, timeout_s=65.0)
        parsed = _extract_json(content)
        if parsed is not None:
            try:
                # Server-side diet enforcement to avoid non-compliant outputs
                try:
                    constraints = (payload.get('userPayload') or {}).get('constraints') or {}
                    parsed = await _enforce_diet_constraints(parsed, constraints)
                except Exception as _e:
                    logger.warning(f"Diet postprocess failed: {_e}")
                _cache_set(key, parsed)
                if not future.done():
                    future.set_result(parsed)
            finally:
                _CONVERT_INFLIGHT.pop(key, None)
            return JSONResponse(parsed)

        # Second attempt: add strict instruction and retry
        msgs.append({"role": "user", "content": "Return STRICT JSON only. No markdown, no prose. Enforce vegan/vegetarian rules strictly when requested; do not leave animal products in ingredients."})
        content = await _call(msgs)
        parsed = _extract_json(content)
        if parsed is not None:
            try:
                try:
                    constraints = (payload.get('userPayload') or {}).get('constraints') or {}
                    parsed = await _enforce_diet_constraints(parsed, constraints)
                except Exception as _e:
                    logger.warning(f"Diet postprocess failed: {_e}")
                _cache_set(key, parsed)
                if not future.done():
                    future.set_result(parsed)
            finally:
                _CONVERT_INFLIGHT.pop(key, None)
            return JSONResponse(parsed)

        # Third attempt: ask model to reformat the previous content into JSON
        repair_msgs = [
            {"role": "system", "content": "You are a formatter. Output EXACT JSON object only. No markdown."},
            {"role": "user", "content": f"Reformat into strict JSON object: {content}"}
        ]
        content2 = await _call(repair_msgs)
        parsed = _extract_json(content2)
        if parsed is not None:
            try:
                try:
                    constraints = (payload.get('userPayload') or {}).get('constraints') or {}
                    parsed = await _enforce_diet_constraints(parsed, constraints)
                except Exception as _e:
                    logger.warning(f"Diet postprocess failed: {_e}")
                _cache_set(key, parsed)
                if not future.done():
                    future.set_result(parsed)
            finally:
                _CONVERT_INFLIGHT.pop(key, None)
            return JSONResponse(parsed)

        # Surface first part of model output to help diagnose
        snippet = (content or '')
        if isinstance(snippet, str):
            snippet = snippet.strip().replace('\n', ' ')[:300]
        try:
            if not future.done():
                future.set_exception(Exception("non-json"))
        finally:
            _CONVERT_INFLIGHT.pop(key, None)
        raise HTTPException(status_code=500, detail=f"DeepSeek returned non-JSON: {snippet}")
    except HTTPException:
        raise
    except Exception as e:
        # Surface cause to client for quick diagnosis
        msg = str(e) if str(e) else e.__class__.__name__
        logger.error(f"DeepSeek proxy failed: {msg}")
        raise HTTPException(status_code=500, detail=f"DeepSeek proxy error: {msg}")

# --- Nutrition Calculation ---
@router.post("/nutrition/calc", response_model=NutritionResult)
async def calculate_nutrition(request: NutritionCalcRequest):
    """Calculate nutrition from ingredients using USDA database"""
    try:
        logging.info(f"Nutrition endpoint called with {len(request.ingredients)} ingredients, {request.servings} servings")
        
        # Persist recipe_ingredients resolution (best-effort)
        try:
            rid = None
            try:
                rid = int(request.recipeId)
            except Exception:
                rid = None
            lang_guess = 'sv'
            for item in (request.ingredients or []):
                raw = (item.get('raw') or '').strip()
                if not raw:
                    continue
                res = resolve(raw, lang_guess)
                db.insert_recipe_ingredient(rid or 0, raw, res.get('canonical_ingredient_id'), res.get('confidence'), res.get('source'))
        except Exception as _e_persist:
            logging.warning(f"persist recipe_ingredients failed: {_e_persist}")

        # Use real USDA integration
        calculator = NutritionCalculator()
        result = await calculator.calculate_nutrition(request.ingredients, request.servings, recipe_id=request.recipeId)

        # Concise, human-readable summary instead of dumping entire object
        try:
            ps = (result or {}).get('perServing', {}) or {}
            warnings_count = len((result or {}).get('warnings', []) or [])
            review_count = len((result or {}).get('needsReview', []) or [])
            debug_len = len((result or {}).get('debugEntries', []) or [])
            compact = (
                f"kcal={ps.get('calories', '—')} "
                f"protein={ps.get('protein', '—')}g "
                f"fat={ps.get('fat', '—')}g "
                f"carbs={ps.get('carbs', '—')}g "
                f"salt={(ps.get('salt') if ps.get('salt') is not None else (round((ps.get('sodium', 0) * 2.5 / 1000), 1) if isinstance(ps.get('sodium'), (int, float)) else '—'))}g"
            )
            logging.info(
                "Nutrition done: servings=%s items=%s %s | warnings=%s needsReview=%s debugEntries=%s",
                request.servings,
                len(request.ingredients or []),
                compact,
                warnings_count,
                review_count,
                debug_len,
            )
        except Exception:
            pass
        return NutritionResult(**result)
    except Exception as e:
        logging.error(f"Nutrition calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Nutrition calculation failed")

@router.get("/nutrition/{recipe_id}")
async def get_nutrition_snapshot(recipe_id: int):
    """Return cached nutrition snapshot; enqueue compute only on first miss to avoid poll loops."""
    try:
        snap = db.get_nutrition_snapshot(recipe_id)
        if snap:
            status = snap.get("status", "pending")
            resp = {"status": status, "meta": snap.get("meta"), "updated_at": snap.get("updated_at")}
            if status == "ready" and snap.get("snapshot"):
                resp["data"] = snap.get("snapshot")
            # Timeout: if pending > 15s, flip to error so klienten ser något (reduced from 30s)
            if status == "pending":
                from datetime import datetime, timedelta
                try:
                    ts = snap.get("updated_at")
                    dt = datetime.fromisoformat(ts) if isinstance(ts, str) else None
                    if dt and (datetime.now() - dt) > timedelta(seconds=15):
                        db.upsert_nutrition_snapshot(recipe_id, status="error", snapshot=None, meta={"error": "timeout"})
                        return {"status": "error", "meta": {"error": "timeout"}}
                except Exception:
                    pass
            return resp
        # No record yet → set pending + enqueue once
        try:
            db.upsert_nutrition_snapshot(recipe_id, status="pending", snapshot=None, meta={"reason": "miss", "queued": True})
        except Exception:
            pass
        try:
            import asyncio
            asyncio.create_task(enqueue_nutrition_compute(int(recipe_id)))
        except Exception:
            pass
        return {"status": "pending", "meta": {"queued": True}}
    except Exception as e:
        logging.error(f"get_nutrition_snapshot error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get nutrition snapshot")

@router.post("/ingredients/resolve")
async def resolve_ingredient(payload: dict = Body(...)):
    """Resolve an ingredient string to canonical id with confidence and source."""
    try:
        text = (payload.get('text') or '').strip()
        lang = (payload.get('lang') or 'sv').strip().lower()
        if not text:
            raise HTTPException(status_code=400, detail="text required")
        res = resolve(text, lang)
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"resolve_ingredient failed: {e}")
        raise HTTPException(status_code=500, detail="resolve failed")

@router.get("/ingredients/translations")
async def get_ingredient_translations(lang: str = 'sv', ids: Optional[str] = None):
    try:
        # Optional on-demand backfill if ids provided (comma-separated canonical ids)
        if ids:
            for part in ids.split(','):
                try:
                    cid = int(part)
                    translate_canonical(cid, lang)
                except Exception:
                    continue
        mapping = db.get_translations_for_lang(lang)
        return mapping
    except Exception as e:
        logger.error(f"get_ingredient_translations failed: {e}")
        raise HTTPException(status_code=500, detail="translations failed")



@router.post("/nutrition/{recipe_id}/recompute")
async def recompute_nutrition_snapshot(recipe_id: int):
    """Force a recomputation: set status=pending and enqueue job once."""
    try:
        try:
            db.upsert_nutrition_snapshot(recipe_id, status="pending", snapshot=None, meta={"reason": "manual_recompute"})
        except Exception:
            pass
        try:
            import asyncio
            asyncio.create_task(enqueue_nutrition_compute(int(recipe_id)))
        except Exception:
            pass
        return {"ok": True, "status": "pending"}
    except Exception as e:
        logger.error(f"recompute_nutrition_snapshot error: {e}")
        raise HTTPException(status_code=500, detail="Failed to enqueue recompute")

@router.post("/nutrition/{recipe_id}/sync")
async def sync_compute_nutrition(recipe_id: int):
    """Dev fallback: compute synchronously and save ready snapshot immediately."""
    try:
        from core.database import db as _db
        try:
            rid = int(recipe_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid recipe id")
        rec = _db.get_saved_recipe(rid)
        if not rec:
            raise HTTPException(status_code=404, detail="recipe not found")
        content = rec.recipe_content.model_dump() if hasattr(rec.recipe_content, 'model_dump') else {}
        ingredients = []
        for ing in content.get('ingredients', []) or []:
            if isinstance(ing, str):
                ingredients.append({'raw': ing})
            elif isinstance(ing, dict):
                ingredients.append({'raw': f"{ing.get('quantity') or ''} {ing.get('name') or ''}".strip()})
        servings = int(content.get('serves') or 4)
        from logic.safe_mode_calculator import compute_safe_snapshot
        calc_res = await compute_safe_snapshot(ingredients, servings)
        per = (calc_res or {}).get('perServing', {})
        nonzero = sum(1 for v in per.values() if isinstance(v, (int, float)) and v)
        if nonzero == 0:
            db.upsert_nutrition_snapshot(rid, status="error", snapshot=None, meta={"error": "empty snapshot"})
            return {"status": "error", "meta": {"error": "empty snapshot"}}
        db.upsert_nutrition_snapshot(rid, status="ready", snapshot=calc_res, meta={"timing": {"mode": "sync"}})
        return {"status": "ready", "data": calc_res}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"sync_compute_nutrition error: {e}")
        raise HTTPException(status_code=500, detail="sync compute failed")
