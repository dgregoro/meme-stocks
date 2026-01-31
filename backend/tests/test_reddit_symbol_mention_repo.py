from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.app.data.database import Base
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.reddit_symbol_mention_repo import (
    RedditSymbolMentionRepository,
)
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.reddit_post import RedditPost
from backend.app.models.reddit_symbol_mention import RedditSymbolMention
from backend.app.models.stock import Stock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_test_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return TestSessionLocal()


def test_mention_repo_add_and_get_symbols_for_post() -> None:
    """Test adding mentions and retrieving symbols for a post."""
    session = create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="GME", name="GameStop", sector="Retail", market_cap=None))
    stock_repo.add(Stock(symbol="AMC", name="AMC", sector="Entertainment", market_cap=None))

    post_repo = RedditPostRepository(session)
    mention_repo = RedditSymbolMentionRepository(session)

    now = datetime.now(timezone.utc)
    post = RedditPost(
        id="post1",
        subreddit="wallstreetbets",
        title="GME and AMC to the moon",
        author="user1",
        upvotes=100,
        comments=20,
        url="https://reddit.com/post1",
        posted_at=now,
        collected_at=now,
    )
    post_repo.add(post)
    mention_repo.add(RedditSymbolMention(post_id="post1", symbol="GME"))
    mention_repo.add(RedditSymbolMention(post_id="post1", symbol="AMC"))

    symbols = mention_repo.get_symbols_for_post("post1")
    assert set(symbols) == {"GME", "AMC"}


def test_mention_repo_get_posts_for_symbol() -> None:
    """Test retrieving mentions for a symbol."""
    session = create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="TSLA", name="Tesla", sector="Auto", market_cap=None))

    post_repo = RedditPostRepository(session)
    mention_repo = RedditSymbolMentionRepository(session)

    now = datetime.now(timezone.utc)
    post1 = RedditPost(
        id="p1",
        subreddit="stocks",
        title="TSLA",
        author="u1",
        upvotes=10,
        comments=2,
        url="/p1",
        posted_at=now,
        collected_at=now,
    )
    post2 = RedditPost(
        id="p2",
        subreddit="stocks",
        title="TSLA moon",
        author="u2",
        upvotes=20,
        comments=5,
        url="/p2",
        posted_at=now,
        collected_at=now,
    )
    post_repo.add(post1)
    post_repo.add(post2)
    mention_repo.add(RedditSymbolMention(post_id="p1", symbol="TSLA"))
    mention_repo.add(RedditSymbolMention(post_id="p2", symbol="TSLA"))

    mentions = mention_repo.get_posts_for_symbol("TSLA")
    assert len(mentions) == 2
    post_ids = {m.post_id for m in mentions}
    assert post_ids == {"p1", "p2"}


def test_mention_repo_count_recent_mentions() -> None:
    """Test counting recent mentions within a time window."""
    session = create_test_session()
    stock_repo = StockRepository(session)
    stock_repo.add(Stock(symbol="NVDA", name="NVIDIA", sector="Tech", market_cap=None))

    post_repo = RedditPostRepository(session)
    mention_repo = RedditSymbolMentionRepository(session)

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=2)

    recent_post = RedditPost(
        id="recent",
        subreddit="stocks",
        title="NVDA",
        author="u1",
        upvotes=10,
        comments=2,
        url="/recent",
        posted_at=now,
        collected_at=now,
    )
    old_post = RedditPost(
        id="old",
        subreddit="stocks",
        title="NVDA old",
        author="u2",
        upvotes=5,
        comments=1,
        url="/old",
        posted_at=old_time,
        collected_at=old_time,
    )
    post_repo.add(recent_post)
    post_repo.add(old_post)
    mention_repo.add(RedditSymbolMention(post_id="recent", symbol="NVDA"))
    mention_repo.add(RedditSymbolMention(post_id="old", symbol="NVDA"))

    count_24h = mention_repo.count_recent_mentions("NVDA", timedelta(hours=24))
    assert count_24h == 1

    count_72h = mention_repo.count_recent_mentions("NVDA", timedelta(hours=72))
    assert count_72h == 2


def test_mention_repo_get_symbols_for_post_empty() -> None:
    """Test get_symbols_for_post returns empty for post with no mentions."""
    session = create_test_session()
    mention_repo = RedditSymbolMentionRepository(session)

    symbols = mention_repo.get_symbols_for_post("nonexistent")
    assert list(symbols) == []
