"""Portfolio API endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.models.portfolio import Portfolio, Position
from backend.routers.alerts import get_current_user
from backend.schemas.portfolio import (
    PortfolioCreate,
    PortfolioOut,
    PositionCreate,
    PositionOut,
)
from backend.services.portfolio_service import (
    add_position,
    create_portfolio,
    get_portfolio_owned,
    get_position_owned,
    get_returns_series,
    list_portfolios,
    metrics,
    remove_position,
    risk_metrics,
    valuate_portfolio,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _position_to_out(position: Position) -> PositionOut:
    return PositionOut(
        id=position.id,
        symbol=position.symbol,
        quantity=float(position.quantity),
        avg_price=float(position.avg_price),
    )


def _portfolio_to_out(
    portfolio: Portfolio,
    *,
    totals: dict,
    metrics_data: dict | None,
    risk_data: dict | None,
    positions: list[Position] | None = None,
) -> PortfolioOut:
    def _sort_key(position: Position) -> tuple[float, str]:
        created_at = getattr(position, "created_at", None)
        if created_at is None:
            return (0.0, str(position.id))
        return (created_at.timestamp(), str(position.id))

    if positions is None:
        try:
            positions_data = list(portfolio.positions)
        except Exception:  # pragma: no cover - detached objects fall back to empty
            positions_data = []
    else:
        positions_data = positions

    positions_sorted = sorted(positions_data, key=_sort_key)
    positions_out = [_position_to_out(position) for position in positions_sorted]
    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        base_ccy=portfolio.base_ccy,
        positions=positions_out,
        totals=totals,
        metrics=metrics_data,
        risk=risk_data,
    )


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio_endpoint(
    payload: PortfolioCreate,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> PortfolioOut:
    try:
        portfolio = await asyncio.to_thread(create_portfolio, current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    totals = {"equity_value": 0.0, "pnl_abs": 0.0, "pnl_pct": 0.0}
    return _portfolio_to_out(
        portfolio, totals=totals, metrics_data=None, risk_data=None, positions=[]
    )


@router.get("", response_model=list[PortfolioOut])
async def list_portfolios_endpoint(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> list[PortfolioOut]:
    portfolios = await asyncio.to_thread(list_portfolios, current_user.id)
    return [
        _portfolio_to_out(
            portfolio,
            totals={"equity_value": 0.0, "pnl_abs": 0.0, "pnl_pct": 0.0},
            metrics_data=None,
            risk_data=None,
            positions=portfolio.positions,
        )
        for portfolio in portfolios
    ]


@router.get("/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio_endpoint(
    portfolio_id: UUID,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> PortfolioOut:
    try:
        portfolio = await asyncio.to_thread(
            get_portfolio_owned, current_user.id, portfolio_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    totals = await valuate_portfolio(portfolio.positions, base_ccy=portfolio.base_ccy)
    performance_series = get_returns_series(portfolio.positions)
    metrics_data = metrics(performance_series)
    risk_data = risk_metrics(performance_series, equity=totals.get("equity_value"))

    return _portfolio_to_out(
        portfolio,
        totals=totals,
        metrics_data=metrics_data,
        risk_data=risk_data,
        positions=portfolio.positions,
    )


@router.post(
    "/{portfolio_id}/positions",
    response_model=PositionOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_position_endpoint(
    portfolio_id: UUID,
    payload: PositionCreate,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> PositionOut:
    try:
        await asyncio.to_thread(get_portfolio_owned, current_user.id, portfolio_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        position = await asyncio.to_thread(add_position, portfolio_id, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _position_to_out(position)


@router.delete("/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_position_endpoint(
    position_id: UUID,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> Response:
    try:
        await asyncio.to_thread(get_position_owned, current_user.id, position_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await asyncio.to_thread(remove_position, position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
