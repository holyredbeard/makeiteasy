from typing import List, Optional
from pydantic import BaseModel, HttpUrl

class VideoRequest(BaseModel):
    youtube_url: HttpUrl
    language: str = "en"

class Step(BaseModel):
    number: int
    action: str
    timestamp: str
    explanation: str
    image_path: Optional[str] = None

class VideoContent(BaseModel):
    video_type: str
    title: str
    materials_or_ingredients: List[str]
    steps: List[Step]

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