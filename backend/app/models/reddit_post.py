from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class RedditPost(Base):
    """Model for Reddit posts/submissions.

    Posts are stored once, with symbol mentions tracked separately
    in the RedditSymbolMention junction table.
    """

    __tablename__ = "reddit_posts"
    __table_args__ = (
        Index("idx_reddit_posts_subreddit", "subreddit"),
        Index("idx_reddit_posts_posted_at", "posted_at"),
        Index("idx_reddit_posts_collected_at", "collected_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    subreddit: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(512))
    author: Mapped[str] = mapped_column(String(100))
    upvotes: Mapped[int] = mapped_column(Integer)
    comments: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String(512))

    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    symbol_mentions = relationship("RedditSymbolMention", back_populates="post", cascade="all, delete-orphan")
