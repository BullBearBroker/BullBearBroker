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


def _ensure_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _describe_condition(condition: Any) -> str:
    if condition is None:
        return ""
    if isinstance(condition, dict):
        if "and" in condition:
            parts = [
                _describe_condition(item)
                for item in _ensure_sequence(condition.get("and"))
            ]
            parts = [part for part in parts if part]
            return " & ".join(parts)
        if "or" in condition:
            parts = [
                _describe_condition(item)
                for item in _ensure_sequence(condition.get("or"))
            ]
            parts = [part for part in parts if part]
            return " | ".join(parts)
        if "not" in condition:
            inner = _describe_condition(condition.get("not"))
            return f"NOT ({inner})" if inner else "NOT condition"

        segments: list[str] = []
        for indicator, payload in condition.items():
            if isinstance(payload, dict):
                inner_segments = [
                    f"{indicator} {op} {payload_value!r}"
                    for op, payload_value in sorted(payload.items())
                ]
                if inner_segments:
                    segments.append(" & ".join(inner_segments))
                else:
                    segments.append(str(indicator))
            elif isinstance(payload, (list, tuple, set)):
                joined = ", ".join(f"{item!r}" for item in payload)
                segments.append(f"{indicator} in [{joined}]")
            else:
                segments.append(f"{indicator} == {payload!r}")
        return " & ".join(segment for segment in segments if segment)

    if isinstance(condition, (list, tuple, set)):
        parts = [_describe_condition(item) for item in condition]
        return " & ".join(part for part in parts if part)

    return str(condition)


def _extract_asset_from_condition(condition: Any) -> str:
    if isinstance(condition, dict):
        asset_value = condition.get("asset")
        if isinstance(asset_value, str) and asset_value.strip():
            return asset_value.strip().upper()
        for value in condition.values():
            candidate = _extract_asset_from_condition(value)
            if candidate:
                return candidate
    elif isinstance(condition, (list, tuple, set)):
        for item in condition:
            candidate = _extract_asset_from_condition(item)
            if candidate:
                return candidate
    return ""


def _normalize_asset(value: Any) -> str | None:
    if value is None:
        return None
    asset = str(value).strip().upper()
    return asset or None


def _normalize_title(value: Any) -> str | None:
    if value is None:
        return None
    title = str(value).strip()
    return title or None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("Alert value must be numeric") from exc


def _default_alert_name(payload: dict[str, Any]) -> str:
    condition = payload.get("condition") or {}
    asset = ""
    for key in ("asset", "symbol", "ticker"):
        raw_value = payload.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            asset = raw_value.strip().upper()
            break
    if not asset:
        asset = _extract_asset_from_condition(condition)

    condition_text = _describe_condition(condition)
    if asset and condition_text:
        return f"{asset}: {condition_text}"
    if asset:
        return f"{asset} alert"
    if condition_text:
        return f"Alert: {condition_text}"
    return "Alert"


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
            return all(
                self.evaluate(item) for item in self._ensure_sequence(condition["and"])
            )
        if "or" in condition:
            return any(
                self.evaluate(item) for item in self._ensure_sequence(condition["or"])
            )
        if "not" in condition:
            return not self.evaluate(self._ensure_mapping(condition["not"]))

        if len(condition) != 1:
            raise ValueError(
                "Condition leaves must contain a single indicator definition"
            )

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
            name = _default_alert_name(data)

        active = bool(data.get("active", True))
        asset = _normalize_asset(data.get("asset"))
        title = _normalize_title(data.get("title") or name)
        condition_expression = _normalize_title(data.get("condition_expression"))
        value = _coerce_float(data.get("value"))

        with self._session_factory() as session:
            alert = Alert(
                user_id=user_id,
                name=name,
                condition=condition,
                delivery_method=delivery_method,
                active=active,
                pending_delivery=True,
            )
            if asset is not None:
                alert.asset = asset
            if title is not None:
                alert.title = title
            if condition_expression is not None:
                alert.condition_expression = condition_expression
            if value is not None:
                alert.value = value
            session.add(alert)
            session.commit()
            session.refresh(alert)
            session.expunge(alert)
            return alert

    def update_alert(
        self, user_id: UUID, alert_id: UUID, data: dict[str, Any]
    ) -> Alert:
        has_condition = "condition" in data
        condition = data.get("condition") if has_condition else None
        if has_condition:
            if not isinstance(condition, dict) or not condition:
                raise ValueError("Alert condition must be a non-empty JSON object")

        delivery_method: AlertDeliveryMethod | None = None
        if "delivery_method" in data:
            delivery_method_raw = (
                data.get("delivery_method") or AlertDeliveryMethod.PUSH
            )
            try:
                delivery_method = (
                    delivery_method_raw
                    if isinstance(delivery_method_raw, AlertDeliveryMethod)
                    else AlertDeliveryMethod(str(delivery_method_raw))
                )
            except ValueError as exc:
                raise ValueError("Invalid delivery method for alert") from exc

        name: str | None = None
        if "name" in data:
            name = str(data.get("name") or "").strip()

        asset = _normalize_asset(data.get("asset")) if "asset" in data else None

        set_title = False
        title = None
        if "title" in data:
            set_title = True
            title = _normalize_title(data.get("title"))
        elif "name" in data:
            set_title = True
            title = _normalize_title(name)

        condition_expression = (
            _normalize_title(data.get("condition_expression"))
            if "condition_expression" in data
            else None
        )

        value = _coerce_float(data.get("value")) if "value" in data else None
        active: bool | None = None
        if "active" in data:
            active = bool(data.get("active"))

        with self._session_factory() as session:
            alert = self._get_alert(session, user_id, alert_id)

            if name is not None:
                if name:
                    alert.name = name
                else:
                    context = dict(data)
                    if not has_condition:
                        context["condition"] = alert.condition
                    alert.name = _default_alert_name(context)

            if has_condition and condition is not None:
                alert.condition = condition
                alert.pending_delivery = True

            if delivery_method is not None:
                alert.delivery_method = delivery_method

            if active is not None:
                alert.active = active

            if asset is not None:
                alert.asset = asset

            if set_title:
                if title is not None:
                    alert.title = title
                elif alert.name:
                    alert.title = alert.name

            if condition_expression is not None:
                alert.condition_expression = condition_expression

            if value is not None:
                alert.value = value

            session.commit()
            session.refresh(alert)
            session.expunge(alert)
            return alert

    def list_alerts_for_user(self, user_id: UUID) -> list[Alert]:
        with self._session_factory() as session:
            results = (
                session.execute(
                    select(Alert)
                    .where(Alert.user_id == user_id)
                    .order_by(Alert.created_at.asc())
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

    def delete_all_alerts_for_user(self, user_id: UUID) -> int:
        with self._session_factory() as session:
            deleted = (
                session.query(Alert)
                .where(Alert.user_id == user_id)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(deleted)

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
