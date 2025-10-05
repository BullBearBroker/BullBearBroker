"""Métricas Prometheus para el servicio de IA."""

from prometheus_client import Counter, Gauge, Histogram

# ✅ Codex fix: métricas IA estructuradas
ai_requests_total = Counter(
    "ai_requests_total",
    "Total de requests IA",
    ["provider", "status"],
)

ai_latency_seconds = Histogram(
    "ai_latency_seconds",
    "Latencia IA por proveedor",
    ["provider"],
)

ai_fallbacks_total = Counter(
    "ai_fallbacks_total",
    "Número de fallbacks IA",
    ["from_provider", "to_provider"],
)

ai_failures_total = Counter(
    "ai_failures_total",
    "Errores IA",
    ["provider", "error_type"],
)

# ✅ Codex fix: métricas de caché IA
ai_cache_hit_total = Counter(
    "ai_cache_hit_total",
    "Aciertos de caché IA",
    ["model"],
)

ai_cache_miss_total = Counter(
    "ai_cache_miss_total",
    "Fallos de caché IA",
    ["model"],
)

ai_stream_tokens_total = Counter(
    "ai_stream_tokens_total",
    "Tokens enviados por streaming",
)

ai_stream_duration_seconds = Histogram(
    "ai_stream_duration_seconds",
    "Duración del streaming IA",
)

ai_conversations_active_total = Gauge(
    "ai_conversations_active_total",
    "Conversaciones IA activas",
)
