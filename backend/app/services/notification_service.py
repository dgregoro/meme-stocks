from __future__ import annotations

from datetime import timedelta
from typing import List

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.data.repositories.notification_repo import NotificationRepository
from backend.app.data.repositories.price_data_repo import PriceDataRepository
from backend.app.data.repositories.stock_repo import StockRepository
from backend.app.models.notification import Notification
from backend.app.services.activity_detector import (
    detect_price_movement,
    detect_sentiment_shift,
    detect_volume_spike,
)
from backend.app.services.analysis_service import build_price_bars_for_stock
from backend.app.services.combined_signal_service import (
    SignalEvaluated,
    evaluate,
    from_activity_signal,
    from_rsi_signal,
    serialize_signal_metadata,
)
from backend.app.services.pattern_analyzer import analyze_price_trend
from backend.app.services.sentiment_analyzer import (
    SentimentSummary,
    calculate_weighted_sentiment,
)


def _build_combined_message(fired_signals: list[tuple[str, str]]) -> str:
    """Build human-readable message summarizing fired signals."""
    if not fired_signals:
        return "Multiple signals aligned"
    parts = [f"{stype}: {val}" for stype, val in fired_signals]
    return "Multiple signals aligned: " + ", ".join(parts)


def generate_notifications_for_stock(db: Session, symbol: str) -> List[Notification]:
    """Generate notifications for a single stock based on latest data.

    When combined_signal_alerts_only=False (default), creates individual alerts
    (volume, price, sentiment) and combined alerts when threshold met.
    When True, creates only combined alerts when threshold met.
    """

    stock_repo = StockRepository(db)
    if stock_repo.get(symbol) is None:
        return []

    settings = get_settings()
    price_repo = PriceDataRepository(db)
    notif_repo = NotificationRepository(db)

    notifications: list[Notification] = []
    prices = price_repo.list_for_stock(symbol)
    posts: list = []

    # --- Gather signals for combined evaluation ---
    vol_signal = None
    price_signal = None
    sentiment_signal = None
    rsi_signal_str: str | None = None
    rsi_value: float | None = None

    if len(prices) >= 2:
        latest = prices[-1]
        prev = prices[-2]
        avg_volume = sum(p.volume for p in prices[:-1]) / float(len(prices) - 1)
        vol_signal = detect_volume_spike(latest.volume, int(avg_volume))
        price_signal = detect_price_movement(latest.close, prev.close)

    if posts:
        window = timedelta(hours=settings.sentiment_window_hours)
        current_summary = calculate_weighted_sentiment(symbol, posts, window=window)
        if current_summary.mention_count > 0:
            previous_summary = SentimentSummary(
                stock_symbol=symbol,
                score=0.0,
                mention_count=0,
                window=current_summary.window,
                calculated_at=current_summary.calculated_at - current_summary.window,
            )
            sentiment_signal = detect_sentiment_shift(current_summary, previous_summary)

    if prices:
        bars = build_price_bars_for_stock(symbol, price_repo)
        trend = analyze_price_trend(bars)
        rsi_signal_str = trend.rsi_signal
        rsi_value = trend.rsi

    # --- Build SignalEvaluated list and evaluate ---
    signals: list[SignalEvaluated] = [
        from_activity_signal(vol_signal, "volume_spike", settings.combined_signal_weight_volume),
        from_activity_signal(price_signal, "price_movement", settings.combined_signal_weight_price),
        from_activity_signal(sentiment_signal, "sentiment_shift", settings.combined_signal_weight_sentiment),
        from_rsi_signal(rsi_signal_str, rsi_value, settings.combined_signal_weight_rsi),
    ]
    # Filter out empty signal_type (shouldn't happen with our adapters)
    signals = [s for s in signals if s.signal_type]
    evaluation = evaluate(symbol, signals)

    # --- Create combined alert when threshold met ---
    if evaluation.threshold_met:
        fired_parts = [
            (s.signal_type, str(s.raw_value) if s.raw_value is not None else "")
            for s in evaluation.signals_evaluated
            if s.fired and s.raw_value
        ]
        message = _build_combined_message(fired_parts)
        severity = "high" if evaluation.combined_score >= evaluation.threshold * 1.5 else "medium"
        combined_notif = Notification(
            stock_symbol=symbol,
            type="combined_signal",
            message=message,
            severity=severity,
            signal_metadata=serialize_signal_metadata(evaluation),
        )
        notif_repo.add(combined_notif)
        notifications.append(combined_notif)

    # --- Create individual alerts when not combined-only ---
    if not settings.combined_signal_alerts_only:
        if vol_signal is not None:
            n = Notification(
                stock_symbol=symbol,
                type=vol_signal.kind,
                message=vol_signal.message,
                severity=vol_signal.severity,
            )
            notif_repo.add(n)
            notifications.append(n)
        if price_signal is not None:
            n = Notification(
                stock_symbol=symbol,
                type=price_signal.kind,
                message=price_signal.message,
                severity=price_signal.severity,
            )
            notif_repo.add(n)
            notifications.append(n)
        if sentiment_signal is not None:
            n = Notification(
                stock_symbol=symbol,
                type=sentiment_signal.kind,
                message=sentiment_signal.message,
                severity=sentiment_signal.severity,
            )
            notif_repo.add(n)
            notifications.append(n)

    return notifications
