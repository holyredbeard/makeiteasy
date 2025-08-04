import os
import secrets
import time
import urllib.parse
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import requests
import logging
from core.oauth_config import (
    get_google_oauth_config, 
    is_google_oauth_configured,
    GOOGLE_OAUTH_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL
)
from core.database import db
from core.auth import create_access_token
from models.types import Token, User
from datetime import timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

# Store OAuth state temporarily (in production, use Redis or database)
oauth_states = {}

@router.get("/google/config")
async def get_google_config():
    """Get Google OAuth configuration for frontend"""
    config = get_google_oauth_config()
    return {
        "client_id": config["client_id"],
        "enabled": is_google_oauth_configured(),
        "redirect_uri": config["redirect_uri"],  # Debug: show redirect URI
        "env_redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "NOT_SET")  # Debug: show env var
    }

@router.get("/google/url")
async def get_google_auth_url():
    """Get Google OAuth authorization URL"""
    if not is_google_oauth_configured():
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )
    
    config = get_google_oauth_config()
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"timestamp": time.time()}
    
    # Build OAuth URL
    params = {
        "client_id": config["client_id"],
        "redirect_uri": "http://localhost:3000",
        "scope": " ".join(config["scopes"]),
        "response_type": "code",
        "state": state,
        "access_type": "offline",
        "prompt": "consent"
    }
    
    auth_url = f"{GOOGLE_OAUTH_URL}?{urllib.parse.urlencode(params)}"
    
    return {"auth_url": auth_url, "state": state}

@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        # Get authorization code and state from query parameters
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")
        
        if error:
            logger.error(f"Google OAuth error: {error}")
            # Redirect to frontend with error
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8001")
            return RedirectResponse(url=f"{frontend_url}/?error=oauth_error&message={error}")
        
        if not code or not state:
            logger.error("Missing code or state in OAuth callback")
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8001")
            return RedirectResponse(url=f"{frontend_url}/?error=oauth_error&message=missing_parameters")
        
        # Verify state (CSRF protection)
        if state not in oauth_states:
            logger.error(f"Invalid OAuth state: {state}")
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(url=f"{frontend_url}/?error=oauth_error&message=invalid_state")
        
        # Clean up state
        del oauth_states[state]
        
        # Exchange code for access token
        config = get_google_oauth_config()
        token_data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"]
        }
        
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        if not token_response.ok:
            logger.error(f"Failed to exchange code for token: {token_response.text}")
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(url=f"{frontend_url}/?error=oauth_error&message=token_exchange_failed")
        
        token_info = token_response.json()
        access_token = token_info.get("access_token")
        
        if not access_token:
            logger.error("No access token received from Google")
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            return RedirectResponse(url=f"{frontend_url}/?error=oauth_error&message=no_access_token")
        
        # Get user info from Google
        user_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if not user_response.ok:
            logger.error(f"Failed to get user info from Google: {user_response.text}")
            return RedirectResponse(url="/?error=oauth_error&message=user_info_failed")
        
        user_info = user_response.json()
        
        # Extract user data
        email = user_info.get("email")
        name = user_info.get("name", "")
        google_id = user_info.get("id")
        avatar_url = user_info.get("picture")
        
        if not email or not google_id:
            logger.error("Missing email or Google ID in user info")
            return RedirectResponse(url="/?error=oauth_error&message=missing_user_data")
        
        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            user = existing_user
            logger.info(f"Existing user logged in via Google: {email}")
        else:
            # Create new user
            user = db.create_oauth_user(email, name, google_id, avatar_url)
            if not user:
                logger.error(f"Failed to create OAuth user: {email}")
                return RedirectResponse(url="/?error=oauth_error&message=user_creation_failed")
            logger.info(f"New OAuth user created: {email}")
        
        # Create JWT token
        jwt_token = create_access_token(
            data={"sub": user.email}
        )
        
        # Redirect to frontend with token
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8001")
        redirect_url = f"{frontend_url}/?token={jwt_token}&oauth_success=true"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        return RedirectResponse(url="/?error=oauth_error&message=internal_error")

@router.post("/google/callback")
async def google_callback_post(request: Request, response: Response):
    """Handle Google OAuth callback from frontend (POST method)"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        
        # Exchange code for access token
        config = get_google_oauth_config()
        token_data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"]
        }
        
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        if not token_response.ok:
            logger.error(f"Failed to exchange code for token: {token_response.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
        
        token_info = token_response.json()
        access_token = token_info.get("access_token")
        
        if not access_token:
            logger.error("No access token received from Google")
            raise HTTPException(status_code=400, detail="No access token received")
        
        # Get user info from Google
        user_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if not user_response.ok:
            logger.error(f"Failed to get user info from Google: {user_response.text}")
            raise HTTPException(status_code=400, detail="Failed to get user information")
        
        user_info = user_response.json()
        
        # Extract user data
        email = user_info.get("email")
        name = user_info.get("name", "")
        google_id = user_info.get("id")
        avatar_url = user_info.get("picture")
        
        if not email or not google_id:
            logger.error("Missing email or Google ID in user info")
            raise HTTPException(status_code=400, detail="Missing email or Google ID")
        
        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            user = existing_user
            logger.info(f"Existing user logged in via Google: {email}")
        else:
            # Create new user
            user = db.create_oauth_user(email, name, google_id, avatar_url)
            if not user:
                logger.error(f"Failed to create OAuth user: {email}")
                raise HTTPException(status_code=500, detail="Failed to create user")
            logger.info(f"New OAuth user created: {email}")
        
        # Create JWT token
        jwt_token = create_access_token(
            data={"sub": user.email}
        )
        
        # Sätt HTTP-only cookie
        response.set_cookie(
            key="access_token",
            value=jwt_token,
            httponly=True,
            samesite="lax",
            secure=False  # Set to True in production with HTTPS
        )
        
        return {"message": "Login successful", "user": user.dict()}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@router.post("/google/mobile")
async def google_mobile_auth(request: Request):
    """Handle Google OAuth for mobile/SPA applications"""
    try:
        data = await request.json()
        id_token = data.get("id_token")
        
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing id_token")
        
        # Verify the ID token with Google
        verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        response = requests.get(verify_url)
        
        if not response.ok:
            raise HTTPException(status_code=400, detail="Invalid ID token")
        
        user_info = response.json()
        
        # Extract user data
        email = user_info.get("email")
        name = user_info.get("name", "")
        google_id = user_info.get("sub")
        avatar_url = user_info.get("picture")
        
        if not email or not google_id:
            raise HTTPException(status_code=400, detail="Missing email or Google ID")
        
        # Check if user already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            user = existing_user
            logger.info(f"Existing user logged in via Google: {email}")
        else:
            # Create new user
            user = db.create_oauth_user(email, name, google_id, avatar_url)
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create user")
            logger.info(f"New OAuth user created: {email}")
        
        # Create JWT token
        jwt_token = create_access_token(
            data={"sub": user.email}
        )
        
        return Token(
            access_token=jwt_token,
            token_type="bearer",
            user=user
        )
        
    except Exception as e:
        logger.error(f"Google mobile auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed") 