from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from models.types import User
from core.database import db
import logging

# --- Konfiguration ---
SECRET_KEY = "a_very_secret_key_that_should_be_in_env_file" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dagar

logger = logging.getLogger(__name__)

# --- Token-skapande ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Beroende för att hämta aktiv användare ---
async def get_current_active_user(request: Request) -> Optional[User]:
    """
    Detta är ett centralt beroende som säkert hämtar den inloggade användaren
    från en JWT-token som lagrats i en cookie. 
    - Läser och verifierar token.
    - Hämtar användaren från databasen.
    - Returnerar användarobjektet eller None om användaren inte är inloggad.
    """
    token = request.cookies.get("access_token")
    
    if not token:
        # Ingen token, användaren är anonym
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        # Ogiltig eller utgången token
        return None

    user_in_db = db.get_user_by_email(email)
    
    if user_in_db is None:
        return None
    
    # Konvertera databasobjekt till Pydantic-modell
    user = User(**user_in_db.dict())

    if not user.is_active:
        return None
        
    return user
