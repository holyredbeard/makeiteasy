import os
from typing import Optional

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# OAuth URLs
GOOGLE_OAUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Redirect URI - update this to match your domain
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000")

# OAuth Scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

def get_google_oauth_config():
    """Get Google OAuth configuration"""
    return {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scopes": GOOGLE_SCOPES
    }

def is_google_oauth_configured() -> bool:
    """Check if Google OAuth is properly configured"""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET) 