from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class Ingredient(BaseModel):
    name: str
    quantity: str
    notes: Optional[str] = None

class Instruction(BaseModel):
    step: int
    description: str
    image_path: Optional[str] = None

class RecipeContent(BaseModel):
    title: str
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    servings: Optional[str] = None
    ingredients: List[Ingredient]
    instructions: List[Instruction]
    chef_tips: Optional[List[str]] = None
    template_name: Optional[str] = Field("professional", description="CSS template to use for PDF generation")
    image_orientation: Optional[str] = Field("landscape", description="Image orientation (landscape or portrait)")
    show_top_image: Optional[bool] = Field(True, description="Whether to show the top image in the PDF")
    show_step_images: Optional[bool] = Field(True, description="Whether to show step-by-step images in the PDF")
    language: Optional[str] = Field("en", description="Language for the PDF")
    nutritional_information: Optional[dict] = None
    thumbnail_path: Optional[str] = None
    image_url: Optional[str] = None

class SavedRecipe(BaseModel):
    id: int
    user_id: int
    source_url: str
    created_at: datetime
    recipe_content: RecipeContent

class Step(BaseModel):
    number: int = Field(..., description="The step number in the recipe.")
    description: str = Field(..., description="Detailed description of the cooking step.")
    image_path: Optional[str] = Field(None, description="Path to the image for this step.")

class VideoRequest(BaseModel):
    youtube_url: str = Field(..., description="The YouTube video URL.")
    language: Optional[str] = Field("en", description="Language code (e.g., 'en', 'sv').")
    job_id: Optional[str] = Field(None, description="Optional job ID for tracking.")
    show_top_image: Optional[bool] = Field(True, description="Whether to include the top image in the PDF.")
    show_step_images: Optional[bool] = Field(True, description="Whether to include step-by-step images in the PDF.")

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
    thumbnail_url: Optional[str] = Field(None, description="URL to the video thumbnail.")
    duration: str = Field(..., description="Duration of the video (e.g., '5:30').")
    view_count: str = Field(..., description="Number of views (e.g., '1M views').")
    published_at: Optional[str] = Field(None, description="When the video was published (e.g., '1 day ago').")
    description: Optional[str] = Field(None, description="Video description.")

class YouTubeSearchRequest(BaseModel):
    query: str = Field(..., description="Search query for YouTube videos.")
    page: Optional[int] = Field(1, description="Page number for pagination.")
    source: Optional[str] = Field("youtube", description="The source to search (e.g., 'youtube', 'tiktok').")

# User Authentication Models
class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    full_name: str = Field(..., description="User's full name")
    username: Optional[str] = Field(None, description="User's public username")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User's password (minimum 6 characters)")

class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

class User(UserBase):
    id: int = Field(..., description="Unique user ID")
    is_active: bool = Field(True, description="Whether the user account is active")
    is_admin: bool = Field(False, description="Whether the user has admin privileges")
    daily_usage: int = Field(0, description="Number of PDFs generated today")
    monthly_usage: int = Field(0, description="Number of PDFs generated this month")
    daily_limit: int = Field(10, description="Daily PDF generation limit")
    monthly_limit: int = Field(100, description="Monthly PDF generation limit")
    created_at: Optional[datetime] = Field(None, description="When the user account was created")
    saved_recipes: List[SavedRecipe] = []
    roles: List[str] = Field(default_factory=list, description="Roles assigned to the user")

class UserInDB(User):
    hashed_password: str = Field(..., description="Hashed password stored in database")

class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    user: User = Field(..., description="User information")

class TokenData(BaseModel):
    email: Optional[str] = None

class SaveRecipeRequest(BaseModel):
    source_url: str
    recipe_content: RecipeContent 