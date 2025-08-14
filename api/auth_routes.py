from fastapi import APIRouter, HTTPException, Depends, status, Response, UploadFile, Request
from fastapi.responses import JSONResponse
from models.types import UserCreate, UserLogin, Token, User
from core.database import db
from core.auth import create_access_token, get_current_active_user
from datetime import timedelta, datetime
import os
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register")
async def register_user(user_data: UserCreate, response: Response):
    """Register a new user and log them in by setting a cookie."""
    existing_user = db.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = db.create_user(user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    access_token = create_access_token(
        data={"sub": user.email}
    )
    
    logger.info(f"New user registered and logged in: {user.email}")
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False # Set secure=True in production with HTTPS
    )
    
    return {"message": "Registration successful", "user": user.dict()}


@router.post("/login")
async def login_user(user_data: UserLogin, response: Response):
    """Login user and set access_token cookie"""
    user = db.authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email}
    )
    
    logger.info(f"User logged in: {user.email}")
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False # Set secure=True in production with HTTPS
    )
    
    return {"message": "Login successful", "user": user.dict()}

@router.post("/logout")
async def logout(response: Response):
    """Logs out the user by clearing the access token cookie."""
    logger.info("User logging out.")
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return current_user

@router.get("/check-username")
async def check_username(u: str):
    """Check if a username is available."""
    try:
        u = (u or '').strip().lower()
        if not u or len(u) < 3 or len(u) > 20:
            return {"available": False}
        import re
        if not re.match(r"^[a-z0-9_]{3,20}$", u):
            return {"available": False}
        from core.database import db as _db
        with _db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (u,))
            row = c.fetchone()
            return {"available": row is None}
    except Exception:
        return {"available": False}

@router.post("/profile")
async def update_profile(request: Request, current_user: User = Depends(get_current_active_user)):
    """Update profile fields: full_name, username, email, password, avatar (multipart)."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        form = await request.form()
        full_name = form.get('full_name')
        username = form.get('username')
        email = form.get('email')
        location = form.get('location')
        instagram_url = form.get('instagram_url')
        youtube_url = form.get('youtube_url')
        facebook_url = form.get('facebook_url')
        tiktok_url = form.get('tiktok_url')
        website_url = form.get('website_url')
        password = form.get('password')
        remove_avatar = str(form.get('remove_avatar', 'false')).lower() == 'true'
        avatar = form.get('avatar')  # UploadFile if provided
        logger.info(f"[PROFILE] user={current_user.email} full_name?={bool(full_name)} username?={bool(username)} email?={bool(email)} password?={bool(password)} remove_avatar={remove_avatar} avatar_file={getattr(avatar,'filename',None)}")

        # persist to DB
        from core.database import db as _db
        with _db.get_connection() as conn:
            c = conn.cursor()
            # Unique checks
            if username:
                u_norm = username.strip().lower()
                c.execute("SELECT id FROM users WHERE username = ? AND id <> ?", (u_norm, current_user.id))
                if c.fetchone():
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
            if full_name:
                c.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, current_user.id))
            if username:
                c.execute("UPDATE users SET username=? WHERE id=?", (username.strip().lower(), current_user.id))
            if email:
                c.execute("UPDATE users SET email=? WHERE id=?", (email, current_user.id))
            if location is not None:
                c.execute("UPDATE users SET location=? WHERE id=?", (location, current_user.id))
            if instagram_url is not None:
                c.execute("UPDATE users SET instagram_url=? WHERE id=?", (instagram_url, current_user.id))
            if youtube_url is not None:
                c.execute("UPDATE users SET youtube_url=? WHERE id=?", (youtube_url, current_user.id))
            if facebook_url is not None:
                c.execute("UPDATE users SET facebook_url=? WHERE id=?", (facebook_url, current_user.id))
            if tiktok_url is not None:
                c.execute("UPDATE users SET tiktok_url=? WHERE id=?", (tiktok_url, current_user.id))
            if website_url is not None:
                c.execute("UPDATE users SET website_url=? WHERE id=?", (website_url, current_user.id))
            if password:
                from core.password import get_password_hash
                c.execute("UPDATE users SET hashed_password=? WHERE id=?", (get_password_hash(password), current_user.id))
            if remove_avatar:
                c.execute("UPDATE users SET avatar_url=NULL WHERE id=?", (current_user.id,))
            # Save avatar if provided (duck-typing to avoid class mismatch)
            if avatar is not None and getattr(avatar, 'filename', None):
                ext = os.path.splitext(avatar.filename)[1] or '.jpg'
                avatars_dir = Path('downloads/avatars')
                avatars_dir.mkdir(parents=True, exist_ok=True)
                filename = f"user_{current_user.id}_{int(time.time())}{ext}"
                filepath = avatars_dir / filename
                with open(filepath, 'wb') as f:
                    content = await avatar.read()
                    f.write(content)
                logger.info(f"[PROFILE] Saved avatar file at {filepath} ({len(content)} bytes)")
                # store public path
                public = f"/downloads/avatars/{filename}"
                c.execute("UPDATE users SET avatar_url=? WHERE id=?", (public, current_user.id))
            conn.commit()
        # Return updated user payload for immediate UI update
        updated = db.get_user_by_id(current_user.id)
        logger.info(f"[PROFILE] Updated user avatar_url={getattr(updated,'avatar_url',None)}")
        return {"ok": True, "user": updated.dict() if updated else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-pdfs")
async def get_user_pdfs(current_user: User = Depends(get_current_active_user)):
    """Get all PDFs generated by the current user"""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_pdfs = db.get_user_pdfs(current_user.id)
    return JSONResponse(content={"pdfs": user_pdfs}) 