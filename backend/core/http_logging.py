from __future__ import annotations

import time
from uuid import uuid4

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid4())
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        # Loguru: usa bind(...) para campos estructurados; nunca pases kwargs a .info()
        try:
            logger.bind(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(duration_ms, 2),
            ).info("http_request")
        except Exception as e:
            # Cualquier fallo de logging NO debe romper la respuesta
            logger.error(f"request_log_error: {e}")

        return response
