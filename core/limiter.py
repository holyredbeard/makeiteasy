from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_user_identifier(request: Request):
    """
    Use the access token from the cookie as the unique identifier for rate limiting.
    Fallback to IP address if the cookie is not present (for unauthenticated users).
    """
    token = request.cookies.get("access_token")
    return token or get_remote_address(request)

# Create a global limiter instance that can be imported by other modules
limiter = Limiter(key_func=get_user_identifier) 