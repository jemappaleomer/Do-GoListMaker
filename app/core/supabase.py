from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Client:
    """Returns a client using project credentials."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def get_authenticated_client(access_token: str) -> Client:
    """Returns a client scoped with user's access token for RLS policies."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    client.postgrest.auth(access_token)
    return client
