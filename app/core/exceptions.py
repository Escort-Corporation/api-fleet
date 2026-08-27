import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError as PostgrestAPIError
from supabase_auth.errors import AuthApiError

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for all application-raised errors. Carries everything needed for a standardized response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "VALIDATION_ERROR"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMITED"


class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "INTERNAL_ERROR"


# Known Supabase Auth (GoTrue) error codes -> (AppError subclass, user-facing message).
# Only relevant here for Bearer token validation (get_current_user_id) — api-fleet has
# no signup/login of its own, it validates tokens issued by api-auth's Supabase Auth.
# Reference: https://supabase.com/docs/guides/auth/debugging/error-codes
_AUTH_ERROR_MAP: dict[str, tuple[type[AppError], str]] = {
    "session_not_found": (UnauthorizedError, "Your session has expired. Please log in again."),
    "user_banned": (ForbiddenError, "This account has been suspended."),
}

# Postgres SQLSTATE codes (surfaced by PostgREST) -> (AppError subclass, user-facing message).
_POSTGREST_ERROR_MAP: dict[str, tuple[type[AppError], str]] = {
    "23505": (ConflictError, "A record with this value already exists."),
    "23503": (ConflictError, "Related record was not found."),
    "23502": (ValidationError, "A required field is missing."),
    "23514": (ValidationError, "The provided data violates a data constraint."),
}


def app_error_from_auth_api_error(error: AuthApiError) -> AppError:
    code = getattr(error, "code", None)
    if code in _AUTH_ERROR_MAP:
        error_class, message = _AUTH_ERROR_MAP[code]
        return error_class(message)

    if error.status == status.HTTP_401_UNAUTHORIZED:
        return UnauthorizedError("Invalid or expired credentials.")
    if error.status in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT):
        return ValidationError(error.message or "Invalid request data.")
    if error.status == status.HTTP_429_TOO_MANY_REQUESTS:
        return RateLimitedError("Too many requests. Please try again later.")
    return InternalError("Authentication service error.")


def app_error_from_postgrest_api_error(error: PostgrestAPIError) -> AppError:
    code = getattr(error, "code", None)
    if code in _POSTGREST_ERROR_MAP:
        error_class, message = _POSTGREST_ERROR_MAP[code]
        return error_class(message)
    return InternalError("Database error.")


def _error_response(status_code: int, error_code: str, message: str, details: Any | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": error_code, "message": message, "details": details}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire every exception type the API can raise to a single, predictable JSON error shape."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.status_code, exc.error_code, exc.message, exc.details)

    @app.exception_handler(AuthApiError)
    async def handle_auth_api_error(request: Request, exc: AuthApiError) -> JSONResponse:
        mapped = app_error_from_auth_api_error(exc)
        return _error_response(mapped.status_code, mapped.error_code, mapped.message, mapped.details)

    @app.exception_handler(PostgrestAPIError)
    async def handle_postgrest_api_error(request: Request, exc: PostgrestAPIError) -> JSONResponse:
        mapped = app_error_from_postgrest_api_error(exc)
        return _error_response(mapped.status_code, mapped.error_code, mapped.message, mapped.details)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "VALIDATION_ERROR",
            "Invalid request data.",
            jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
        )
