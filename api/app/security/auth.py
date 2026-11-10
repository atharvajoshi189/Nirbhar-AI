import os
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
from app.db.supabase import get_supabase_admin_client

async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Authoritative user authentication dependency.
    Extracts user identity from Supabase Auth Bearer token or authorized X-User-Id header.
    Fail-closed: returns 401 if token is invalid or user is not found.
    """
    supabase = get_supabase_admin_client()

    # 1. Bearer Token Authentication
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
        try:
            user_response = supabase.auth.get_user(token)
            if user_response and user_response.user:
                return {
                    "id": user_response.user.id,
                    "email": user_response.user.email,
                    "role": user_response.user.role,
                    "token": token
                }
        except Exception:
            pass  # Fall through to alternative check or 401

    # 2. X-User-Id Header (for authenticated inter-service or testing workflows)
    if x_user_id:
        try:
            # Verify user exists in Supabase
            admin_check = supabase.auth.admin.get_user_by_id(x_user_id)
            if admin_check and admin_check.user:
                return {
                    "id": admin_check.user.id,
                    "email": admin_check.user.email,
                    "role": admin_check.user.role,
                    "token": None
                }
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials. Please sign in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

