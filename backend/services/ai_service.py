import asyncio
import inspect
import hashlib  # ✅ Codex fix: hashing para claves de caché
import json  # ✅ Codex fix: structured logging support
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin  # [Codex] nuevo

import aiohttp

from backend.core.metrics import AI_PROVIDER_FAILOVER_TOTAL
from backend.metrics.ai_metrics import (
    ai_cache_hit_total,  # ✅ Codex fix: métrica caché hit
)
from backend.metrics.ai_metrics import (
    ai_cache_miss_total,  # ✅ Codex fix: métrica caché miss
)
from backend.metrics.ai_metrics import (  # ✅ Codex fix: IA Prometheus metrics
    ai_conversations_active_total,
    ai_failures_total,
    ai_fallbacks_total,
    ai_latency_seconds,
    ai_provider_failures_total,
    ai_provider_fallbacks_total,
    ai_provider_latency_seconds,
    ai_provider_requests_total,
    ai_requests_total,
    ai_stream_duration_seconds,
    ai_stream_tokens_total,
)
from backend.utils.config import Config

import backend.services.context_service as context_service
import backend.services.sentiment_service as sentiment_service
from .cache_service import cache  # ✅ Codex fix: servicio de caché IA
from .mistral_service import mistral_service
from .ai_route_context import get_current_route, reset_route, set_route

try:  # pragma: no cover - optional imports depending on entrypoint
    from backend.services.market_service import market_service
except ImportError:  # pragma: no cover
    market_service = None  # type: ignore

try:  # pragma: no cover - optional imports depending on entrypoint
    from backend.services.news_service import news_service
except ImportError:  # pragma: no cover
    from services.news_service import news_service  # type: ignore

try:  # pragma: no cover
    from backend.services.forex_service import forex_service
except ImportError:  # pragma: no cover
    from services.forex_service import forex_service  # type: ignore


logger = logging.getLogger(__name__)


# ✅ Codex fix: módulo de caché IA
def get_cached_response(model: str, prompt: str | None):
    if not prompt:
        return None
    cache_key = f"ai:{model}:{hashlib.sha256(prompt.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is None:
        ai_cache_miss_total.labels(model=model).inc()
        return None
    if isinstance(cached, (bytes, bytearray)):
        cached = cached.decode()
    if isinstance(cached, str):
        try:
            cached = json.loads(cached)
        except json.JSONDecodeError:
            cached = {"text": cached}
    if not isinstance(cached, dict):
        ai_cache_miss_total.labels(model=model).inc()
        return None
    ai_cache_hit_total.labels(model=model).inc()
    logger.info(
        json.dumps(
            {
                "ai_event": "cache_hit",
                "model": model,
            }
        )
    )
    return cached


# ✅ Codex fix: almacenamiento de respuestas IA en caché
def store_response_in_cache(
    model: str, prompt: str | None, response: dict | None
) -> None:
    if not prompt or not response:
        return
    ttl = 600 if len(prompt) > 500 else 300
    cache_key = f"ai:{model}:{hashlib.sha256(prompt.encode()).hexdigest()}"
    payload = json.dumps(response)
    cache.set(cache_key, payload, ex=ttl)


def timestamp() -> float:  # ✅ Codex fix: helper for structured logs
    return time.time()


PROVIDER_TIMEOUTS: dict[str, float] = {  # ✅ Codex fix: adaptive timeouts por proveedor
    "mistral": 6.0,
    "huggingface": 8.0,
    "ollama": 5.0,
    "local": 2.0,
}


@dataclass
class CircuitBreakerState:  # ✅ Codex fix: estado del circuit breaker
    state: str = "closed"
    failure_count: int = 0
    last_failure_time: float = 0.0
    next_retry_time: float = 0.0
    last_error: str | None = None


@dataclass
class AIResponsePayload:
    text: str
    provider: str | None
    used_data: bool = False
    sources: list[str] = None

    def __post_init__(self) -> None:
        if self.sources is None:
            self.sources = []


