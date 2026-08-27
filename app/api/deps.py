from typing import Annotated

from fastapi import Depends, Header

from app.core.exceptions import UnauthorizedError
from app.core.supabase_client import get_supabase_client


def get_bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user_id(token: Annotated[str, Depends(get_bearer_token)]) -> str:
    """Validates a Bearer token issued by api-auth's Supabase Auth (same project,
    see ARCHITECTURE.md section 8 — api-fleet has no login of its own)."""
    client = get_supabase_client()
    user_response = client.auth.get_user(token)
    if user_response is None or user_response.user is None:
        raise UnauthorizedError("Invalid or expired access token.")
    return user_response.user.id
