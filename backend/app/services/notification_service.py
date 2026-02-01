from __future__ import annotations

from datetime import timedelta
from typing import List

from sqlalchemy.orm import Session

from backend.app.data.repositories.notification_repo import NotificationRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.reddit_post_repo import RedditPostRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.notification import Notification
from backend.app.services.activity_detector import (
    detect_price_movement,
    detect_sentiment_shift,
    detect_volume_spike,
)
from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    calculate_weighted_sentiment,
)


def generate_notifications_for_stock(db: Session, symbol: str) -> List[Notification]:
    """Generate notifications for a single stock based on latest data.

    This does not perform scheduling; it is a pure operation over current
    DB state and returns Notification objects that are also persisted.
    """

    stock_repo = StockRepository(db)
    if stock_repo.get(symbol) is None:
        return []

    reddit_repo = RedditPostRepository(db)
    price_repo = PriceDataRepository(db)
    notif_repo = NotificationRepository(db)

    notifications: list[Notification] = []

    # Volume spike / price movement using last two price points if available
    prices = price_repo.list_for_stock(symbol)
    if len(prices) >= 2:
        latest = prices[-1]
        prev = prices[-2]

        # Volume spike relative to simple average of previous N volumes (here: all except latest)
        avg_volume = sum(p.volume for p in prices[:-1]) / float(len(prices) - 1) if len(prices) > 1 else 0
        vol_signal = detect_volume_spike(latest.volume, int(avg_volume))
        if vol_signal is not None:
            n = Notification(
                stock_symbol=symbol,
                type=vol_signal.kind,
                message=vol_signal.message,
                severity=vol_signal.severity,
            )
            notif_repo.add(n)
            notifications.append(n)

        price_signal = detect_price_movement(latest.close, prev.close)
        if price_signal is not None:
            n = Notification(
                stock_symbol=symbol,
                type=price_signal.kind,
                message=price_signal.message,
                severity=price_signal.severity,
            )
            notif_repo.add(n)
            notifications.append(n)

    # Sentiment shift using last two 24h windows if possible (simplified: compare current vs. older window)
    posts = reddit_repo.list_for_stock(symbol)
    if posts:
        current_summary: SentimentSummary = calculate_weighted_sentiment(symbol, posts, window=timedelta(hours=24))
        # For now, we skip historic sentiment and only emit shift when there were previous mentions;
        # a more advanced implementation would cache/store prior summaries.
        if current_summary.mention_count > 0:
            # Placeholder: treat previous summary as neutral baseline (0.0)
            previous_summary = SentimentSummary(
                stock_symbol=symbol,
                score=0.0,
                mention_count=0,
                window=current_summary.window,
                calculated_at=current_summary.calculated_at - current_summary.window,
            )

            s_signal = detect_sentiment_shift(current_summary, previous_summary)
            if s_signal is not None:
                n = Notification(
                    stock_symbol=symbol,
                    type=s_signal.kind,
                    message=s_signal.message,
                    severity=s_signal.severity,
                )
                notif_repo.add(n)
                notifications.append(n)

    return notifications
