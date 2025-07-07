from pydantic import BaseModel, Field
from typing import List, Optional

class VideoRequest(BaseModel):
    youtube_url: str
    language: Optional[str] = "en"
    job_id: Optional[str] = None

class Step(BaseModel):
    step_number: int = Field(..., description="The step number, starting from 1.")
    description: str = Field(..., description="A clear, concise description of the step.")
    image_path: Optional[str] = Field(None, description="Path to a representative image for this step.")
    timestamp: Optional[str] = Field(None, description="Timestamp in MM:SS format indicating when the step occurs in the video.")

class Recipe(BaseModel):
    title: str = Field(..., description="The official title of the recipe.")
    description: Optional[str] = Field(None, description="A short, enticing description of the dish, suitable for a header.")
    serves: Optional[str] = Field(None, description="The number of people the recipe serves (e.g., '4 people').")
    prep_time: Optional[str] = Field(None, description="The preparation time (e.g., '15 minutes').")
    cook_time: Optional[str] = Field(None, description="The cooking time (e.g., '30 minutes').")
    ingredients: List[str] = Field(..., description="A list of all ingredients required for the recipe.")
    steps: List[Step] = Field(..., description="A list of detailed, step-by-step instructions.")
    thumbnail_path: Optional[str] = Field(None, description="Path to the main recipe thumbnail image.")

class YouTubeSearchRequest(BaseModel):
    query: str
    language: str = "en"

class YouTubeVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str
    duration: str
    view_count: str
    published_at: str
    description: str 