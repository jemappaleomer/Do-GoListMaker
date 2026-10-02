from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Client:
    """Returns a client using project credentials."""
    supabase_key = settings.key
    if not settings.SUPABASE_URL or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY) must be set in environment variables.")
    return create_client(settings.SUPABASE_URL, supabase_key)

def get_authenticated_client(access_token: str) -> Client:
    """Returns a client scoped with user's access token for RLS policies.
    
    Note: In supabase-py v2.x, postgrest.auth() updates postgrest.headers 
    but NOT postgrest.session.headers (they are separate objects). 
    We must update both so the actual HTTP requests carry the user's JWT.
    """
    supabase_key = settings.key
    client = create_client(settings.SUPABASE_URL, supabase_key)
    # Set the token on the postgrest client's own headers
    client.postgrest.auth(access_token)
    # CRITICAL: Also set it on the HTTP session headers that are actually used for requests
    if hasattr(client.postgrest, 'session') and hasattr(client.postgrest.session, 'headers'):
        client.postgrest.session.headers["authorization"] = f"Bearer {access_token}"
    return client

