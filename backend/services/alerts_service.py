"""Advanced alerts service with JSON-based conditions and push delivery."""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.database import SessionLocal
from backend.models import Alert, AlertDeliveryMethod, PushSubscription, User
from backend.services import indicators_service
from backend.services.push_service import push_service


ComparisonOperator = Callable[[float, float], bool]


class ConditionEvaluator:
    """Evaluate alert conditions expressed as JSON structures."""

    _OPERATORS: dict[str, ComparisonOperator] = {
        "lt": operator.lt,
        "lte": operator.le,
        "gt": operator.gt,
        "gte": operator.ge,
        "eq": operator.eq,
        "neq": operator.ne,
    }

    def __init__(self, market_data: dict[str, Any]) -> None:
        self._market_data = market_data
        self._cache: dict[str, float] = {}

    def evaluate(self, condition: dict[str, Any]) -> bool:
        if not isinstance(condition, dict):
            raise ValueError("Condition payload must be a JSON object")

        if "and" in condition:
            return all(self.evaluate(item) for item in self._ensure_sequence(condition["and"]))
        if "or" in condition:
            return any(self.evaluate(item) for item in self._ensure_sequence(condition["or"]))
        if "not" in condition:
            return not self.evaluate(self._ensure_mapping(condition["not"]))

        if len(condition) != 1:
            raise ValueError("Condition leaves must contain a single indicator definition")

        indicator, payload = next(iter(condition.items()))
        return self._evaluate_indicator(indicator, self._ensure_mapping(payload))

    @staticmethod
    def _ensure_sequence(value: Any) -> Iterable[dict[str, Any]]:
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ValueError("Logical operator expects a list of conditions")
        return value  # type: ignore[return-value]

    @staticmethod
    def _ensure_mapping(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("Condition block must be an object")
        return value

    def _evaluate_indicator(self, name: str, payload: dict[str, Any]) -> bool:
        left_value = self._resolve_metric(name)
        for op_name, raw_operand in payload.items():
            comparator = self._OPERATORS.get(op_name.lower())
            if comparator is None:
                raise ValueError(f"Unsupported comparator '{op_name}' in condition")
            right_value = self._resolve_operand(raw_operand)
            if not comparator(left_value, right_value):
                return False
        return True

    def _resolve_metric(self, name: str) -> float:
        key = name.lower()
        if key in self._cache:
            return self._cache[key]

        value: float
        if key in self._market_data:
            value = float(self._market_data[key])
        elif key == "close":
            latest = self._market_data.get("latest") or {}
            if "close" not in latest:
                raise ValueError("Market data missing 'close' price")
            value = float(latest["close"])
        elif key == "rsi":
            prices = self._market_data.get("prices") or self._market_data.get("closes")
            if not prices:
                raise ValueError("RSI evaluation requires 'prices'")
            value = float(indicators_service.calculate_rsi(prices))
        elif key == "vwap":
            prices = self._market_data.get("prices")
            volumes = self._market_data.get("volumes")
            if not prices or not volumes:
                raise ValueError("VWAP evaluation requires 'prices' and 'volumes'")
            value = float(indicators_service.calculate_vwap(prices, volumes))
        elif key == "atr":
            candles = self._market_data.get("candles")
            if not candles:
                raise ValueError("ATR evaluation requires 'candles'")
            value = float(indicators_service.calculate_atr(candles))
        else:
            indicators = self._market_data.get("indicators", {})
            if key not in indicators:
                raise ValueError(f"Unknown metric '{name}' in condition")
            value = float(indicators[key])

        self._cache[key] = value
        return value

    def _resolve_operand(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            try:
                return float(value)
            except ValueError:
                return self._resolve_metric(value)
        raise ValueError("Condition operands must be numbers or indicator references")


class AlertsService:
    """Service that manages CRUD operations and evaluation of advanced alerts."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def create_alert(self, user_id: UUID, data: dict[str, Any]) -> Alert:
        condition = data.get("condition")
        if not isinstance(condition, dict) or not condition:
            raise ValueError("Alert condition must be a non-empty JSON object")

        delivery_method_raw = data.get("delivery_method", AlertDeliveryMethod.PUSH)
        try:
            delivery_method = (
                delivery_method_raw
                if isinstance(delivery_method_raw, AlertDeliveryMethod)
                else AlertDeliveryMethod(str(delivery_method_raw))
            )
        except ValueError as exc:
            raise ValueError("Invalid delivery method for alert") from exc

        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Alert name is required")

        active = bool(data.get("active", True))

        with self._session_factory() as session:
            alert = Alert(
                user_id=user_id,
                name=name,
                condition=condition,
                delivery_method=delivery_method,
                active=active,
                pending_delivery=True,
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            session.expunge(alert)
            return alert

    def list_alerts_for_user(self, user_id: UUID) -> list[Alert]:
        with self._session_factory() as session:
            results = (
                session.execute(
                    select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.asc())
                )
                .scalars()
                .all()
            )
            for alert in results:
                session.expunge(alert)
            return results

    def toggle_alert(self, user_id: UUID, alert_id: UUID, *, active: bool) -> Alert:
        with self._session_factory() as session:
            alert = self._get_alert(session, user_id, alert_id)
            alert.active = active
            session.commit()
            session.refresh(alert)
            session.expunge(alert)
            return alert

    def delete_alert(self, user_id: UUID, alert_id: UUID) -> None:
        with self._session_factory() as session:
            alert = self._get_alert(session, user_id, alert_id)
            session.delete(alert)
            session.commit()

    # ------------------------------------------------------------------
    # Evaluation logic
    # ------------------------------------------------------------------
    def evaluate_alerts(self, market_data: dict[str, Any]) -> list[UUID]:
        evaluator = ConditionEvaluator(market_data)
        triggered_ids: list[UUID] = []

        with self._session_factory() as session:
            alerts = (
                session.execute(select(Alert).where(Alert.active.is_(True)))
                .scalars()
                .all()
            )
            for alert in alerts:
                try:
                    if evaluator.evaluate(alert.condition):
                        triggered_ids.append(alert.id)
                        self._deliver_alert(session, alert)
                except ValueError:
                    # Condición inválida -> marcamos como inactiva para evitar spam
                    alert.active = False
            session.commit()

        return triggered_ids

    def send_alert(self, alert: Alert, user: User) -> int:
        with self._session_factory() as session:
            persistent_alert = self._get_alert(session, user.id, alert.id)
            return self._deliver_alert(session, persistent_alert)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _get_alert(self, session: Session, user_id: UUID, alert_id: UUID) -> Alert:
        alert = (
            session.execute(
                select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
            )
            .scalars()
            .first()
        )
        if alert is None:
            raise ValueError("Alert not found")
        return alert

    def _deliver_alert(self, session: Session, alert: Alert) -> int:
        user = session.get(User, alert.user_id)
        if user is None:
            return 0

        if alert.delivery_method != AlertDeliveryMethod.PUSH:
            alert.pending_delivery = False
            return 0

        subscriptions = (
            session.execute(
                select(PushSubscription).where(PushSubscription.user_id == user.id)
            )
            .scalars()
            .all()
        )
        if not subscriptions:
            alert.pending_delivery = False
            return 0

        payload = {
            "type": "alert",
            "name": alert.name,
            "condition": alert.condition,
        }
        delivered = push_service.broadcast(subscriptions, payload, category="alerts")
        alert.pending_delivery = delivered > 0
        return delivered


alerts_service = AlertsService()


__all__ = ["AlertsService", "alerts_service"]
