from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base
from backend.services.portfolio_service import PortfolioService


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def service(session_factory) -> PortfolioService:
    return PortfolioService(session_factory=session_factory)


def test_import_reports_row_errors(service: PortfolioService) -> None:
    user_id = uuid4()
    service.create_item(user_id, symbol="MSFT", amount=1)

    csv_payload = """symbol,amount\nmsft,2\nAAPL,foo\nAAPL,1\nGOOG,-5\nAMZN,3\n"""

    result = service.import_from_csv(user_id, content=csv_payload)

    assert result["created"] == 1
    assert [item["symbol"] for item in result["items"]] == ["AMZN"]
    assert len(result["errors"]) == 4
    messages = {error["row"]: error["message"] for error in result["errors"]}
    assert messages[2] == "El símbolo ya existe en tu portafolio"
    assert messages[3] == "La cantidad debe ser numérica"
    assert messages[4] == "Símbolo duplicado en el archivo"
    assert messages[5] == "La cantidad debe ser mayor que cero"


def test_import_supports_bom_and_semicolon(service: PortfolioService) -> None:
    user_id = uuid4()
    csv_payload = "\ufeffsymbol;amount\n btc ;1.5\neth;2\n"

    result = service.import_from_csv(user_id, content=csv_payload)

    assert result["created"] == 2
    assert {item["symbol"] for item in result["items"]} == {"BTC", "ETH"}
    assert result["errors"] == []


def test_import_enforces_size_limit(service: PortfolioService) -> None:
    user_id = uuid4()
    oversized = "symbol,amount\n" + "AAPL,1\n" * 40000

    with pytest.raises(ValueError) as exc_info:
        service.import_from_csv(user_id, content=oversized)

    assert "256KB" in str(exc_info.value)


def test_import_enforces_row_limit(service: PortfolioService) -> None:
    user_id = uuid4()
    rows = "\n".join(f"SYM{i},1" for i in range(1, 505))
    csv_payload = f"symbol,amount\n{rows}\n"

    result = service.import_from_csv(user_id, content=csv_payload)

    assert result["created"] == PortfolioService.MAX_IMPORT_ROWS
    last_error = result["errors"][-1]
    assert last_error["message"] == "El archivo CSV supera el máximo de 500 filas"
