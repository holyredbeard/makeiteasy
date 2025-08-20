from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.limiter import limiter
import os
import logging
import signal
import sys
import multiprocessing
from dotenv import load_dotenv
from api.routes import router as recipes_router
from api.auth_routes import router as auth_router
from api.google_auth import router as google_auth_router
from logic.video_processing import preload_vision_models
from logic.job_queue import start_worker_background

# --- App Initialization ---
# Always load .env and override to ensure fresh keys are picked up on restart
load_dotenv(override=True)
import os as _os_check
import logging as _log_check
_log_check.info(f"ENV CHECK: DEEPSEEK_API_KEY present={bool(_os_check.getenv('DEEPSEEK_API_KEY'))}")
_log_check.info(f"ENV CHECK: REPLICA_API_KEY present={bool(_os_check.getenv('REPLICA_API_KEY')) or bool(_os_check.getenv('REPLICATE_API_TOKEN'))}")

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logging.info("--- SERVER RESTART - CODE VERSION 2 ---")
# Reduce noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

app = FastAPI(
    title="Make It Easy - Video to PDF Converter",
    description="Transform YouTube how-to videos into comprehensive step-by-step PDF instructions",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")
# Serve generated images under /images
app.mount("/images", StaticFiles(directory="public/images"), name="images")

app.include_router(recipes_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(google_auth_router, prefix="/api/v1/auth", tags=["google-auth"])

@app.on_event("startup")
async def startup_event():
    """Start job workers on application startup"""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        start_worker_background(loop, num_workers=2)
        logging.info("Job workers started on startup")
    except Exception as e:
        logging.error(f"Failed to start job workers on startup: {e}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Server is running"}

@app.get("/")
async def read_index(request: Request):
    code = request.query_params.get("code")
    if code:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/v1/auth/google/callback?{request.url.query}")
    
    return FileResponse("static/index.html")

@app.get("/output/{filename}")
async def serve_pdf(filename: str):
    pdf_path = f"output/{filename}"
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf")
    else:
        return {"error": "PDF not found"}, 404



import psutil

def find_and_kill_process_on_port(port):
    """Find and kill a process that is listening on the given port."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    logging.info(f"Found process {proc.info['name']} (PID {proc.info['pid']}) on port {port}. Terminating.")
                    proc.terminate()
                    proc.wait(timeout=3)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            continue
        except Exception as e:
            logging.error(f"Error while trying to kill process on port {port}: {e}")

if __name__ == "__main__":
    import uvicorn
    
    PORT = 8000
    
    # Ensure the port is free before starting the server
    find_and_kill_process_on_port(PORT)
    
    # Set multiprocessing start method
    # This is important for compatibility, especially on macOS and Windows
    multiprocessing.set_start_method('spawn', force=True)
    
    try:
        # Preload vision models (BLIP) för att undvika kallstart vid Generate
        try:
            preload_vision_models()
        except Exception:
            pass
        # Start background job worker
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            start_worker_background(loop, num_workers=2)
            logging.info("Job workers started successfully")
        except Exception as _e:
            logging.warning(f"Job worker could not start: {_e}")
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=PORT,
            reload=True,
            reload_excludes=[
                "stable-diffusion-webui/*",
                "stable-diffusion-webui/venv/*",
                "venv/*",
                "whisper_env/*",
                "pdf_env/*",
            ],
        )
    except Exception as e:
        logging.error(f"Server failed to start: {e}")
    finally:
        # Final cleanup attempt
        find_and_kill_process_on_port(PORT)
        logging.info("Server shutdown complete.")
