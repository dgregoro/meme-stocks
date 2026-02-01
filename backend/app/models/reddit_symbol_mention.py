from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.data.database import Base


class RedditSymbolMention(Base):
    """Junction table linking Reddit posts to stock symbols (many-to-many)."""

    __tablename__ = "reddit_symbol_mentions"
    __table_args__ = (
        UniqueConstraint("post_id", "symbol", name="uq_post_symbol"),
        Index("idx_symbol_mentions_symbol", "symbol"),
        Index("idx_symbol_mentions_post", "post_id"),
    )

    post_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reddit_posts.id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.symbol"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    post = relationship("RedditPost", back_populates="symbol_mentions")
    stock = relationship("Stock", back_populates="reddit_mentions")
