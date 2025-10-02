"""Pydantic schemas for portfolio endpoints."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PortfolioCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    amount: float = Field(..., gt=0)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El símbolo es obligatorio")
        return cleaned.upper()


class PortfolioItemResponse(BaseModel):
    id: UUID
    symbol: str
    amount: float
    price: Optional[float] = None
    value: Optional[float] = None

    model_config = {
        "from_attributes": True,
    }


class PortfolioSummaryResponse(BaseModel):
    items: List[PortfolioItemResponse]
    total_value: float


class PortfolioImportError(BaseModel):
    row: int
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {"row": 5, "message": "La cantidad debe ser numérica"}
        }
    }


class PortfolioImportResult(BaseModel):
    created: int
    items: List[PortfolioItemResponse]
    errors: List[PortfolioImportError]

    model_config = {
        "json_schema_extra": {
            "example": {
                "created": 1,
                "items": [
                    {"id": "6b2c6d4d-5b2f-4cd0-9e10-0afadf7c6c71", "symbol": "AAPL", "amount": 3.0}
                ],
                "errors": [
                    {"row": 4, "message": "El símbolo ya existe en tu portafolio"}
                ],
            }
        }
    }


__all__ = [
    "PortfolioCreate",
    "PortfolioItemResponse",
    "PortfolioSummaryResponse",
    "PortfolioImportError",
    "PortfolioImportResult",
]
