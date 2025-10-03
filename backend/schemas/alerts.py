"""Pydantic schemas for advanced alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.alert import Alert, AlertDeliveryMethod


class ConditionModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AlertBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    condition: dict[str, Any]
    delivery_method: AlertDeliveryMethod = AlertDeliveryMethod.PUSH
    active: bool = True

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre de la alerta es obligatorio")
        return value

    @field_validator("condition")
    @classmethod
    def _validate_condition(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict) or not value:
            raise ValueError("La condición debe ser un objeto JSON válido")
        return value


class AlertCreate(AlertBase):
    pass


class AlertToggle(BaseModel):
    active: bool


class AlertOut(AlertBase):
    id: UUID
    pending_delivery: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, alert: Alert) -> "AlertOut":
        return cls(
            id=alert.id,
            name=alert.name,
            condition=alert.condition,
            delivery_method=alert.delivery_method,
            active=alert.active,
            pending_delivery=alert.pending_delivery,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )


__all__ = ["AlertCreate", "AlertOut", "AlertToggle"]
