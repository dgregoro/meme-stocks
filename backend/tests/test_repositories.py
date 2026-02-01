from __future__ import annotations

from datetime import datetime, timedelta, date, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.data.database import Base
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.reddit_symbol_mention_repo import (
    RedditSymbolMentionRepository,
)
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.price_data import PriceData
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
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


def test_reddit_post_repository_add_and_list_for_stock() -> None:
    session = create_test_session()

    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))

    post_repo = RedditPostRepository(session)
    mention_repo = RedditSymbolMentionRepository(session)

    now = datetime.now(timezone.utc)
    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="AMC to the moon",
        author="user1",
        upvotes=100,
        comments=20,
        url="https://reddit.com/post1",
        posted_at=now,
        collected_at=now,
    )
    post_repo.add(post)
    mention_repo.add(RedditSymbolMention(post_id="post1", symbol="AMC"))

    posts = post_repo.list_for_stock("AMC")
    assert len(posts) == 1
    assert posts[0].id == "post1"


def test_reddit_post_repository_count_recent_mentions() -> None:
    session = create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="TSLA", name="Tesla", sector="Auto", market_cap=None))

    post_repo = RedditPostRepository(session)
    mention_repo = RedditSymbolMentionRepository(session)

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=2)

    recent_post = RedditPost(
        id="recent",
        subreddit="wallstreetbets",
        title="TSLA",
        author="user1",
        upvotes=10,
        comments=2,
        url="https://reddit.com/recent",
        posted_at=now,
        collected_at=now,
    )
    old_post = RedditPost(
        id="old",
        subreddit="wallstreetbets",
        title="TSLA old",
        author="user2",
        upvotes=5,
        comments=1,
        url="https://reddit.com/old",
        posted_at=old_time,
        collected_at=old_time,
    )
    post_repo.add(recent_post)
    mention_repo.add(RedditSymbolMention(post_id="recent", symbol="TSLA"))
    post_repo.add(old_post)
    mention_repo.add(RedditSymbolMention(post_id="old", symbol="TSLA"))

    count_24h = post_repo.count_recent_mentions("TSLA", timedelta(hours=24))
    assert count_24h == 1


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
