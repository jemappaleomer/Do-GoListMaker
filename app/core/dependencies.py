from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from app.core.supabase import get_supabase_client

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    Reads the access_token from HttpOnly cookie.
    If valid, returns a dict with user information and the access token.
    If missing or invalid, returns None without raising an exception.
    """
    token = request.cookies.get("sb_access_token")
    if not token:
        return None
    
    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            user = user_response.user
            # Get profile info from user_metadata or profiles table
            username = user.user_metadata.get("username") if user.user_metadata else None
            if not username:
                username = user.email.split("@")[0] if user.email else "User"

            return {
                "id": str(user.id),
                "email": user.email,
                "username": username,
                "access_token": token
            }
    except Exception:
        return None
    return None

async def get_current_user_required(request: Request) -> Dict[str, Any]:
    """
    Dependency that enforces authentication.
    If not logged in, redirects or raises 401.
    """
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bu işlem için giriş yapmalısınız."
        )
    return user
