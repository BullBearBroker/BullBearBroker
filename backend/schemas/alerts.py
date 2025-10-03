"""Pydantic schemas for the advanced alerts API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.models.alert import Alert, AlertDeliveryMethod

Op = Literal["<", ">", "<=", ">=", "==", "crosses_above", "crosses_below"]

_COMPARATOR_MAP: dict[str, str] = {
    "<": "lt",
    "<=": "lte",
    ">": "gt",
    ">=": "gte",
    "==": "eq",
}

_COMPARATOR_SYMBOL: dict[str, str] = {
    "<": "<",
    "<=": "≤",
    ">": ">",
    ">=": "≥",
    "==": "=",
}

_CHANNEL_MAP: dict[str, AlertDeliveryMethod] = {
    "push": AlertDeliveryMethod.PUSH,
    "email": AlertDeliveryMethod.EMAIL,
    "webhook": AlertDeliveryMethod.WEBHOOK,
}

_LEGACY_OPERATOR_MAP: dict[str, str] = {
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "==": "==",
    "=": "==",
}


class AlertCondition(BaseModel):
    """Single rule for an alert condition."""

    field: str = Field(..., min_length=1)
    op: Op
    value: float | None = None

    @model_validator(mode="after")
    def _normalize(self) -> "AlertCondition":
        field = self.field.strip()
        if not field:
            raise ValueError("field es obligatorio")
        self.field = field

        if self.op in _COMPARATOR_MAP and self.value is None:
            raise ValueError("value es obligatorio para comparaciones numéricas")
        if self.value is not None:
            try:
                self.value = float(self.value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError("value debe ser numérico") from exc

        if self.op in {"crosses_above", "crosses_below"} and self.value is None:
            raise ValueError("value es obligatorio para operadores 'crosses'")

        return self

    def to_mapping(self) -> dict[str, Any]:
        """Return the JSON payload expected by the alerts service."""

        if self.op in _COMPARATOR_MAP:
            assert self.value is not None  # validated in _normalize
            return {self.field: {_COMPARATOR_MAP[self.op]: self.value}}

        if self.op == "crosses_above":
            assert self.value is not None
            return {self.field: {"crosses_above": self.value}}
        if self.op == "crosses_below":
            assert self.value is not None
            return {self.field: {"crosses_below": self.value}}

        raise ValueError(f"Operador no soportado: {self.op}")

    def to_expression(self) -> str:
        """Render a human readable representation of the condition."""

        if self.op in _COMPARATOR_SYMBOL:
            symbol = _COMPARATOR_SYMBOL[self.op]
            return f"{self.field} {symbol} {self.value}".strip()
        if self.op == "crosses_above":
            return f"{self.field} cruza por encima de {self.value}".strip()
        if self.op == "crosses_below":
            return f"{self.field} cruza por debajo de {self.value}".strip()
        return self.field


class AlertCreate(BaseModel):
    """Payload accepted by the alerts endpoints for create/update."""

    asset: str | None = None
    channel: Literal["push", "email", "webhook"] = "push"
    active: bool = True
    name: Optional[str] = None
    title: Optional[str] = None
    value: float | None = None
    condition: dict[str, Any] | None = None
    conditions: Optional[List[AlertCondition]] = None
    legacy_mode: bool = Field(default=False, exclude=True)
    legacy_operator: str | None = Field(default=None, exclude=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _ingest_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        condition = payload.get("condition")
        conditions = payload.get("conditions")

        if condition is not None and conditions:
            raise ValueError("Use solo 'condition' o 'conditions', no ambos.")

        if isinstance(condition, str):
            op = condition.strip()
            mapped = _LEGACY_OPERATOR_MAP.get(op)
            if mapped is None:
                raise ValueError("Operador de condición legacy no soportado")
            value = payload.get("value")
            if value is None:
                raise ValueError("value es obligatorio para condiciones legacy")
            payload["conditions"] = [{"field": "close", "op": mapped, "value": value}]
            payload.pop("condition", None)
            payload["legacy_mode"] = True
            payload["legacy_operator"] = op
        elif isinstance(condition, dict) and not conditions:
            # Mantener compatibilidad con el formato JSON avanzado existente
            payload["condition"] = condition
        elif condition is not None:
            raise ValueError("Formato de 'condition' no soportado")

        if conditions is not None:
            payload["conditions"] = list(conditions)

        return payload

    @model_validator(mode="after")
    def _normalize(self) -> "AlertCreate":
        if self.title:
            cleaned_title = self.title.strip()
            self.title = cleaned_title or None

        if not self.name and self.title:
            self.name = self.title

        if self.name:
            cleaned = self.name.strip()
            self.name = cleaned or None

        if self.asset is not None:
            asset_clean = self.asset.strip().upper()
            if not asset_clean:
                raise ValueError("asset es obligatorio")
            self.asset = asset_clean
        elif self.legacy_mode:
            raise ValueError("asset es obligatorio")

        if self.conditions:
            condition_nodes = [condition.to_mapping() for condition in self.conditions]
            if len(condition_nodes) == 1:
                self.condition = condition_nodes[0]
            else:
                self.condition = {"and": condition_nodes}
            if self.value is None and self.conditions:
                self.value = self.conditions[0].value

        if not self.condition:
            raise ValueError("conditions debe tener al menos 1 condición")

        if self.channel not in _CHANNEL_MAP:
            raise ValueError("Canal de alerta no soportado")

        if self.value is not None:
            try:
                self.value = float(self.value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensivo
                raise ValueError("value debe ser numérico") from exc

        return self

    def to_service_payload(self) -> dict[str, Any]:
        """Normalize the payload into the structure expected by the service layer."""

        condition_payload = self.condition
        condition_expression: str | None = None
        if self.legacy_mode:
            condition_expression = self.legacy_operator
        elif self.conditions:
            expression_parts = [cond.to_expression() for cond in self.conditions]
            condition_expression = (
                " AND ".join(part for part in expression_parts if part) or None
            )

        payload: dict[str, Any] = {
            "name": self.name,
            "condition": condition_payload,
            "delivery_method": _CHANNEL_MAP[self.channel],
            "asset": self.asset,
            "title": self.title or self.name,
            "condition_expression": condition_expression,
            "value": self.value,
            "active": self.active,
        }

        return {key: value for key, value in payload.items() if value is not None}


class AlertUpdate(BaseModel):
    """Payload used for updating existing alerts."""

    asset: str | None = None
    channel: Literal["push", "email", "webhook"] | None = None
    active: bool | None = None
    name: Optional[str] = None
    title: Optional[str] = None
    value: float | None = None
    condition: dict[str, Any] | None = None
    conditions: Optional[List[AlertCondition]] = None
    legacy_mode: bool = Field(default=False, exclude=True)
    legacy_operator: str | None = Field(default=None, exclude=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _ingest_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        if "condition" in payload:
            condition = payload.get("condition")
            if isinstance(condition, str):
                op = condition.strip()
                mapped = _LEGACY_OPERATOR_MAP.get(op)
                if mapped is None:
                    raise ValueError("Operador de condición legacy no soportado")
                value = payload.get("value")
                if value is not None:
                    payload["conditions"] = [
                        {"field": "close", "op": mapped, "value": value}
                    ]
                payload.pop("condition", None)
                payload["legacy_mode"] = True
                payload["legacy_operator"] = op
            elif isinstance(condition, dict):
                payload["condition"] = condition
            else:
                raise ValueError("Formato de 'condition' no soportado")

        if "conditions" in payload and payload["conditions"] is not None:
            payload["conditions"] = list(payload["conditions"])

        return payload

    @model_validator(mode="after")
    def _normalize(self) -> "AlertUpdate":
        if self.title:
            cleaned_title = self.title.strip()
            self.title = cleaned_title or None

        if self.name:
            cleaned = self.name.strip()
            self.name = cleaned or None
        elif self.title:
            self.name = self.title

        if self.asset is not None:
            asset_clean = self.asset.strip().upper()
            if not asset_clean:
                raise ValueError("asset es obligatorio")
            self.asset = asset_clean

        if self.channel is not None and self.channel not in _CHANNEL_MAP:
            raise ValueError("Canal de alerta no soportado")

        if self.conditions:
            condition_nodes = [condition.to_mapping() for condition in self.conditions]
            if len(condition_nodes) == 1:
                self.condition = condition_nodes[0]
            else:
                self.condition = {"and": condition_nodes}
            if self.value is None:
                self.value = self.conditions[0].value

        if self.value is not None:
            try:
                self.value = float(self.value)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensivo
                raise ValueError("value debe ser numérico") from exc

        return self

    def to_service_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}

        if self.name is not None:
            payload["name"] = self.name
        if self.conditions:
            payload["condition"] = self.condition
        elif self.condition is not None:
            payload["condition"] = self.condition

        if self.channel is not None:
            payload["delivery_method"] = _CHANNEL_MAP[self.channel]

        if self.asset is not None:
            payload["asset"] = self.asset

        if self.title is not None or self.name is not None:
            payload["title"] = self.title or self.name

        if self.value is not None:
            payload["value"] = self.value

        if self.active is not None:
            payload["active"] = self.active

        if self.legacy_mode and self.legacy_operator:
            payload["condition_expression"] = self.legacy_operator
        elif "condition" in payload and self.conditions:
            expression_parts = [cond.to_expression() for cond in self.conditions]
            payload["condition_expression"] = (
                " AND ".join(part for part in expression_parts if part) or None
            )

        return {key: value for key, value in payload.items() if value is not None}


class AlertToggle(BaseModel):
    active: bool


class AlertOut(BaseModel):
    """Representation of alerts returned to clients."""

    id: Any
    name: str
    asset: str | None
    channel: Literal["push", "email", "webhook"]
    pending_delivery: bool
    created_at: datetime
    updated_at: datetime
    condition: dict[str, Any]
    condition_expression: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, alert: Alert) -> "AlertOut":
        channel = alert.delivery_method.value
        return cls(
            id=alert.id,
            name=alert.name,
            asset=getattr(alert, "asset", None),
            channel=channel if channel in _CHANNEL_MAP else "push",
            pending_delivery=alert.pending_delivery,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
            condition=alert.condition,
            condition_expression=getattr(alert, "condition_expression", None),
        )


__all__ = [
    "AlertCondition",
    "AlertCreate",
    "AlertUpdate",
    "AlertOut",
    "AlertToggle",
]
