"""Global error handling utilities for the FastAPI backend."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_error_handlers(app: FastAPI) -> None:
    """Attach custom exception handlers to the provided FastAPI application."""

    # ✅ Codex fix: Handle FastAPI HTTP exceptions with structured logging
    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        log_data: dict[str, Any] = {
            "service": "backend",
            "event": "http_error",
            "method": request.method,
            "path": request.url.path,
            "status": exc.status_code,
            "detail": exc.detail,
        }
        logging.error(json.dumps(log_data))
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=exc.headers if exc.headers else None,
        )

    # ✅ Codex fix: Provide consistent validation error responses
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload: Any = None
        if hasattr(request, "json"):
            try:
                payload = await request.json()
            except Exception:  # pragma: no cover - defensive safety
                payload = None

        logging.error(
            json.dumps(
                {
                    "service": "alerts",
                    "event": "alert_validation_error",
                    "detail": str(exc),
                    "payload": jsonable_encoder(payload),
                }
            )
        )
        return JSONResponse({"error": "Validation Error"}, status_code=422)

    # ✅ Codex fix: Capture unexpected exceptions globally
    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log_data: dict[str, Any] = {
            "service": "backend",
            "event": "internal_error",
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "error": str(exc),
        }
        logging.error(json.dumps(log_data))
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
