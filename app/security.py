"""Security middleware helpers and request rate limiting."""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import Response

from app.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


def add_security_headers(response: Response) -> None:
    """Attach baseline security headers to an HTTP response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-XSS-Protection", "1; mode=block")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none';")
    if settings.ENABLE_HSTS:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def split_csv(raw: str) -> list[str]:
    """Split comma-separated config values, preserving '*' semantics."""
    cleaned = [item.strip() for item in raw.split(",") if item.strip()]
    if not cleaned:
        return ["*"]
    return cleaned


def install_rate_limiter(app) -> None:
    """Wire slowapi limiter into a FastAPI application."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return standardized rate limit exceeded response."""
    return Response(
        content='{"detail":"Rate limit exceeded."}',
        status_code=429,
        media_type="application/json",
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
