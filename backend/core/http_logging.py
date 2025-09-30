from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging_config import get_logger

logger = get_logger(component="http")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid4())
        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception as exc:  # pragma: no cover - defensive logging
            duration_ms = (time.perf_counter() - start) * 1000
            logger.bind(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
            ).exception("http_request_error", error=str(exc))
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        ).info("http_request")

        return response
