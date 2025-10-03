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
    condition: dict[str, Any]
    delivery_method: AlertDeliveryMethod = AlertDeliveryMethod.PUSH
    active: bool = True

    @field_validator("condition")
    @classmethod
    def _validate_condition(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict) or not value:
            raise ValueError("La condición debe ser un objeto JSON válido")
        return value


class AlertCreate(AlertBase):
    name: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AlertUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    condition: dict[str, Any] | None = None
    delivery_method: AlertDeliveryMethod | None = None
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("condition")
    @classmethod
    def _validate_condition(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict) or not value:
            raise ValueError("La condición debe ser un objeto JSON válido")
        return value


class AlertToggle(BaseModel):
    active: bool


class AlertOut(AlertBase):
    name: str
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


__all__ = ["AlertCreate", "AlertUpdate", "AlertOut", "AlertToggle"]
