"""Observability utilities: structured logging and Prometheus metrics."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "taskflow_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "taskflow_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)


class JsonFormatter(logging.Formatter):
    """Format logs as JSON for ingestion by log platforms."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging(log_format: Literal["plain", "json"]) -> None:
    """Configure application root logger formatting."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s",
            )
        )
    root.handlers = [handler]


def metrics_response() -> Response:
    """Return Prometheus metrics payload response."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

