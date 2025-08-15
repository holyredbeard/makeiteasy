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

router = APIRouter()
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

                    # Stream transcription: convert to 16k mono WAV in a thread and stream segments
                    queue: "asyncio.Queue" = asyncio.Queue()
                    loop = asyncio.get_running_loop()

                    def _blocking_transcribe():
                        wav_tmp = None
                        try:
                            import tempfile, subprocess, os
                            wav_tmpf = tempfile.NamedTemporaryFile(prefix=f"{job_id}_", suffix=".wav", delete=False)
                            wav_tmp = wav_tmpf.name
                            wav_tmpf.close()
                            ffmpeg_cmd = ["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "16000", "-vn", "-f", "wav", wav_tmp]
                            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            for seg in transcribe_audio_stream(wav_tmp, lang_hint=language):
                                # pass segment to async queue
                                loop.call_soon_threadsafe(queue.put_nowait, seg)
                        except Exception as e:
                            logger.error(f"[STREAM_TRANSCRIBE] Error during blocking transcribe: {e}")
                        finally:
                            # signal completion
                            try:
                                loop.call_soon_threadsafe(queue.put_nowait, None)
                            except Exception:
                                pass
                            try:
                                if wav_tmp and os.path.exists(wav_tmp):
                                    os.unlink(wav_tmp)
                            except Exception:
                                pass

                    # kickoff blocking transcription
                    _ = loop.run_in_executor(None, _blocking_transcribe)

                    collected_text_parts = []
                    while True:
                        seg = await queue.get()
                        if seg is None:
                            break
                        text_seg = seg.get("text", "")
                        collected_text_parts.append(text_seg)
                        # stream segment to frontend
                        yield await send_event("transcribing", text_seg, debug_info={"start": seg.get("start"), "end": seg.get("end")})

                    transcript = " ".join([p.strip() for p in collected_text_parts if p and p.strip()])
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
async def list_collection_recipes(request: Request, collection_id: int):
    return db.list_collection_recipes(collection_id)

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
