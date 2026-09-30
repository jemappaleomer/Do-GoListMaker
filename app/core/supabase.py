from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Client:
    """Returns a client using project credentials."""
    supabase_key = settings.key
    if not settings.SUPABASE_URL or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY) must be set in environment variables.")
    return create_client(settings.SUPABASE_URL, supabase_key)

def get_authenticated_client(access_token: str) -> Client:
    """Returns a client scoped with user's access token for RLS policies."""
    supabase_key = settings.key
    client = create_client(settings.SUPABASE_URL, supabase_key)
    client.postgrest.auth(access_token)
    return client
