"""Pydantic schemas for portfolio and position endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class PortfolioCreate(BaseModel):
    name: str
    base_ccy: str | None = "USD"


class PositionCreate(BaseModel):
    symbol: str
    quantity: float
    avg_price: float


class PositionOut(BaseModel):
    id: UUID
    symbol: str
    quantity: float
    avg_price: float

    class Config:
        orm_mode = True


class PortfolioOut(BaseModel):
    id: UUID
    name: str
    base_ccy: str
    positions: list[PositionOut]
    totals: dict
    metrics: dict | None
    risk: dict | None

    class Config:
        orm_mode = True


__all__ = [
    "PortfolioCreate",
    "PositionCreate",
    "PositionOut",
    "PortfolioOut",
]
