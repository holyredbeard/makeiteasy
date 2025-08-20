import asyncio
import logging
from typing import Optional

from core.database import db
from logic.nutrition_calculator import NutritionCalculator
from logic.safe_mode_calculator import compute_safe_snapshot

logger = logging.getLogger(__name__)

_queue: Optional[asyncio.Queue] = None


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def enqueue_nutrition_compute(recipe_id: int):
    q = get_queue()
    await q.put({"type": "nutrition.compute", "recipe_id": int(recipe_id)})
    try:
        db.upsert_nutrition_snapshot(int(recipe_id), status="pending", snapshot=None, meta={"reason": "enqueue"})
    except Exception:
        pass


async def _compute_nutrition_snapshot(recipe_id: int):
    from models.types import SavedRecipe
    try:
        calc = NutritionCalculator()
        # Load recipe and build ingredient raw list
        recipe: Optional[SavedRecipe] = db.get_saved_recipe(int(recipe_id))
        if not recipe:
            logger.warning("nutrition.compute: recipe %s not found", recipe_id)
            db.upsert_nutrition_snapshot(int(recipe_id), status="error", snapshot=None, meta={"error": "not_found"})
            return
        content = recipe.recipe_content.dict() if hasattr(recipe.recipe_content, 'dict') else recipe.recipe_content
        ingredients = content.get('ingredients') or []
        servings = content.get('serves') or content.get('servings') or 4
        try:
            servings = int(servings) if isinstance(servings, (int, float, str)) and str(servings).isdigit() else 4
        except Exception:
            servings = 4
        raw_items = []
        for ing in ingredients:
            if isinstance(ing, str):
                raw_items.append({"raw": ing})
            elif isinstance(ing, dict):
                raw_items.append({"raw": f"{ing.get('quantity') or ''} {ing.get('name') or ''}".strip()})
        
        # Compute with timeout
        import time
        import asyncio
        t0 = time.time()
        
        # Safe Mode first: fast and robust (with timeout)
        try:
            result = await asyncio.wait_for(compute_safe_snapshot(raw_items, servings), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("nutrition.compute safe_mode timeout for recipe=%s", recipe_id)
            db.upsert_nutrition_snapshot(int(recipe_id), status="error", snapshot=None, meta={"error": "safe_mode_timeout"})
            return
        except Exception as e:
            logger.warning("nutrition.compute safe_mode failed for recipe=%s: %s", recipe_id, e)
            result = None
        
        # Smart fallback logic: only use full calculator if safe mode really failed
        should_fallback = False
        if not result or not result.get('perServing'):
            should_fallback = True
            logger.info("nutrition.compute fallback: no result from safe mode for recipe=%s", recipe_id)
        else:
            per = result.get('perServing', {})
            # Check if we have meaningful nutrition data
            calories = per.get('calories', 0)
            protein = per.get('protein', 0) 
            fat = per.get('fat', 0)
            carbs = per.get('carbs', 0)
            
            # Only fallback if ALL major nutrients are zero AND we have skipped ingredients
            skipped = result.get('meta', {}).get('skipped', [])
            if calories == 0 and protein == 0 and fat == 0 and carbs == 0 and len(skipped) > len(raw_items) * 0.5:
                should_fallback = True
                logger.info("nutrition.compute fallback: too many skipped ingredients (%d/%d) for recipe=%s", len(skipped), len(raw_items), recipe_id)
            elif calories > 0:
                # We have reasonable data, don't fallback
                logger.info("nutrition.compute safe mode success: %.1f calories for recipe=%s", calories, recipe_id)
        
        if should_fallback:
            try:
                logger.info("nutrition.compute fallback to full calculator for recipe=%s", recipe_id)
                result = await asyncio.wait_for(calc.calculate_nutrition(raw_items, servings, recipe_id=str(recipe_id)), timeout=30.0)
                # mark meta safe_mode=false if present
                if isinstance(result, dict):
                    meta = result.get('meta') or {}
                    meta['safe_mode'] = False
                    result['meta'] = meta
            except asyncio.TimeoutError:
                logger.warning("nutrition.compute full calculator timeout for recipe=%s", recipe_id)
                db.upsert_nutrition_snapshot(int(recipe_id), status="error", snapshot=None, meta={"error": "full_calculator_timeout"})
                return
            except Exception as _e_fb:
                logger.warning("fallback calculator failed: %s", _e_fb)

        # Hard rule: never write a ready snapshot that is zero across all keys
        try:
            per = (result or {}).get('perServing', {})
            nonzero = sum(1 for v in per.values() if isinstance(v, (int, float)) and v)
            if nonzero == 0:
                db.upsert_nutrition_snapshot(int(recipe_id), status="error", snapshot=None, meta={"error": "empty snapshot"})
                logger.warning("nutrition.compute wrote error=empty snapshot for recipe=%s", recipe_id)
                return
        except Exception:
            pass
        t1 = time.time()
        meta = {"timing": {"total": int((t1 - t0) * 1000)}}
        db.upsert_nutrition_snapshot(int(recipe_id), status="ready", snapshot=result, meta=meta)
        logger.info("nutrition.compute: recipe %s done in %sms", recipe_id, meta['timing']['total'])
    except Exception as e:
        logger.error("nutrition.compute failed for %s: %s", recipe_id, e)
        db.upsert_nutrition_snapshot(int(recipe_id), status="error", snapshot=None, meta={"error": str(e)})


async def worker_loop():
    q = get_queue()
    while True:
        job = await q.get()
        try:
            jtype = job.get("type")
            if jtype == "nutrition.compute":
                await _compute_nutrition_snapshot(job.get("recipe_id"))
            else:
                logger.warning("Unknown job type: %s", jtype)
        except Exception as e:
            logger.error("Job failed: %s", e)
        finally:
            q.task_done()


def start_worker_background(loop: Optional[asyncio.AbstractEventLoop] = None, num_workers: int = 2):
    try:
        loop = loop or asyncio.get_event_loop()
        for i in range(num_workers):
            loop.create_task(worker_loop())
        logger.info("Job workers started (%d workers)", num_workers)
    except Exception as e:
        logger.error("Failed to start job workers: %s", e)


