import os
from typing import Optional
from supabase import create_client, Client
from app.config import settings

_supabase_admin_client: Optional[Client] = None

def get_supabase_admin_client() -> Client:
    """
    Returns authoritative server-side Supabase client using SERVICE_ROLE_KEY.
    Used strictly by backend services to execute authoritative mutations and write audit logs.
    """
    global _supabase_admin_client
    if _supabase_admin_client is not None:
        return _supabase_admin_client

    url = settings.SUPABASE_URL or os.getenv("SUPABASE_URL")
    key = settings.SUPABASE_SERVICE_ROLE_KEY or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key or "your-project" in url or "your_supabase" in key:
        raise ValueError(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured in .env. "
            "Rule 1: Stop and notify user when credentials are missing; do not fall back to mock data."
        )

    _supabase_admin_client = create_client(url, key)
    return _supabase_admin_client

def get_supabase_user_client(access_token: str) -> Client:
    """
    Returns user-scoped Supabase client initialized with user's JWT.
    Enforces Row Level Security (RLS) policies at the database layer.
    """
    url = settings.SUPABASE_URL or os.getenv("SUPABASE_URL")
    anon_key = settings.SUPABASE_ANON_KEY or os.getenv("SUPABASE_ANON_KEY")

    if not url or not anon_key or "your-project" in url or "your_supabase" in anon_key:
        raise ValueError(
            "SUPABASE_URL or SUPABASE_ANON_KEY is not configured in .env. "
            "Rule 1: Stop and notify user when credentials are missing; do not fall back to mock data."
        )

    client = create_client(url, anon_key)
    client.postgrest.auth(access_token)
    return client
