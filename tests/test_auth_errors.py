"""Erros do Supabase Auth na validacao do Bearer token viram a resposta certa ao cliente."""

from supabase_auth.errors import AuthApiError

from app.core.exceptions import UnauthorizedError, app_error_from_auth_api_error


def test_invalid_or_expired_token_is_401_not_500():
    # O Supabase responde 403 bad_jwt para token malformado, com assinatura invalida ou expirado.
    error = AuthApiError("invalid JWT: unable to parse or verify signature", 403, "bad_jwt")
    mapped = app_error_from_auth_api_error(error)
    assert isinstance(mapped, UnauthorizedError) and mapped.status_code == 401


def test_session_not_found_is_401():
    mapped = app_error_from_auth_api_error(AuthApiError("Session not found", 403, "session_not_found"))
    assert mapped.status_code == 401
