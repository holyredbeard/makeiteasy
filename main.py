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

# --- App Initialization ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logging.info("--- SERVER RESTART - CODE VERSION 2 ---")

app = FastAPI(
    title="Make It Easy - Video to PDF Converter",
    description="Transform YouTube how-to videos into comprehensive step-by-step PDF instructions",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

app.include_router(recipes_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(google_auth_router, prefix="/api/v1/auth", tags=["google-auth"])

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

def cleanup_multiprocessing():
    try:
        multiprocessing.current_process()._cleanup()
        import multiprocessing.resource_tracker
        if hasattr(multiprocessing.resource_tracker, '_CLEANUP_CALLBACKS'):
            for callback in multiprocessing.resource_tracker._CLEANUP_CALLBACKS:
                try:
                    callback()
                except:
                    pass
    except Exception as e:
        logging.warning(f"Error during multiprocessing cleanup: {e}")

def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup_multiprocessing()
    sys.exit(0)

if __name__ == "__main__":
    import uvicorn
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    multiprocessing.set_start_method('spawn', force=True)
    
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        cleanup_multiprocessing()
