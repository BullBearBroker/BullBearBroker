"""Métricas Prometheus para el servicio de IA."""

from prometheus_client import Counter, Gauge, Histogram

# ✅ Codex fix: métricas IA estructuradas
ai_requests_total = Counter(
    "ai_requests_total",
    "Total de requests IA",
    ["outcome"],
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


ai_provider_latency_seconds = Histogram(
    "ai_provider_latency_seconds",
    "Latencia por proveedor IA",
    ["provider", "route"],
)

ai_provider_failures_total = Counter(
    "ai_provider_failures_total",
    "Fallos por proveedor IA (con código o razón)",
    ["provider", "reason", "route"],
)

ai_provider_requests_total = Counter(
    "ai_provider_requests_total",
    "Llamadas a proveedor IA (por estado)",
    ["provider", "outcome"],
)

ai_provider_fallbacks_total = Counter(
    "ai_provider_fallbacks_total",
    "Fallbacks activados por proveedor (desde -> hacia)",
    ["from_provider", "to_provider", "route"],
)

ai_adaptive_timeouts_total = Counter(
    "ai_adaptive_timeouts_total",
    "Timeouts adaptativos activados",
)


ai_insights_generated_total = Counter(
    "ai_insights_generated_total", "Número total de insights generados por IA"
)
ai_insight_duration_seconds = Histogram(
    "ai_insight_duration_seconds", "Duración de generación de insights de IA"
)
ai_insight_failures_total = Counter(
    "ai_insight_failures_total",
    "Errores ocurridos durante la generación de insights IA",
)


ai_notifications_total = Counter(
    "ai_notifications_total",
    "Notificaciones emitidas por IA",
)

alert_notifications_total = Counter(
    "alert_notifications_total",
    "Alertas enviadas al usuario",
)
