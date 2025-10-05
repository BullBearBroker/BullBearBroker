"""Structured logging middleware for FastAPI requests."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that records structured JSON logs for each HTTP request."""

    # ✅ Codex fix: Initialize logging middleware
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and emit structured logs when completed."""

        # ✅ Codex fix: Capture request metadata for structured logging
        start_time = time.monotonic()
        request_id = str(uuid4())
        response: Response | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # ✅ Codex fix: Preserve original exception while ensuring logging occurs
            status_code = 500
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            log_data = {
                "service": "backend",
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
                "request_id": request_id,
                "timestamp": timestamp,
            }
            logging.info(json.dumps(log_data))

        if response is None:
            # ✅ Codex fix: Defensive guard for unexpected middleware behavior
            raise RuntimeError("LoggingMiddleware received no response from downstream application")

        return response