class AIService:
    MARKET_KEYWORDS = {
        "precio",
        "price",
        "valor",
        "cotización",
        "acciones",
        "acción",
        "stock",
        "mercado",
        "eurusd",
        "usd",
        "btc",
        "eth",
        "forex",
    }
    INDICATOR_KEYWORDS = {"rsi", "macd", "vwap", "atr", "indicador", "bollinger"}
    NEWS_KEYWORDS = {"news", "noticia", "noticias", "headline", "titular"}
    ALERT_KEYWORDS = {"alerta", "alertas"}

    def __init__(self):
        self.market_service = market_service
        self.use_real_ai = True  # Mantener compatibilidad con otros servicios
        self._api_base_url = Config.API_BASE_URL.rstrip("/")
        # [Codex] nuevo - base para indicadores
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._circuit_breaker_threshold = 3  # ✅ Codex fix: umbral de fallos
        self._circuit_breaker_cooldown = 60.0
        self._max_retries = 3  # ✅ Codex fix: configurable para pruebas
        self._last_provider_attempted: str | None = None
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._cooldown_durations = {"sync": 5.0, "stream": 10.0, "context": 15.0}

    def set_market_service(self, market_service):
        self.market_service = market_service

    def _get_circuit(self, provider: str) -> CircuitBreakerState:
        return self._circuit_breakers.setdefault(provider, CircuitBreakerState())

    def _reset_circuit(self, provider: str) -> None:
        circuit = self._get_circuit(provider)
        circuit.state = "closed"
        circuit.failure_count = 0
        circuit.next_retry_time = 0.0
        circuit.last_error = None

    def _register_failure(self, provider: str, error: Exception) -> CircuitBreakerState:
        circuit = self._get_circuit(provider)
        circuit.failure_count += 1
        circuit.last_failure_time = timestamp()
        circuit.last_error = error.__class__.__name__
        if circuit.failure_count >= self._circuit_breaker_threshold:
            circuit.state = "open"
            circuit.next_retry_time = (
                circuit.last_failure_time + self._circuit_breaker_cooldown
            )
        return circuit

    def _ready_for_attempt(self, provider: str) -> bool:
        circuit = self._get_circuit(provider)
        now = timestamp()
        if circuit.state == "open" and now >= circuit.next_retry_time:
            circuit.state = "half_open"
            return True
        if circuit.state == "open":
            return False
        return True

    def _log_provider_call(
        self,
        provider_name: str,
        success: bool,
        duration_ms: float,
        fallback_used: bool,
    ) -> None:
        payload = {
            "ai_event": "provider_call",
            "provider": provider_name,
            "success": success,
            "duration_ms": round(duration_ms, 3),
            "fallback_used": fallback_used,
            "timestamp": timestamp(),
        }
        logger.info(json.dumps(payload))  # ✅ Codex fix: logs JSON estructurados

    def _get_provider_label(self, provider_name: str) -> str:
        mapping = {
            "mistral": "Mistral",
            "huggingface": "HuggingFace",
            "ollama": "Local",
            "local": "Local",
        }
        return mapping.get(provider_name.lower(), provider_name)

    def _record_provider_fallback(
        self, from_provider: str, to_provider: str, route: str
    ) -> None:
        from_label = self._get_provider_label(from_provider)
        to_label = (
            to_provider
            if to_provider in {"cooldown_skip"}
            else self._get_provider_label(to_provider)
        )
        ai_provider_fallbacks_total.labels(from_label, to_label, route).inc()
        logger.info(
            json.dumps(
                {
                    "ai_event": "provider_fallback",
                    "from": from_label,
                    "to": to_label,
                    "route": route,
                }
            )
        )

    @staticmethod
    def _map_http_reason(status_code: int | None) -> str:
        if status_code == 408:
            return "timeout"
        if status_code == 429:
            return "rate_limited"
        if status_code is not None and 500 <= status_code < 600:
            return "server_error"
        if status_code is not None and 400 <= status_code < 500:
            return "bad_response"
        return "unknown"

    async def process_message(
        self, message: str, context: dict[str, Any] = None
    ) -> AIResponsePayload:
        """Procesar mensaje del usuario y generar respuesta enriquecida."""

        context = dict(context or {})

        async def _local_response(reason: str, fallback_used: bool) -> AIResponsePayload:
            start_local = time.perf_counter()
            ai_text = await self.generate_response(message)
            duration_ms = (time.perf_counter() - start_local) * 1000
            provider = "local"
            ai_latency_seconds.labels(provider=provider).observe(duration_ms / 1000)
            ai_requests_total.labels(provider=provider, status="success").inc()
            self._log_provider_call(provider, True, duration_ms, fallback_used)
            logger.info(
                json.dumps(
                    {
                        "ai_event": "process_message_local_fallback",
                        "reason": reason,
                        "elapsed_ms": round(duration_ms, 3),
                    }
                )
            )
            return AIResponsePayload(
                text=ai_text,
                provider=provider,
                used_data=False,
                sources=[],
            )

        normalized_message = (message or "").strip()
        if not normalized_message:
            return await _local_response("empty_message", False)

        decision = self._analyze_message(message)
        symbols = decision["symbols"]
        interval = decision["interval"] or "1h"

        used_data = False
        sources: list[str] = []
        enrichment: dict[str, list[str]] = {}

        # Market data (precios)
        market_context: dict[str, Any] = {}
        if decision["use_market_data"]:
            try:
                market_context = await self.get_market_context(message)
                if market_context:
                    context.update(market_context)
                    price_lines = self._summarize_market_context(market_context)
                    if price_lines:
                        enrichment.setdefault("prices", []).extend(price_lines)
                        used_data = True
                        if "prices" not in sources:
                            sources.append("prices")
            except Exception:
                logger.exception("Error collecting market context")

        # Indicadores técnicos
        if decision["need_indicators"]:
            try:
                indicator_context = await self._collect_indicator_snapshots(message)
                if indicator_context:
                    context["indicator_data"] = indicator_context
                    indicator_lines = self._summarize_indicators(indicator_context)
                    if indicator_lines:
                        enrichment.setdefault("indicators", []).extend(indicator_lines)
                        used_data = True
                        if "indicators" not in sources:
                            sources.append("indicators")
            except Exception:
                logger.exception("Error collecting indicator snapshots")

        # Noticias
        if decision["need_news"]:
            try:
                news_items = await self._collect_news_highlights(symbols)
                if news_items:
                    context["news"] = news_items
                    news_lines = self._summarize_news(news_items)
                    if news_lines:
                        enrichment.setdefault("news", []).extend(news_lines)
                        used_data = True
                        if "news" not in sources:
                            sources.append("news")
            except Exception:
                logger.exception("Error collecting news highlights")

        # Alertas sugeridas
        if decision["need_alerts"] and symbols:
            try:
                alert_suggestions = await self._collect_alert_suggestions(
                    symbols, interval
                )
                if alert_suggestions:
                    context["alert_suggestions"] = alert_suggestions
                    alert_lines = self._summarize_alerts(alert_suggestions)
                    if alert_lines:
                        enrichment.setdefault("alerts", []).extend(alert_lines)
                        used_data = True
                        if "alerts" not in sources:
                            sources.append("alerts")
            except Exception:
                logger.exception("Error collecting alert suggestions")

        # Cotizaciones forex específicas
        if decision["forex_pairs"]:
            try:
                forex_lines = await self._collect_forex_quotes(decision["forex_pairs"])
                if forex_lines:
                    enrichment.setdefault("prices", []).extend(forex_lines)
                    used_data = True
                    if "prices" not in sources:
                        sources.append("prices")
            except Exception:
                logger.exception("Error collecting forex quotes")

        enrichment_text = self._build_enrichment_summary(enrichment)
        if enrichment_text:
            context["enrichment_summary"] = enrichment_text

        prompt_for_cache: str | None = None  # ✅ Codex fix: prompt base para caché
        try:
            prompt_for_cache = self._build_prompt(message, context)
        except ValueError as exc:
            return await _local_response(str(exc) or "prompt_invalid", False)
        except Exception:
            prompt_for_cache = None
        providers: list[tuple[str, Callable[[], Awaitable[str]]]] = [
            ("mistral", lambda: self.process_with_mistral(message, context))
        ]

        if Config.HUGGINGFACE_API_KEY:
            providers.append(
                ("huggingface", lambda: self._call_huggingface(message, context))
            )
        else:
            logger.info("HuggingFace token not configured. Skipping provider.")

        providers.append(("ollama", lambda: self._call_ollama(message, context)))

        ai_text: str | None = None  # ✅ Codex fix: inicialización para fallback caché
        provider: str | None = None

        try:
            call_with_backoff = self._call_with_backoff
            try:
                parameters = inspect.signature(call_with_backoff).parameters
            except (TypeError, ValueError):
                parameters = None

            if parameters is not None and len(parameters) == 1:
                ai_text, provider = await call_with_backoff(providers)  # type: ignore[arg-type]
            else:
                ai_text, provider = await call_with_backoff(
                    providers, prompt_for_cache
                )
            logger.info("AI response generated using provider %s", provider)
        except Exception as exc:
            last_provider = self._last_provider_attempted or "unknown"
            logger.error(
                json.dumps(
                    {
                        "ai_event": "provider_failure",
                        "last_provider": last_provider,
                        "error": str(exc),
                    }
                )
            )  # ✅ Codex fix: mensaje unificado
            cache_fallback_text: str | None = None
            cache_fallback_provider: str | None = None
            if prompt_for_cache:
                for provider_name, _ in providers:
                    cached_payload = get_cached_response(
                        provider_name, prompt_for_cache
                    )
                    if cached_payload and cached_payload.get("text"):
                        cache_fallback_text = cached_payload["text"]
                        cache_fallback_provider = cached_payload.get(
                            "provider", provider_name
                        )
                        ai_fallbacks_total.labels(
                            from_provider=last_provider,
                            to_provider="cache",
                        ).inc()
                        logger.info(
                            json.dumps(
                                {
                                    "ai_event": "cache_fallback",
                                    "from_provider": last_provider,
                                    "model": cache_fallback_provider,
                                }
                            )
                        )
                        provider = cache_fallback_provider
                        ai_text = cache_fallback_text
                        ai_requests_total.labels(
                            provider=provider or "cache",
                            status="success",
                        ).inc()
                        self._log_provider_call(
                            cache_fallback_provider or "cache", True, 0.0, True
                        )
                        break
            if not ai_text:
                AI_PROVIDER_FAILOVER_TOTAL.labels(provider="local").inc()
                ai_fallbacks_total.labels(
                    from_provider=last_provider,
                    to_provider="local",
                ).inc()
                response_payload = await _local_response("provider_failure", True)
                ai_text = response_payload.text
                provider = response_payload.provider
                logger.info("AI response generated using local fallback")

        final_parts: list[str] = []
        if enrichment_text:
            final_parts.append(enrichment_text)
        if ai_text:
            final_parts.append(ai_text)

        final_message = (
            "\n\n".join(part for part in final_parts if part.strip()) or ai_text
        )

        if (
            prompt_for_cache and provider and ai_text
        ):  # ✅ Codex fix: persistencia en caché
            store_response_in_cache(
                provider,
                prompt_for_cache,
                {"text": ai_text, "provider": provider},
            )

        return AIResponsePayload(
            text=final_message,
            provider=provider,
            used_data=used_data,
            sources=sources,
        )

    async def process_with_mistral(
        self, message: str, context: dict[str, Any] = None
    ) -> str:
        """Procesar mensaje con Mistral AI"""
        try:
            # Generar respuesta con Mistral AI
            response = await mistral_service.generate_financial_response(
                message, context
            )

            # Verificar que la respuesta sea válida
            if response and len(response.strip()) > 10:
                if "dificultades" in response.lower():
                    error = ValueError("Respuesta de error de Mistral AI")
                    reason = mistral_service.pop_last_reason() or "bad_response"
                    setattr(error, "ai_reason", reason)
                    raise error
                mistral_service.pop_last_reason()
                return response
            else:
                error = ValueError("Respuesta vacía de Mistral AI")
                reason = mistral_service.pop_last_reason() or "bad_response"
                setattr(error, "ai_reason", reason)
                raise error

        except Exception as e:
            logger.warning("Mistral provider failed: %s", e)
            raise

    async def _call_with_backoff(
        self,
        providers: list[tuple[str, Callable[[], Awaitable[str]]]],
        prompt_for_cache: str | None = None,
    ) -> tuple[str, str]:  # ✅ Codex fix: soporte de caché en backoff
        last_error: Exception | None = None
        total_providers = len(providers)
        route = get_current_route()
        for index, (provider_name, provider) in enumerate(providers):
            self._last_provider_attempted = provider_name
            backoff = 1
            provider_label = self._get_provider_label(provider_name)
            if prompt_for_cache:
                cached_payload = get_cached_response(provider_name, prompt_for_cache)
                if cached_payload and cached_payload.get("text"):
                    cached_text = cached_payload["text"]
                    cached_provider = cached_payload.get("provider", provider_name)
                    ai_requests_total.labels(
                        provider=cached_provider, status="success"
                    ).inc()
                    self._reset_circuit(provider_name)
                    self._log_provider_call(provider_name, True, 0.0, index > 0)
                    return cached_text, cached_provider
            if not self._ready_for_attempt(provider_name):
                fallback_used = index < total_providers - 1
                self._log_provider_call(provider_name, False, 0.0, fallback_used)
                if fallback_used:
                    AI_PROVIDER_FAILOVER_TOTAL.labels(provider=provider_name).inc()
                    next_provider = providers[index + 1][0]
                    ai_fallbacks_total.labels(
                        from_provider=provider_name,
                        to_provider=next_provider,
                    ).inc()
                    self._record_provider_fallback(provider_name, next_provider, route)
                continue

            cooldown_key = (provider_label, route)
            now = time.monotonic()
            cooldown_until = self._cooldowns.get(cooldown_key, 0.0)
            if now < cooldown_until:
                fallback_used = index < total_providers - 1
                self._log_provider_call(provider_name, False, 0.0, fallback_used)
                if fallback_used:
                    AI_PROVIDER_FAILOVER_TOTAL.labels(provider=provider_name).inc()
                    next_provider = providers[index + 1][0]
                    ai_fallbacks_total.labels(
                        from_provider=provider_name,
                        to_provider=next_provider,
                    ).inc()
                    ai_provider_fallbacks_total.labels(
                        provider_label, "cooldown_skip", route
                    ).inc()
                    logger.info(
                        json.dumps(
                            {
                                "ai_event": "cooldown_skip",
                                "provider": provider_label,
                                "route": route,
                                "retry_at": round(cooldown_until, 3),
                            }
                        )
                    )
                    self._record_provider_fallback(
                        provider_name, next_provider, route
                    )
                continue

            for attempt in range(1, self._max_retries + 1):
                start = time.perf_counter()
                try:
                    timeout_seconds = PROVIDER_TIMEOUTS.get(provider_name, 10.0)
                    response = await asyncio.wait_for(
                        provider(), timeout=timeout_seconds
                    )
                    if response and response.strip():
                        duration_ms = (time.perf_counter() - start) * 1000
                        ai_latency_seconds.labels(provider=provider_name).observe(
                            duration_ms / 1000
                        )
                        ai_requests_total.labels(
                            provider=provider_name, status="success"
                        ).inc()
                        self._reset_circuit(provider_name)
                        self._log_provider_call(
                            provider_name,
                            True,
                            duration_ms,
                            index > 0,
                        )
                        return response, provider_name
                    raise ValueError(f"Respuesta vacía de {provider_name}")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    last_error = exc
                    duration_ms = (time.perf_counter() - start) * 1000
                    ai_latency_seconds.labels(provider=provider_name).observe(
                        duration_ms / 1000
                    )
                    ai_requests_total.labels(
                        provider=provider_name, status="failure"
                    ).inc()
                    ai_failures_total.labels(
                        provider=provider_name,
                        error_type=exc.__class__.__name__,
                    ).inc()
                    circuit = self._register_failure(provider_name, exc)
                    reason = getattr(exc, "ai_reason", None)
                    if reason == "rate_limited":
                        cooldown_seconds = self._cooldown_durations.get(route, 5.0)
                        self._cooldowns[cooldown_key] = time.monotonic() + cooldown_seconds
                    logger.warning(
                        "Provider %s attempt %d failed: %s",
                        provider_name,
                        attempt,
                        exc,
                    )
                    fallback_flag = (
                        attempt >= self._max_retries and index < total_providers - 1
                    )
                    self._log_provider_call(
                        provider_name,
                        False,
                        duration_ms,
                        fallback_flag,
                    )
                    if circuit.state == "open":
                        logger.error(
                            "Provider %s circuit breaker opened after %d failures",
                            provider_name,
                            circuit.failure_count,
                        )
                        break
                    if attempt < self._max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.error(
                            "Provider %s exhausted retries after %d attempts",
                            provider_name,
                            attempt,
                        )
                        break

            if index < total_providers - 1:
                AI_PROVIDER_FAILOVER_TOTAL.labels(provider=provider_name).inc()
                next_provider = providers[index + 1][0]
                ai_fallbacks_total.labels(
                    from_provider=provider_name,
                    to_provider=next_provider,
                ).inc()
                self._record_provider_fallback(provider_name, next_provider, route)

        if last_error:
            raise last_error
        raise RuntimeError("No providers available")

    async def _call_huggingface(self, message: str, context: dict[str, Any]) -> str:
        if not Config.HUGGINGFACE_API_KEY:
            raise RuntimeError("HuggingFace token not configured")

        model = self._select_model_for_profile((context or {}).get("risk_profile"))
        base_url = Config.HUGGINGFACE_API_URL.rstrip("/")
        url = f"{base_url}/{model}"
        prompt = self._build_prompt(message, context)

        headers = {
            "Authorization": f"Bearer {Config.HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 400,
                "temperature": 0.4,
            },
        }

        provider_label = "HuggingFace"
        route = get_current_route()
        ai_provider_requests_total.labels(provider_label, route).inc()
        start = time.perf_counter()
        data: Any | None = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=headers, json=payload, timeout=30
                ) as response:
                    status_code = response.status
                    if status_code != 200:
                        error_body = await response.text()
                        reason = self._map_http_reason(status_code)
                        duration = time.perf_counter() - start
                        ai_provider_latency_seconds.labels(
                            provider_label, route
                        ).observe(duration)
                        ai_provider_failures_total.labels(
                            provider_label, reason, route
                        ).inc()
                        logger.warning(
                            json.dumps(
                                {
                                    "ai_event": "provider_call",
                                    "provider": provider_label,
                                    "route": route,
                                    "latency_ms": round(duration * 1000, 2),
                                    "status": "error",
                                    "reason": reason,
                                    "http_status": status_code,
                                }
                            )
                        )
                        error = RuntimeError(
                            f"HuggingFace API error {status_code}: {error_body}"
                        )
                        setattr(error, "ai_reason", reason)
                        setattr(error, "ai_status_code", status_code)
                        raise error

                    try:
                        data = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as exc:
                        duration = time.perf_counter() - start
                        reason = "bad_response"
                        ai_provider_latency_seconds.labels(
                            provider_label, route
                        ).observe(duration)
                        ai_provider_failures_total.labels(
                            provider_label, reason, route
                        ).inc()
                        logger.warning(
                            json.dumps(
                                {
                                    "ai_event": "provider_call",
                                    "provider": provider_label,
                                    "route": route,
                                    "latency_ms": round(duration * 1000, 2),
                                    "status": "error",
                                    "reason": reason,
                                    "http_status": status_code,
                                }
                            )
                        )
                        value_error = ValueError("Invalid JSON from HuggingFace")
                        setattr(value_error, "ai_reason", reason)
                        setattr(value_error, "ai_status_code", status_code)
                        raise value_error from exc

        except asyncio.TimeoutError as exc:
            duration = time.perf_counter() - start
            reason = "timeout"
            ai_provider_latency_seconds.labels(provider_label, route).observe(duration)
            ai_provider_failures_total.labels(provider_label, reason, route).inc()
            logger.warning(
                json.dumps(
                    {
                        "ai_event": "provider_call",
                        "provider": provider_label,
                        "route": route,
                        "latency_ms": round(duration * 1000, 2),
                        "status": "error",
                        "reason": reason,
                        "http_status": 408,
                    }
                )
            )
            timeout_error = TimeoutError("HuggingFace request timed out")
            setattr(timeout_error, "ai_reason", reason)
            setattr(timeout_error, "ai_status_code", 408)
            raise timeout_error from exc
        except aiohttp.ClientError as exc:
            duration = time.perf_counter() - start
            reason = "unknown"
            ai_provider_latency_seconds.labels(provider_label, route).observe(duration)
            ai_provider_failures_total.labels(provider_label, reason, route).inc()
            logger.warning(
                json.dumps(
                    {
                        "ai_event": "provider_call",
                        "provider": provider_label,
                        "route": route,
                        "latency_ms": round(duration * 1000, 2),
                        "status": "error",
                        "reason": reason,
                        "http_status": None,
                    }
                )
            )
            runtime_error = RuntimeError(f"Error comunicándose con HuggingFace: {exc}")
            setattr(runtime_error, "ai_reason", reason)
            setattr(runtime_error, "ai_status_code", None)
            raise runtime_error from exc

        generated_text: str | None = None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(
                    item.get("generated_text"), str
                ):
                    generated_text = item["generated_text"]
                    break
                if isinstance(item, str):
                    generated_text = item
                    break
        elif isinstance(data, dict):
            text_candidate = data.get("generated_text") or data.get("data")
            if isinstance(text_candidate, str):
                generated_text = text_candidate

        if generated_text and generated_text.strip():
            duration = time.perf_counter() - start
            ai_provider_latency_seconds.labels(provider_label, route).observe(duration)
            logger.info(
                json.dumps(
                    {
                        "ai_event": "provider_call",
                        "provider": provider_label,
                        "route": route,
                        "latency_ms": round(duration * 1000, 2),
                        "status": "ok",
                        "http_status": 200,
                    }
                )
            )
            return generated_text.strip()

        reason = "bad_response"
        ai_provider_failures_total.labels(provider_label, reason, route).inc()
        duration = time.perf_counter() - start
        ai_provider_latency_seconds.labels(provider_label, route).observe(duration)
        logger.warning(
            json.dumps(
                {
                    "ai_event": "provider_call",
                    "provider": provider_label,
                    "route": route,
                    "latency_ms": round(duration * 1000, 2),
                    "status": "error",
                    "reason": reason,
                    "http_status": 200,
                }
            )
        )
        error = ValueError("Respuesta vacía de HuggingFace")
        setattr(error, "ai_reason", reason)
        setattr(error, "ai_status_code", 200)
        raise error

    async def _call_ollama(self, message: str, context: dict[str, Any]) -> str:
        host = (
            Config.OLLAMA_HOST.rstrip("/")
            if Config.OLLAMA_HOST
            else "http://localhost:11434"
        )
        model = Config.OLLAMA_MODEL or "llama3"
        prompt = self._build_prompt(message, context)

        async with aiohttp.ClientSession() as session:
            # Verificar que el servidor de Ollama esté disponible y que el modelo exista
            async with session.get(f"{host}/api/tags", timeout=5) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(f"Ollama disponibilidad fallida: {body}")

                tags = await response.json()
                models = tags.get("models") if isinstance(tags, dict) else None
                if isinstance(models, list) and not any(
                    isinstance(item, dict) and item.get("name") == model
                    for item in models
                ):
                    raise RuntimeError(f"Modelo {model} no disponible en Ollama")

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }

            async with session.post(
                f"{host}/api/generate", json=payload, timeout=30
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise RuntimeError(f"Error generando respuesta de Ollama: {body}")

                data = await response.json()

        generated_text = data.get("response") if isinstance(data, dict) else None
        if isinstance(generated_text, str) and generated_text.strip():
            return generated_text.strip()

        raise ValueError("Respuesta vacía de Ollama")

    def _build_prompt(self, message: str, context: dict[str, Any]) -> str:
        if not (message or "").strip():
            raise ValueError("El mensaje no puede estar vacío")
        prompt_lines = [
            "Eres BullBearBroker, un analista financiero profesional.",
            f"Consulta del usuario: {message}",
        ]

        if context:
            market_data = context.get("market_data")
            if market_data:
                prompt_lines.append(f"Datos de mercado: {market_data}")

            indicator_data = context.get("indicator_data")  # [Codex] nuevo
            if indicator_data:
                prompt_lines.append(
                    f"Indicadores técnicos: {indicator_data}"
                )  # [Codex] nuevo

            other_context = {
                key: value
                for key, value in context.items()
                if key not in {"market_data", "indicator_data"}
                # [Codex] cambiado - excluir indicadores ya agregados
            }
            if other_context:
                prompt_lines.append(f"Contexto adicional: {other_context}")

        prompt_lines.append(
            "Responde en español con recomendaciones concretas y breves."
        )
        return "\n".join(prompt_lines)

    def _select_model_for_profile(self, profile: str | None) -> str:
        base_model = Config.HUGGINGFACE_MODEL
        if not profile:
            return base_model

        normalized = str(profile).strip().lower()
        mapping = getattr(Config, "HUGGINGFACE_RISK_MODELS", None)
        if isinstance(mapping, dict):
            lowered = {
                str(key).strip().lower(): str(value)
                for key, value in mapping.items()
                if value
            }
            if normalized in lowered:
                return lowered[normalized]

        defaults = {
            "investor": base_model,
            "trader": base_model,
            "analyst": base_model,
            "fund": base_model,
        }
        return defaults.get(normalized, base_model)

    def _analyze_message(self, message: str) -> dict[str, Any]:
        lower = message.lower()
        symbols = self.extract_symbols(message)
        interval = self._extract_interval(message)

        need_indicators = any(keyword in lower for keyword in self.INDICATOR_KEYWORDS)
        need_news = any(keyword in lower for keyword in self.NEWS_KEYWORDS)
        need_alerts = any(keyword in lower for keyword in self.ALERT_KEYWORDS)
        price_terms = any(keyword in lower for keyword in self.MARKET_KEYWORDS)

        forex_pairs = [
            symbol for symbol in symbols if self._looks_like_forex_pair(symbol)
        ]

        use_market_data = bool(
            symbols or price_terms or need_indicators or need_news or need_alerts
        )

        return {
            "symbols": symbols,
            "interval": interval,
            "need_indicators": need_indicators,
            "need_news": need_news,
            "need_alerts": need_alerts,
            "forex_pairs": forex_pairs,
            "use_market_data": use_market_data,
        }

    async def get_market_context(self, message: str) -> dict[str, Any]:
        """Obtener contexto de mercado relevante"""
        if not self.market_service:
            return {}

        context = {}
        symbols = self.extract_symbols(message)

        if symbols:
            market_data = {}
            for symbol in symbols:
                try:
                    asset_type = await self.market_service.detect_asset_type(symbol)
                    price_data = await self.market_service.get_price(symbol, asset_type)
                    if price_data:
                        market_data[symbol] = {
                            "price": price_data.get("price", "N/A"),
                            "change": price_data.get("change", "N/A"),
                            "raw_price": price_data.get("raw_price", 0),
                            "raw_change": price_data.get("raw_change", 0),
                        }
                except Exception as e:
                    print(f"Error getting price for {symbol}: {e}")
                    continue

            if market_data:
                context["market_data"] = market_data
                context["symbols"] = list(market_data.keys())

        return context

    async def _collect_indicator_snapshots(self, message: str) -> dict[str, Any]:
        """Busca símbolos + intervalos y consulta /api/markets/indicators con datos reales."""
        # [Codex] nuevo
        interval = self._extract_interval(message)
        if not interval:
            return {}

        symbols = self.extract_symbols(message)
        if not symbols:
            return {}

        tasks = []
        prepared: list[tuple[str, str]] = []

        session_timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=session_timeout) as session:
            for symbol in symbols[:2]:
                # [Codex] nuevo - limitamos a dos símbolos para evitar latencia
                asset_type = await self._resolve_asset_type(symbol)
                if asset_type is None:
                    continue
                normalized = self._normalize_symbol_for_indicators(asset_type, symbol)
                url = urljoin(self._api_base_url + "/", "api/markets/indicators")
                params = {
                    "type": asset_type,
                    "symbol": normalized,
                    "interval": interval,
                    "limit": "300",
                    "include_atr": "true",
                    "atr_period": "14",
                    "include_stoch_rsi": "true",
                    "stoch_rsi_period": "14",
                    "stoch_rsi_k": "3",
                    "stoch_rsi_d": "3",
                    "include_ichimoku": "true",
                    "ichimoku_conversion": "9",
                    "ichimoku_base": "26",
                    "ichimoku_span_b": "52",
                    "include_vwap": "true",
                }
                tasks.append(self._fetch_indicator_snapshot(session, url, params))
                prepared.append((symbol.upper(), asset_type))

            if not tasks:
                return {}

            results = await asyncio.gather(*tasks, return_exceptions=True)

        indicator_map: dict[str, Any] = {}
        for (symbol_key, asset_type), result in zip(prepared, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "Indicator snapshot failed for %s: %s", symbol_key, result
                )
                continue
            if not isinstance(result, dict):
                continue
            indicator_map[symbol_key] = {
                "asset_type": asset_type,
                "interval": result.get("interval"),
                "source": result.get("source"),
                "indicators": result.get("indicators", {}),
            }
        return indicator_map

    async def _fetch_indicator_snapshot(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        """Realiza la llamada HTTP para recuperar indicadores técnicos."""
        # [Codex] nuevo
        async with session.get(url, params=params) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(
                    f"Indicadores {params.get('symbol')} -> {response.status}: {body[:200]}"
                )
            return await response.json()

    async def _collect_news_highlights(
        self, symbols: list[str], limit: int = 3
    ) -> list[dict[str, Any]]:
        if news_service is None:
            return []
        try:
            articles = await news_service.get_latest_news(limit=8)
        except Exception as exc:
            logger.warning("NewsService error: %s", exc)
            return []

        if not articles:
            return []

        symbols_lower = [sym.lower() for sym in symbols if sym]
        selected: list[dict[str, Any]] = []
        for article in articles:
            title = article.get("title") or ""
            summary = article.get("summary") or ""
            text_blob = f"{title} {summary}".lower()
            if symbols_lower:
                if any(sym in text_blob for sym in symbols_lower):
                    selected.append(article)
            else:
                selected.append(article)
            if len(selected) >= limit:
                break

        if not selected and symbols_lower:
            selected = articles[:limit]

        highlights: list[dict[str, Any]] = []
        for item in selected[:limit]:
            highlights.append(
                {
                    "title": item.get("title") or "Sin título",
                    "source": item.get("source") or "News",
                    "url": item.get("url"),
                    "published_at": item.get("published_at"),
                    "summary": item.get("summary"),
                }
            )
        return highlights

    async def _collect_alert_suggestions(
        self, symbols: list[str], interval: str
    ) -> list[dict[str, str]]:
        try:
            from backend.services.alert_service import (
                alert_service as shared_alert_service,
            )
        except ImportError:  # pragma: no cover - evitar fallos en modo standalone
            return []

        suggestions: list[dict[str, str]] = []
        for symbol in symbols[:2]:
            try:
                result = await shared_alert_service.suggest_alert_condition(
                    symbol, interval
                )
                if result:
                    payload = {"symbol": symbol, **result}
                    suggestions.append(payload)
            except Exception as exc:
                logger.warning("Alert suggestion failed for %s: %s", symbol, exc)
        return suggestions

    async def _collect_forex_quotes(self, pairs: list[str]) -> list[str]:
        if forex_service is None:
            return []
        summaries: list[str] = []
        for pair in pairs[:3]:
            try:
                quote = await forex_service.get_quote(pair)
            except Exception as exc:
                logger.warning("Forex quote failed for %s: %s", pair, exc)
                continue
            if not quote:
                continue
            price = quote.get("price")
            change = quote.get("change")
            source = quote.get("source") or "Forex"
            change_str = (
                f"{change:+.4f}" if isinstance(change, int | float) else change or "n/d"
            )
            price_str = (
                f"{price:.4f}" if isinstance(price, int | float) else price or "n/d"
            )
            formatted_pair = self._format_forex_symbol(pair)
            summaries.append(f"{formatted_pair}: {price_str} ({change_str}) — {source}")
        return summaries

    def _summarize_market_context(self, market_context: dict[str, Any]) -> list[str]:
        if not market_context:
            return []
        market_data = market_context.get("market_data") or {}
        lines: list[str] = []
        for symbol, payload in market_data.items():
            raw_price = payload.get("raw_price")
            price = (
                f"{raw_price:,.2f}"
                if isinstance(raw_price, int | float)
                else payload.get("price")
            )
            raw_change = payload.get("raw_change")
            change = (
                f"{raw_change:+.2f}%"
                if isinstance(raw_change, int | float)
                else payload.get("change")
            )
            source = payload.get("source") or "Mercado"
            lines.append(
                f"{symbol}: precio {price or 'n/d'} ({change or 'n/d'}) — {source}"
            )
        return lines

    def _summarize_indicators(self, indicator_map: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for symbol, payload in indicator_map.items():
            indicators = payload.get("indicators", {})
            parts: list[str] = []
            rsi = indicators.get("rsi", {}).get("value")
            if isinstance(rsi, int | float):
                parts.append(f"RSI {rsi:.1f}")
            macd_obj = indicators.get("macd") or {}
            macd_val = macd_obj.get("macd")
            if isinstance(macd_val, int | float):
                parts.append(f"MACD {macd_val:.3f}")
            atr = indicators.get("atr", {}).get("value")
            if isinstance(atr, int | float):
                parts.append(f"ATR {atr:.3f}")
            stoch = indicators.get("stochastic_rsi") or {}
            stoch_k = stoch.get("%K")
            if isinstance(stoch_k, int | float):
                parts.append(f"StochRSI %K {stoch_k:.1f}")
            vwap = indicators.get("vwap", {}).get("value")
            if isinstance(vwap, int | float):
                parts.append(f"VWAP {vwap:.3f}")

            if not parts:
                continue
            interval = payload.get("interval", "n/d")
            lines.append(f"{symbol} ({interval}): {', '.join(parts)}")
        return lines

    def _summarize_news(self, news_items: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for item in news_items:
            title = item.get("title") or "Sin título"
            source = item.get("source") or "News"
            lines.append(f"{title} — {source}")
        return lines

    def _summarize_alerts(self, suggestions: list[dict[str, str]]) -> list[str]:
        lines: list[str] = []
        for item in suggestions:
            symbol = item.get("symbol", "Activo")
            suggestion = item.get("suggestion")
            note = item.get("notes")
            if not suggestion:
                continue
            if note:
                lines.append(f"{symbol}: {suggestion} (nota: {note})")
            else:
                lines.append(f"{symbol}: {suggestion}")
        return lines

    def _build_enrichment_summary(self, enrichment: dict[str, list[str]]) -> str:
        if not enrichment:
            return ""
        sections: list[str] = []
        if enrichment.get("prices"):
            sections.append(
                "📈 Datos de mercado:\n"
                + "\n".join(f"- {line}" for line in enrichment["prices"])
            )
        if enrichment.get("indicators"):
            sections.append(
                "📊 Indicadores técnicos:\n"
                + "\n".join(f"- {line}" for line in enrichment["indicators"])
            )
        if enrichment.get("news"):
            sections.append(
                "📰 Noticias relevantes:\n"
                + "\n".join(f"- {line}" for line in enrichment["news"])
            )
        if enrichment.get("alerts"):
            sections.append(
                "🚨 Ideas de alertas:\n"
                + "\n".join(f"- {line}" for line in enrichment["alerts"])
            )
        return "\n\n".join(sections).strip()

    def _looks_like_forex_pair(self, symbol: str) -> bool:
        if "/" in symbol:
            parts = symbol.split("/")
            return len(parts) == 2 and all(len(p) == 3 for p in parts)
        return bool(len(symbol) == 6 and symbol.isalpha())

    def _format_forex_symbol(self, symbol: str) -> str:
        if "/" in symbol:
            return symbol.upper()
        if len(symbol) == 6:
            return f"{symbol[:3]}/{symbol[3:]}".upper()
        return symbol.upper()

    async def _resolve_asset_type(self, symbol: str) -> str | None:
        """Determina tipo de activo combinando heurísticas con MarketService."""
        # [Codex] nuevo
        symbol_up = symbol.upper()
        if "/" in symbol_up or (
            len(symbol_up) == 6 and symbol_up.isalpha() and symbol_up.isupper()
        ):
            return "forex"
        if self.market_service:
            try:
                detected = await self.market_service.detect_asset_type(symbol_up)
                if detected in {"crypto", "stock"}:
                    return detected
            except Exception:
                logger.debug(
                    "No se pudo detectar tipo via MarketService para %s", symbol_up
                )
        return "stock"

    def _normalize_symbol_for_indicators(self, asset_type: str, symbol: str) -> str:
        """Normaliza símbolo según la API de indicadores."""
        # [Codex] nuevo
        symbol_up = symbol.upper()
        if asset_type == "crypto" and not symbol_up.endswith("USDT"):
            return f"{symbol_up}USDT"
        if asset_type == "forex":
            return symbol_up.replace("/", "")
        return symbol_up

    def _extract_interval(self, message: str) -> str | None:
        """Busca intervalos soportados (1h, 4h, 1d) dentro del mensaje."""
        # [Codex] nuevo
        match = re.search(r"\b(1h|4h|1d)\b", message, flags=re.IGNORECASE)
        return match.group(1).lower() if match else None

    def _merge_indicator_response(
        self, ai_response: str, indicator_map: dict[str, Any]
    ) -> str:
        """Combina la respuesta textual del modelo con un resumen de indicadores."""
        # [Codex] nuevo
        if not indicator_map:
            return ai_response

        lines = ["", "📊 Indicadores recientes:"]
        for symbol, payload in indicator_map.items():
            data = payload.get("indicators", {})
            summary_parts: list[str] = []

            rsi_data = data.get("rsi")
            if rsi_data and rsi_data.get("value") is not None:
                summary_parts.append(f"RSI {rsi_data['value']}")

            macd_data = data.get("macd")
            if macd_data and macd_data.get("macd") is not None:
                summary_parts.append(f"MACD {macd_data['macd']}")

            atr_data = data.get("atr")
            if atr_data and atr_data.get("value") is not None:
                summary_parts.append(f"ATR {atr_data['value']}")

            stoch_data = data.get("stochastic_rsi")
            if stoch_data and stoch_data.get("%K") is not None:
                summary_parts.append(f"StochRSI %K {stoch_data['%K']}")

            ichimoku_data = data.get("ichimoku")
            if ichimoku_data and ichimoku_data.get("tenkan_sen") is not None:
                summary_parts.append(
                    f"Ichimoku T/K {ichimoku_data['tenkan_sen']}/{ichimoku_data['kijun_sen']}"
                )

            vwap_data = data.get("vwap")
            if vwap_data and vwap_data.get("value") is not None:
                summary_parts.append(f"VWAP {vwap_data['value']}")

            if not summary_parts:
                continue

            interval = payload.get("interval", "n/d")
            lines.append(f"- {symbol} ({interval}): {', '.join(summary_parts)}")

        if len(lines) == 2:
            return ai_response

        return ai_response + "\n".join(lines)

    def extract_symbols(self, message: str) -> list:
        """Extraer símbolos de activos del mensaje"""
        # Símbolos de cripto comunes
        crypto_symbols = {
            "BTC",
            "ETH",
            "BNB",
            "XRP",
            "ADA",
            "SOL",
            "DOT",
            "AVAX",
            "MATIC",
            "DOGE",
        }

        # Patrones regex para detectar símbolos
        patterns = [
            r"\b([A-Z]{2,5})\b",  # Símbolos de acciones (AAPL, TSLA)
            r"precio de (\w+)",
            r"valor de (\w+)",
            r"cotización de (\w+)",
            r"price of (\w+)",
            r"cuánto vale (\w+)",
        ]

        found_symbols = set()

        # Buscar símbolos conocidos
        words = message.upper().split()
        for word in words:
            cleaned_word = word.strip(".,!?;:()[]{}")
            if cleaned_word in crypto_symbols or (
                len(cleaned_word) in [3, 4, 5] and cleaned_word.isalpha()
            ):
                found_symbols.add(cleaned_word)

        # Buscar con patrones regex
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                symbol = match[0].upper() if isinstance(match, tuple) else match.upper()

                if len(symbol) >= 2 and symbol.isalpha():
                    found_symbols.add(symbol)

        return list(found_symbols)

    async def generate_response(self, message: str) -> str:
        """Generar respuesta local (fallback)"""
        lower_message = message.lower()

        # Detectar consultas de precio
        if self.is_price_query(lower_message):
            return await self.handle_price_query(message)

        # Respuestas predefinidas
        responses = {
            "bitcoin": (
                "📈 Bitcoin está mostrando fortaleza. Soporte clave en $40,000, resistencia en "
                "$45,000. Volumen aumentado 15% en 24h. Recomendación: acumular en dips."
            ),
            "ethereum": (
                "🔷 Ethereum consolidando en $2,500. El upgrade próximamente podría impulsar el "
                "precio. Technicals muestran patrón alcista."
            ),
            "acciones": (
                "💼 Recomiendo diversificar: Tech (AAPL, MSFT), Renewable Energy (ENPH), "
                "Healthcare (JNJ). Allocation sugerida: 60% stocks, 20% crypto, 20% cash."
            ),
            "estrategia": (
                "🎯 Estrategias: Conservadora (40% bonds, 40% blue chips, 20% gold). Agresiva "
                "(50% growth stocks, 30% crypto, 20% emerging markets). Rebalancear "
                "trimestralmente."
            ),
            "mercado": (
                "🌍 Mercados globales: S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo "
                "dollar-cost averaging y diversificación."
            ),
            "forex": (
                "💱 Forex: EUR/USD 1.0850, GBP/USD 1.2450, USD/JPY 150.20. Atención a "
                "reuniones del Fed para cambios en tasas."
            ),
            "noticias": (
                "📰 Sigue las noticias de: Fed meetings, earnings reports, GDP data, y "
                "regulatory announcements. Usa fuentes confiables como Bloomberg, Reuters, y "
                "Financial Times."
            ),
            "portfolio": (
                "📊 Para construir portfolio: 1) Define tu risk tolerance, 2) Diversifica "
                "across asset classes, 3) Considera horizonte temporal, 4) Rebalancea "
                "regularmente."
            ),
            "riesgo": (
                "⚖️ Gestión de riesgo: Nunca inviertas más de lo que puedes perder, "
                "diversifica, usa stop-loss orders, y mantén cash para oportunidades."
            ),
            "inversión": (
                "💡 Principios de inversión: Long-term perspective, dollar-cost averaging, "
                "focus on fundamentals, and avoid emotional decisions."
            ),
        }

        for keyword, response in responses.items():
            if keyword in lower_message:
                return response

        # Respuesta por defecto para consultas generales
        return self.get_default_response(message)

    def is_price_query(self, message: str) -> bool:
        """Detectar si es una consulta de precio"""
        price_keywords = [
            "precio",
            "valor",
            "cuánto vale",
            "price of",
            "cotización",
            "valor de",
            "precio de",
            "how much is",
            "current price",
        ]
        return any(keyword in message for keyword in price_keywords)

    async def handle_price_query(self, message: str) -> str:
        """Manejar consultas de precio"""
        if not self.market_service:
            return "Servicio de mercado no disponible en este momento."

        symbols = self.extract_symbols(message)

        if not symbols:
            return (
                "No pude identificar el símbolo del activo. Por favor especifica, por ejemplo: "
                "'precio de BTC' o 'valor de AAPL'."
            )

        responses = []
        for symbol in symbols[:3]:  # Limitar a 3 símbolos por respuesta
            try:
                asset_type = await self.market_service.detect_asset_type(symbol)
                price_data = await self.market_service.get_price(symbol, asset_type)

                if price_data:
                    response = (
                        f"**{symbol}**: {price_data['price']} ({price_data['change']})"
                    )
                    responses.append(response)
                else:
                    responses.append(f"**{symbol}**: No disponible")

            except Exception as e:
                print(f"Error getting price for {symbol}: {e}")
                responses.append(f"**{symbol}**: Error obteniendo datos")

        if responses:
            return "📊 Precios actuales:\n" + "\n".join(responses)
        else:
            return "No pude obtener precios para los símbolos mencionados."

    def get_default_response(self, message: str) -> str:
        """Respuesta por defecto para consultas generales"""
        return f"""🤖 **BullBearBroker Analysis**

He analizado tu consulta sobre "{message}". Como asistente financiero especializado, te recomiendo:

📊 **Diversificación**: Spread investments across stocks, crypto, bonds, and real estate
⏰ **Horizonte Temporal**: Align investments with your time horizon and goals
📉 **Gestión de Riesgo**: Never invest more than you can afford to lose
🔍 **Due Diligence**: Research thoroughly before any investment
💡 **Educación Continua**: Stay informed about market trends and developments

**¿En qué aspecto te gustaría que profundice?**
- 📈 Análisis técnico de algún activo
- 💰 Estrategias de inversión específicas
- 📰 Impacto de noticias recientes
- 🎯 Recomendaciones de portfolio"""

    async def get_fallback_response(self, message: str) -> str:
        """Respuesta de fallback para errores"""
        return f"""⚠️ **Estoy teniendo dificultades técnicas**

Lo siento, estoy experimentando problemas temporales para procesar tu solicitud sobre "{message}".

Mientras tanto, te sugiero:
1. 📊 Verificar precios directamente en exchanges confiables
2. 📰 Consultar noticias financieras recientes
3. 🔍 Realizar tu propio análisis fundamental

**Por favor intenta nuevamente en unos minutos.** Estoy trabajando para resolver el issue.

¿Hay algo más en lo que pueda ayudarte?"""

    async def analyze_sentiment(self, text: str) -> dict[str, float]:
        """Analizar sentimiento de texto (para noticias)"""
        try:
            if self.use_real_ai:
                return await mistral_service.analyze_market_sentiment(text)
        except Exception:
            pass

        # Fallback simple
        return {
            "sentiment_score": 0.0,
            "confidence": 0.7,
            "keywords": ["market", "analysis", "financial"],
        }


    async def process_with_context(self, session_id: str, message: str) -> dict[str, Any]:
        start = time.perf_counter()
        history_entries = context_service.get_history(session_id)
        history_context: list[dict[str, str]] = []
        for entry in history_entries:
            if entry.message:
                history_context.append({"role": "user", "content": entry.message})
            if entry.response:
                history_context.append({"role": "assistant", "content": entry.response})

        sentiment = sentiment_service.analyze_sentiment(message)
        base_context: dict[str, Any] | None = None
        if history_context:
            base_context = {"history": history_context}

        token = set_route("context")
        try:
            response_payload = await self.process_message(
                message,
                context=base_context,
            )
        finally:
            reset_route(token)
        response_text = (
            response_payload.text
            if hasattr(response_payload, "text")
            else str(response_payload)
        )

        context_service.save_message(session_id, message, response_text)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            json.dumps(
                {
                    "ai_event": "process_with_context",
                    "session": session_id,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "sentiment": sentiment["label"],
                    "history_len": len(history_entries),
                }
            )
        )

        return {
            "message": message,
            "response": response_text,
            "sentiment": sentiment,
            "history_len": len(history_entries),
        }


    async def stream_generate(self, prompt: str):
        """Simular generación de texto en streaming."""

        start_time = time.perf_counter()
        ai_conversations_active_total.inc()

        try:
            if not prompt or not prompt.strip():
                raise ValueError("El mensaje no puede estar vacío")

            # Simulación sencilla de tokens parciales manteniendo espacios.
            segments = re.findall(r"\S+\s*", prompt)
            if not segments:
                segments = [prompt]

            for token in segments:
                await asyncio.sleep(0.05)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                logger.info(
                    json.dumps(
                        {
                            "ai_event": "stream_chunk",
                            "length": len(token),
                            "elapsed_ms": round(elapsed_ms, 2),
                        }
                    )
                )
                ai_stream_tokens_total.inc(len(token))
                yield token

            completion_chunk = json.dumps({"error": False, "done": True})
            ai_stream_tokens_total.inc(len(completion_chunk))
            logger.info(
                json.dumps(
                    {
                        "ai_event": "stream_chunk",
                        "length": len(completion_chunk),
                        "elapsed_ms": round(
                            (time.perf_counter() - start_time) * 1000.0, 2
                        ),
                        "type": "completion",
                    }
                )
            )
            yield completion_chunk

        except (asyncio.TimeoutError, ValueError) as exc:
            logger.warning(
                json.dumps(
                    {
                        "ai_event": "stream_error",
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    }
                )
            )
            error_chunk = json.dumps({"error": True, "message": str(exc)})
            ai_stream_tokens_total.inc(len(error_chunk))
            yield error_chunk
            return

        except Exception as exc:  # pragma: no cover - defensivo
            logger.error(
                json.dumps(
                    {
                        "ai_event": "stream_error",
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    }
                ),
                exc_info=True,
            )
            error_chunk = json.dumps(
                {"error": True, "message": "Error inesperado generando respuesta"}
            )
            ai_stream_tokens_total.inc(len(error_chunk))
            yield error_chunk
            return

        finally:
            total_duration = time.perf_counter() - start_time
            ai_conversations_active_total.dec()
            ai_stream_duration_seconds.observe(total_duration)


# Singleton instance
ai_service = AIService()
