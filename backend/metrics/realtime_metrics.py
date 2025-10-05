"""Métricas Prometheus para el gateway de tiempo real."""

from prometheus_client import Counter, Gauge

# ✅ Codex fix: métricas para monitorear conexiones WebSocket en tiempo real
ws_connections_active_total = Gauge(
    "ws_connections_active_total",
    "Conexiones WebSocket activas",
)

# ✅ Codex fix: métrica para contar mensajes emitidos a través del gateway
ws_messages_sent_total = Counter(
    "ws_messages_sent_total",
    "Mensajes enviados por WebSocket",
)

# ✅ Codex fix: métrica para rastrear errores durante las sesiones WebSocket
ws_errors_total = Counter(
    "ws_errors_total",
    "Errores en WebSocket",
)

__all__ = [
    "ws_connections_active_total",
    "ws_messages_sent_total",
    "ws_errors_total",
]
