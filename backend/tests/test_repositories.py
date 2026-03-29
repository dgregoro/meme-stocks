from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.models.stock import Stock


def create_test_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return TestSessionLocal()


def test_stock_repository_add_and_get() -> None:
    session = create_test_session()
    repo = StockRepository(session)

    stock = Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=1_000_000_000)
    repo.add(stock)

    fetched = repo.get("GME")
    assert fetched is not None
    assert fetched.symbol == "GME"
    assert fetched.name == "GameStop"


def test_price_data_repository_add_and_query() -> None:
    session = create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="BBBY", name="Bed Bath & Beyond", sector="Retail", market_cap=None))

    repo = PriceDataRepository(session)

    d = date(2024, 1, 1)
    price = PriceData(
        stock_symbol="BBBY",
        date=d,
        open=10.0,
        high=12.0,
        low=9.5,
        close=11.5,
        volume=1_000_000,
    )
    repo.add(price)

    all_prices = repo.list_for_stock("BBBY")
    assert len(all_prices) == 1
    assert all_prices[0].close == 11.5

    fetched = repo.get_for_date("BBBY", d)
    assert fetched is not None
    assert fetched.date == d
