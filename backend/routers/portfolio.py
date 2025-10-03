"""Routes for managing user portfolio holdings."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.schemas.portfolio import (
    PortfolioCreate,
    PortfolioImportError,
    PortfolioImportResult,
    PortfolioItemResponse,
    PortfolioSummaryResponse,
)

USER_SERVICE_ERROR: Exception | None = None

try:  # pragma: no cover - allow running from different entrypoints
    from backend.models import User
except ImportError:  # pragma: no cover
    from backend.models import User  # type: ignore

try:  # pragma: no cover
    from backend.services.user_service import (
        InvalidTokenError,
        UserNotFoundError,
        user_service,
    )
except RuntimeError as exc:  # pragma: no cover - missing configuration
    user_service = None  # type: ignore[assignment]
    InvalidTokenError = RuntimeError  # type: ignore[assignment]
    UserNotFoundError = RuntimeError  # type: ignore[assignment]
    USER_SERVICE_ERROR = exc
except ImportError:  # pragma: no cover
    from services.user_service import (  # type: ignore
        InvalidTokenError,
        UserNotFoundError,
        user_service,
    )

try:  # pragma: no cover
    from backend.services.portfolio_service import portfolio_service
except ImportError:  # pragma: no cover
    from services.portfolio_service import portfolio_service  # type: ignore

router = APIRouter(tags=["portfolio"])
security = HTTPBearer()


def _ensure_user_service_available() -> None:
    if user_service is None:
        detail = "Servicio de usuarios no disponible"
        if USER_SERVICE_ERROR is not None:
            detail = f"{detail}. {USER_SERVICE_ERROR}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    _ensure_user_service_available()
    try:
        return await asyncio.to_thread(
            user_service.get_current_user, credentials.credentials
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc


@router.get("", response_model=PortfolioSummaryResponse)
async def list_portfolio(
    current_user: Annotated[User, Depends(get_current_user)],
) -> PortfolioSummaryResponse:
    summary = await portfolio_service.get_portfolio_overview(current_user.id)
    items = [
        PortfolioItemResponse(
            id=item["id"],
            symbol=item["symbol"],
            amount=float(item["amount"]),
            price=item.get("price"),
            value=item.get("value"),
        )
        for item in summary["items"]
    ]
    return PortfolioSummaryResponse(items=items, total_value=summary["total_value"])


@router.get("/export", response_class=Response)
async def export_portfolio(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    csv_payload = await asyncio.to_thread(
        portfolio_service.export_to_csv, current_user.id
    )
    headers = {"Content-Disposition": 'attachment; filename="portfolio.csv"'}
    return Response(
        content=csv_payload,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.post("/import", response_model=PortfolioImportResult)
async def import_portfolio(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PortfolioImportResult:
    content_type = file.content_type or "text/csv"
    if "csv" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir un archivo CSV válido",
        )

    raw_data = await file.read()
    try:
        decoded = raw_data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:  # pragma: no cover - defensivo
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo CSV debe estar codificado en UTF-8",
        ) from exc

    try:
        result = await asyncio.to_thread(
            portfolio_service.import_from_csv,
            current_user.id,
            content=decoded,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    items = [
        PortfolioItemResponse(
            id=entry["id"],
            symbol=entry["symbol"],
            amount=float(entry["amount"]),
            price=None,
            value=None,
        )
        for entry in result["items"]
    ]

    errors = [PortfolioImportError(**error) for error in result["errors"]]
    return PortfolioImportResult(created=result["created"], items=items, errors=errors)


@router.post(
    "", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_portfolio_item(
    payload: PortfolioCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PortfolioItemResponse:
    try:
        item = await asyncio.to_thread(
            portfolio_service.create_item,
            current_user.id,
            symbol=payload.symbol,
            amount=payload.amount,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except UserNotFoundError as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return PortfolioItemResponse(
        id=item.id,
        symbol=item.symbol,
        amount=float(item.amount),
        price=None,
        value=None,
    )


@router.delete("/{item_id}", status_code=status.HTTP_200_OK)
async def delete_portfolio_item(
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    deleted = await asyncio.to_thread(
        portfolio_service.delete_item, current_user.id, item_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activo no encontrado en el portafolio",
        )

    return {"message": "Activo eliminado", "id": str(item_id)}
