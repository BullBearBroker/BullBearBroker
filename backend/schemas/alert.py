"""Pydantic schemas for alert endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AlertBase(BaseModel):
    title: str = Field(..., max_length=255)
    asset: Optional[str] = Field(None, max_length=50)
    condition: str = Field(..., description="Expresión condicional en formato libre")
    value: Optional[float] = Field(None, description="Valor numérico auxiliar")
    active: bool = Field(True, description="Indica si la alerta está activa")

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El título de la alerta es obligatorio")
        return cleaned

    @field_validator("condition")
    @classmethod
    def _normalize_condition(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("La condición de la alerta es obligatoria")
        return value.strip()

    @field_validator("asset")
    @classmethod
    def _normalize_asset(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned.upper() if cleaned else None


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    asset: Optional[str] = Field(None, max_length=50)
    condition: Optional[str] = Field(None)
    value: Optional[float] = None
    active: Optional[bool] = None

    @field_validator("condition")
    @classmethod
    def _normalize_condition(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("La condición de la alerta es obligatoria")
        return cleaned

    @field_validator("asset")
    @classmethod
    def _normalize_asset(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned.upper() if cleaned else None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El título de la alerta es obligatorio")
        return cleaned


class AlertResponse(BaseModel):
    id: str
    title: str
    asset: str
    condition: str
    value: float
    active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, alert) -> "AlertResponse":
        return cls(
            id=str(alert.id),
            title=getattr(alert, "title", ""),
            asset=getattr(alert, "asset", ""),
            condition=getattr(alert, "condition", ""),
            value=float(getattr(alert, "value", 0.0)),
            active=bool(getattr(alert, "active", True)),
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )


class AlertListItem(AlertResponse):
    pass


class AlertSuggestionPayload(BaseModel):
    asset: str
    interval: Optional[str] = "1h"

    @field_validator("asset")
    @classmethod
    def _normalize_asset(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El símbolo del activo es obligatorio")
        return cleaned.upper()


class AlertSuggestionResult(BaseModel):
    suggestion: str
    notes: Optional[str] = None


__all__ = [
    "AlertBase",
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    "AlertListItem",
    "AlertSuggestionPayload",
    "AlertSuggestionResult",
]
