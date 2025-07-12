from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class Step(BaseModel):
    step_number: int = Field(..., description="The step number in the recipe.")
    description: str = Field(..., description="Detailed description of the cooking step.")
    image_path: Optional[str] = Field(None, description="Path to the image for this step.")

class VideoRequest(BaseModel):
    youtube_url: str = Field(..., description="The YouTube video URL.")
    language: Optional[str] = Field("en", description="Language code (e.g., 'en', 'sv').")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")

class Recipe(BaseModel):
    title: str = Field(..., description="The official title of the recipe.")
    description: Optional[str] = Field(None, description="A short, enticing description of the dish, suitable for a header.")
    serves: Optional[str] = Field(None, description="The number of people the recipe serves (e.g., '4 people').")
    prep_time: Optional[str] = Field(None, description="The preparation time (e.g., '15 minutes').")
    cook_time: Optional[str] = Field(None, description="The cooking time (e.g., '30 minutes').")
    ingredients: List[str] = Field(..., description="A list of all ingredients required for the recipe.")
    steps: List[Step] = Field(..., description="A list of detailed, step-by-step instructions.")
    thumbnail_path: Optional[str] = Field(None, description="Path to the main recipe thumbnail image.")

class YouTubeVideo(BaseModel):
    video_id: str = Field(..., description="The YouTube video ID.")
    title: str = Field(..., description="The title of the video.")
    channel_title: str = Field(..., description="The name of the YouTube channel.")
    thumbnail_url: str = Field(..., description="URL to the video thumbnail.")
    duration: str = Field(..., description="Duration of the video (e.g., '5:30').")
    view_count: str = Field(..., description="Number of views (e.g., '1M views').")
    published_at: str = Field(..., description="When the video was published (e.g., '1 day ago').")
    description: str = Field(..., description="Video description.")

class YouTubeSearchRequest(BaseModel):
    query: str = Field(..., description="Search query for YouTube videos.")
    max_results: Optional[int] = Field(10, description="Maximum number of results to return.")

# User Authentication Models
class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    full_name: str = Field(..., description="User's full name")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User's password (minimum 6 characters)")

class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

class User(UserBase):
    id: int = Field(..., description="Unique user ID")
    is_active: bool = Field(True, description="Whether the user account is active")
    created_at: datetime = Field(..., description="When the user account was created")

class UserInDB(User):
    hashed_password: str = Field(..., description="Hashed password stored in database")

class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    user: User = Field(..., description="User information")

class TokenData(BaseModel):
    email: Optional[str] = None 