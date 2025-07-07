from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import logging
from api.routes import router

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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router, prefix="/api/v1")

# Serve the main HTML page
@app.get("/")
async def read_index():
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