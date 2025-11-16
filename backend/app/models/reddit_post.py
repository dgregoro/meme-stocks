from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.data.database import Base


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stock_symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("stocks.symbol"), index=True
    )
    subreddit: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(512))
    author: Mapped[str] = mapped_column(String(100))
    upvotes: Mapped[int] = mapped_column(Integer)
    comments: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String(512))

    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
