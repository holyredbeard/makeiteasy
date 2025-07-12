from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from dotenv import load_dotenv
from api.routes import router
from api.auth_routes import router as auth_router
from api.google_auth import router as google_auth_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Create FastAPI app
app = FastAPI(
    title="Make It Easy - Video to PDF Converter",
    description="Transform YouTube how-to videos into comprehensive step-by-step PDF instructions",
    version="1.0.0"
)

# Add CORS middleware to allow React frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8001"],  # React development server and frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(google_auth_router, prefix="/api/v1/auth", tags=["google-auth"])

# Serve the main HTML page
@app.get("/")
async def read_index(request: Request):
    # Check if this is a Google OAuth callback
    code = request.query_params.get("code")
    if code:
        # This is a Google OAuth callback, redirect to the proper handler
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/v1/auth/google/callback?{request.url.query}")
    
    return FileResponse("static/index.html")

# Serve generated PDFs
@app.get("/output/{filename}")
async def serve_pdf(filename: str):
    pdf_path = f"output/{filename}"
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf")
    else:
        return {"error": "PDF not found"}, 404

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)