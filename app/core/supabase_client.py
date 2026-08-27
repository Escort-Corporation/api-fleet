from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Client authenticated with the secret key. Used for anything that doesn't need
    to be scoped to a specific user's RLS context — e.g. validating a Bearer token
    issued by api-auth's Supabase Auth (same project, see ARCHITECTURE.md section 8).
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_secret_key)


@lru_cache
def get_supabase_admin_client() -> Client:
    """Client authenticated with the secret key. Bypasses RLS — backend-only, never
    exposed to clients. Used for writes to vehicles/vehicle_ownerships."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def get_supabase_client_for_token(access_token: str) -> Client:
    """Client scoped to a specific user's access token, so RLS is enforced by the database."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_secret_key)
    client.postgrest.auth(access_token)
    return client
