"""Application entrypoint for TaskFlow API."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bootstrap import ensure_bootstrap_admin
from app.config import get_settings
from app.database_init import init_db
from app.observability import REQUEST_COUNT, REQUEST_LATENCY, configure_logging, metrics_response
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.tasks import router as tasks_router
from app.schemas import ErrorResponse
from app.security import add_security_headers, install_rate_limiter, split_csv

settings = get_settings()
configure_logging(settings.LOG_FORMAT)
logger = logging.getLogger("taskflow.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks."""
    if settings.AUTO_CREATE_TABLES:
        init_db()
        logger.info("database_initialized mode=create_all")
    ensure_bootstrap_admin(logger)
    yield


app = FastAPI(
    title="TaskFlow API",
    description="Modern task management REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=split_csv(settings.CORS_ALLOW_ORIGINS),
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=split_csv(settings.CORS_ALLOW_METHODS),
    allow_headers=split_csv(settings.CORS_ALLOW_HEADERS),
)
install_rate_limiter(app)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log each request with latency and attach a request id header."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "request_failed method=%s path=%s request_id=%s duration_ms=%s",
            request.method,
            request.url.path,
            request_id,
            duration_ms,
        )
        raise

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    duration_seconds = duration_ms / 1000
    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status_code=str(response.status_code),
    ).inc()
    REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(duration_seconds)
    response.headers["X-Request-ID"] = request_id
    if settings.ENABLE_SECURITY_HEADERS:
        add_security_headers(response)
    logger.info(
        "request_completed method=%s path=%s status_code=%s request_id=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        duration_ms,
    )
    return response


@app.get("/api/metrics", tags=["observability"])
def prometheus_metrics():
    """Expose Prometheus-compatible metrics."""
    return metrics_response()


def _error_code_from_status(status_code: int) -> str:
    """Map HTTP status codes to stable error codes."""
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
    }
    return code_map.get(status_code, "api_error")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return standardized HTTP error responses."""
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        detail=exc.detail,
        error_code=_error_code_from_status(exc.status_code),
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return standardized request validation error responses."""
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        detail=exc.errors(),
        error_code="validation_error",
        request_id=request_id,
    ).model_dump()
    return JSONResponse(status_code=422, content=payload)


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(health_router, prefix="/api/health", tags=["health"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
