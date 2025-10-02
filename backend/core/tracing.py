from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from backend.utils.config import Config

_TRACING_CONFIGURED = False
_HTTPX_INSTRUMENTOR = None


def _parse_headers(raw_headers: Optional[str]) -> Dict[str, str]:
    if not raw_headers:
        return {}
    headers: Dict[str, str] = {}
    for chunk in raw_headers.split(","):
        if not chunk:
            continue
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value
    return headers


def _load_tracing_dependencies() -> Optional[Tuple[Any, ...]]:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:  # pragma: no cover - tracing dependencies are optional
        return None

    return (
        trace,
        FastAPIInstrumentor,
        HTTPXClientInstrumentor,
        Resource,
        TracerProvider,
        BatchSpanProcessor,
        OTLPSpanExporter,
    )


def configure_tracing(app) -> bool:  # type: ignore[no-untyped-def]
    global _TRACING_CONFIGURED, _HTTPX_INSTRUMENTOR
    if _TRACING_CONFIGURED or not getattr(Config, "ENABLE_TRACING", False):
        return False

    dependencies = _load_tracing_dependencies()
    if dependencies is None:
        return False

    (
        trace,
        FastAPIInstrumentor,
        HTTPXClientInstrumentor,
        Resource,
        TracerProvider,
        BatchSpanProcessor,
        OTLPSpanExporter,
    ) = dependencies

    resource = Resource.create({"service.name": Config.OTEL_SERVICE_NAME})

    tracer_provider = trace.get_tracer_provider()
    if not isinstance(tracer_provider, TracerProvider):
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
    else:
        try:
            tracer_provider.resource = tracer_provider.resource.merge(resource)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - older SDK versions
            pass

    exporter_kwargs: Dict[str, Any] = {"timeout": getattr(Config, "OTEL_EXPORTER_OTLP_TIMEOUT", 10)}
    endpoint = getattr(Config, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    if endpoint:
        exporter_kwargs["endpoint"] = endpoint
    headers = _parse_headers(getattr(Config, "OTEL_EXPORTER_OTLP_HEADERS", None))
    if headers:
        exporter_kwargs["headers"] = headers

    try:
        exporter = OTLPSpanExporter(**exporter_kwargs)
    except Exception:  # pragma: no cover - exporter misconfiguration
        return False

    processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(processor)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

    _HTTPX_INSTRUMENTOR = HTTPXClientInstrumentor()
    if not getattr(_HTTPX_INSTRUMENTOR, "_instrumented", False):
        _HTTPX_INSTRUMENTOR.instrument(tracer_provider=tracer_provider)

    _TRACING_CONFIGURED = True
    return True


def reset_tracing_state_for_tests() -> None:
    global _TRACING_CONFIGURED, _HTTPX_INSTRUMENTOR
    if _HTTPX_INSTRUMENTOR is not None:
        try:
            _HTTPX_INSTRUMENTOR.uninstrument()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
    _HTTPX_INSTRUMENTOR = None
    _TRACING_CONFIGURED = False


__all__ = ["configure_tracing", "reset_tracing_state_for_tests"]
