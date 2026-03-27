"""Leader-follower signal detection service.

Detects significant price/volume moves (leaders), identifies follower candidates
in the same group, and emits structured opportunity signals.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from backend.app.config import get_settings
from backend.app.models.leader_event import LeaderEvent

if TYPE_CHECKING:
    from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.stock_group_repo import StockGroupRepository
    from backend.app.data.repositories.stock_repo import StockRepository

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIN_BARS_FOR_LEADER = 5


def compute_event_date(
    price_repo: PriceDataRepository,
    stock_repo: StockRepository,
) -> dt.date | None:
    """Return max(price_data.date) across tracked symbols, or None if empty."""
    stocks = stock_repo.list()
    symbols = [s.symbol for s in stocks]
    if not symbols:
        return None
    return price_repo.get_max_date(symbols)


REJECTION_INSUFFICIENT_BARS = "insufficient_bars"
REJECTION_NO_DATA_ON_EVENT_DATE = "no_data_on_event_date"
REJECTION_ZERO_AVG_VOLUME = "zero_avg_volume"
REJECTION_BELOW_RETURN_THRESHOLD = "below_return_threshold"
REJECTION_INSUFFICIENT_VOLUME = "insufficient_volume"
REJECTION_ERROR = "error"


def _get_effective_thresholds() -> tuple[float, float]:
    """Return (return_threshold, volume_threshold) based on debug mode."""
    settings = get_settings()
    if settings.leader_follower_debug_mode:
        return (
            settings.leader_return_threshold_pct_debug,
            settings.leader_volume_spike_threshold_debug,
        )
    return settings.leader_return_threshold_pct, settings.leader_volume_spike_threshold


def detect_leaders(
    db: Session,
    event_date: dt.date,
    symbols: list[str],
    run_id: int | None = None,
) -> tuple[list[LeaderEvent], list[dict[str, object]]]:
    """Detect leaders for event_date from the given symbols. Returns (created, evaluations).
    Per-symbol failures are logged and collected with rejection_reasons.
    """
    from backend.app.data.repositories.leader_event_repo import LeaderEventRepository
    from backend.app.data.repositories.price_data_repo import PriceDataRepository

    return_threshold, volume_threshold = _get_effective_thresholds()
    price_repo = PriceDataRepository(db)
    leader_repo = LeaderEventRepository(db)
    created: list[LeaderEvent] = []
    evaluations: list[dict[str, object]] = []

    for symbol in symbols:
        try:
            bars = list(price_repo.list_for_stock(symbol))
            bars_on_or_before = [b for b in bars if b.date <= event_date]
            bars_on_or_before.sort(key=lambda b: b.date)
            if len(bars_on_or_before) < MIN_BARS_FOR_LEADER:
                evaluations.append(
                    {
                        "symbol": symbol,
                        "return_pct": None,
                        "volume_ratio": None,
                        "qualified_as_leader": False,
                        "rejection_reasons": [REJECTION_INSUFFICIENT_BARS],
                    }
                )
                continue
            last_bars = bars_on_or_before[-MIN_BARS_FOR_LEADER:]
            if last_bars[-1].date != event_date:
                evaluations.append(
                    {
                        "symbol": symbol,
                        "return_pct": None,
                        "volume_ratio": None,
                        "qualified_as_leader": False,
                        "rejection_reasons": [REJECTION_NO_DATA_ON_EVENT_DATE],
                    }
                )
                continue
            prev_close = last_bars[-2].close
            curr_close = last_bars[-1].close
            curr_volume = last_bars[-1].volume
            avg_volume = sum(b.volume for b in last_bars[:-1]) / (len(last_bars) - 1)
            if avg_volume <= 0:
                evaluations.append(
                    {
                        "symbol": symbol,
                        "return_pct": None,
                        "volume_ratio": None,
                        "qualified_as_leader": False,
                        "rejection_reasons": [REJECTION_ZERO_AVG_VOLUME],
                    }
                )
                continue
            return_pct = ((curr_close - prev_close) / prev_close) * 100.0
            volume_ratio = curr_volume / avg_volume
            reasons: list[str] = []
            if abs(return_pct) < return_threshold:
                reasons.append(REJECTION_BELOW_RETURN_THRESHOLD)
            if volume_ratio < volume_threshold:
                reasons.append(REJECTION_INSUFFICIENT_VOLUME)
            if reasons:
                evaluations.append(
                    {
                        "symbol": symbol,
                        "return_pct": return_pct,
                        "volume_ratio": volume_ratio,
                        "qualified_as_leader": False,
                        "rejection_reasons": reasons,
                    }
                )
                continue
            direction = "up" if return_pct > 0 else "down"
            event = LeaderEvent(
                leader_symbol=symbol,
                event_date=event_date,
                return_pct=return_pct,
                volume_ratio=volume_ratio,
                direction=direction,
                job_run_id=run_id,
            )
            leader_repo.add(event)
            created.append(event)
            evaluations.append(
                {
                    "symbol": symbol,
                    "return_pct": return_pct,
                    "volume_ratio": volume_ratio,
                    "qualified_as_leader": True,
                    "rejection_reasons": [],
                }
            )
        except Exception as exc:
            logger.warning("Leader detection failed for %s: %s", symbol, exc)
            evaluations.append(
                {
                    "symbol": symbol,
                    "return_pct": None,
                    "volume_ratio": None,
                    "qualified_as_leader": False,
                    "rejection_reasons": [REJECTION_ERROR],
                }
            )

    return created, evaluations


def select_follower_candidates(
    leader_event: LeaderEvent,
    stock_group_repo: StockGroupRepository,
    price_repo: PriceDataRepository,
    event_date: dt.date,
) -> list[tuple[str, str]]:
    """Return (follower_symbol, group_id) for candidates that have not moved.

    Excludes leader. Excludes symbols with abs(return) >= follower_move_threshold.
    Primary group = lexicographically smallest group_id when symbol in multiple groups.
    Skips symbols with no price data (log and continue).
    """
    settings = get_settings()
    threshold = settings.follower_move_threshold_pct

    group_ids = stock_group_repo.get_groups_for_symbol(leader_event.leader_symbol)
    if not group_ids:
        return []
    primary_group = min(group_ids)

    members = stock_group_repo.get_symbols_in_group(primary_group)
    candidates: list[tuple[str, str]] = []

    for symbol in members:
        if symbol == leader_event.leader_symbol:
            continue
        try:
            bars = list(price_repo.list_for_stock(symbol))
            bars_on_date = [b for b in bars if b.date <= event_date]
            bars_on_date.sort(key=lambda b: b.date)
            if len(bars_on_date) < 2:
                continue
            last_bars = bars_on_date[-2:]
            if last_bars[-1].date != event_date:
                continue
            prev_close = last_bars[-2].close
            curr_close = last_bars[-1].close
            return_pct = ((curr_close - prev_close) / prev_close) * 100.0
            if abs(return_pct) >= threshold:
                continue
            candidates.append((symbol, primary_group))
        except Exception as exc:
            logger.warning("Follower candidate check failed for %s: %s", symbol, exc)

    return candidates


def _get_allowed_pairs_for_signals(db: "Session", event_date: dt.date) -> set[tuple[str, str]] | None:
    """When enable_pair_filtering_for_signals, return (leader, follower) pairs that pass thresholds.

    Returns None when filtering is disabled (caller allows all). Returns set (possibly empty) when enabled.
    """
    settings = get_settings()
    if getattr(settings, "enable_pair_filtering_for_signals", False) is not True:
        return None

    from backend.app.services.leader_follower_evaluation_service import (
        aggregate_by_pair,
        filter_pairs_by_thresholds,
        run_evaluation,
    )

    lookback = int(getattr(settings, "leader_follower_pair_filter_lookback_days", 90))
    since = event_date - timedelta(days=lookback)
    signals, price_by_symbol, horizons = run_evaluation(db, since_date=since, until_date=event_date, limit=2000)
    pairs = aggregate_by_pair(signals, price_by_symbol, horizons)
    passing, _ = filter_pairs_by_thresholds(
        pairs,
        settings.leader_follower_pair_min_signal_count,
        settings.leader_follower_pair_min_avg_return_1d,
        settings.leader_follower_pair_min_win_rate_1d,
    )
    return {(p["leader_symbol"], p["follower_symbol"]) for p in passing}


def compute_strength_score(
    return_pct: float,
    volume_ratio: float,
) -> float:
    """Compute strength score: w_r*norm_return + w_v*norm_volume, clamped to [0,1].

    Normalizes using config caps; values above cap map to 1.
    """
    settings = get_settings()
    w_r = settings.leader_follower_strength_weight_return
    w_v = settings.leader_follower_strength_weight_volume
    cap_r = settings.leader_follower_norm_return_cap_pct
    cap_v = settings.leader_follower_norm_volume_cap

    norm_return = min(1.0, abs(return_pct) / cap_r) if cap_r > 0 else 0.0
    norm_volume = min(1.0, volume_ratio / cap_v) if cap_v > 0 else 0.0
    score = w_r * norm_return + w_v * norm_volume
    return max(0.0, min(1.0, score))


def create_signals(
    leader_events: list[LeaderEvent],
    candidates_map: dict[int, list[tuple[str, str]]],
    signal_repo: LeaderFollowerSignalRepository,
    cooldown_days: int,
    event_date: dt.date,
    *,
    idempotent: bool = False,
) -> int | tuple[int, int]:
    """Create LeaderFollowerSignal for each (leader, candidate, group) not in cooldown.

    When idempotent=True, skips if signal exists and returns (created, skipped).
    Otherwise returns created count only.
    """
    from backend.app.models.leader_follower_signal import LeaderFollowerSignal

    created = 0
    skipped = 0
    for event in leader_events:
        candidates = candidates_map.get(event.id, [])
        for follower_symbol, group_id in candidates:
            if signal_repo.exists_within_cooldown(
                event.leader_symbol,
                follower_symbol,
                event_date,
                cooldown_days,
            ):
                continue
            if idempotent and signal_repo.exists_for(
                event.leader_symbol,
                follower_symbol,
                event_date,
            ):
                skipped += 1
                continue
            strength = compute_strength_score(event.return_pct, event.volume_ratio)
            signal = LeaderFollowerSignal(
                leader_symbol=event.leader_symbol,
                follower_symbol=follower_symbol,
                group_id=group_id,
                signal_date=event_date,
                strength_score=strength,
                leader_return_pct=event.return_pct,
                leader_volume_ratio=event.volume_ratio,
                metrics_json=None,
            )
            signal_repo.add(signal)
            created += 1
    return (created, skipped) if idempotent else created


def run_detection(db: Session, run_id: int | None = None) -> dict[str, object]:
    """Run full leader-follower detection pipeline. Returns metrics dict."""
    from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.stock_group_repo import StockGroupRepository
    from backend.app.data.repositories.stock_repo import StockRepository

    settings = get_settings()
    stock_repo = StockRepository(db)
    price_repo = PriceDataRepository(db)
    stock_group_repo = StockGroupRepository(db)
    signal_repo = LeaderFollowerSignalRepository(db)

    grouped_symbols = stock_group_repo.get_all_symbols()
    grouped_leader_universe_size = len(grouped_symbols)

    if not grouped_symbols:
        universe_size = len(stock_repo.list())
        return {
            "input_universe_size": universe_size,
            "grouped_leader_universe_size": 0,
            "leader_events_detected": 0,
            "follower_candidates_found": 0,
            "signals_emitted": 0,
            "symbols_skipped": 0,
            "errors_count": 0,
        }

    event_date = compute_event_date(price_repo, stock_repo)
    if event_date is None:
        universe_size = len(stock_repo.list())
        return {
            "input_universe_size": universe_size,
            "grouped_leader_universe_size": grouped_leader_universe_size,
            "leader_events_detected": 0,
            "follower_candidates_found": 0,
            "signals_emitted": 0,
            "symbols_skipped": 0,
            "errors_count": 0,
        }

    universe_size = len(stock_repo.list())
    leader_events, evaluations = detect_leaders(db, event_date, grouped_symbols, run_id=run_id)

    # Persist evaluations and compute near_miss_count when run_id is set
    near_miss_count = 0
    if run_id is not None:
        from backend.app.data.repositories.leader_debug_repo import LeaderDebugRepository
        from backend.app.models.leader_debug_evaluation import LeaderDebugEvaluation

        debug_repo = LeaderDebugRepository(db)
        return_threshold, volume_threshold = _get_effective_thresholds()
        for ev in evaluations:
            return_pct = ev.get("return_pct")
            volume_ratio = ev.get("volume_ratio")
            if return_pct is not None and volume_ratio is not None and not ev.get("qualified_as_leader"):
                near_miss_count += 1
            rec = LeaderDebugEvaluation(
                job_run_id=run_id,
                stock_symbol=str(ev["symbol"]),
                return_pct=return_pct,
                volume_ratio=volume_ratio,
                qualified_as_leader=bool(ev.get("qualified_as_leader", False)),
                rejection_reasons=json.dumps(ev.get("rejection_reasons", [])),
                metrics_json=json.dumps(
                    {
                        "return_threshold": return_threshold,
                        "volume_threshold": volume_threshold,
                    }
                ),
            )
            debug_repo.add(rec)

    allowed_pairs = _get_allowed_pairs_for_signals(db, event_date)
    candidates_map: dict[int, list[tuple[str, str]]] = {}
    total_candidates = 0
    candidate_repo = None
    if run_id is not None:
        from backend.app.data.repositories.leader_follower_candidate_repo import (
            LeaderFollowerCandidateRepository,
        )
        from backend.app.models.leader_follower_candidate import LeaderFollowerCandidate

        candidate_repo = LeaderFollowerCandidateRepository(db)

    for event in leader_events:
        candidates = select_follower_candidates(event, stock_group_repo, price_repo, event_date)
        if allowed_pairs is not None:
            candidates = [
                (follower_symbol, group_id)
                for follower_symbol, group_id in candidates
                if (event.leader_symbol, follower_symbol) in allowed_pairs
            ]
        candidates_map[event.id] = candidates
        total_candidates += len(candidates)

        if candidate_repo is not None and run_id is not None:
            for follower_symbol, group_id in candidates:
                c = LeaderFollowerCandidate(
                    job_run_id=run_id,
                    event_date=event_date,
                    leader_symbol=event.leader_symbol,
                    follower_symbol=follower_symbol,
                    group_id=group_id,
                    metrics_json=None,
                )
                candidate_repo.add(c)

    signals_emitted = create_signals(
        leader_events,
        candidates_map,
        signal_repo,
        settings.leader_follower_cooldown_days,
        event_date,
    )

    metrics: dict[str, object] = {
        "input_universe_size": universe_size,
        "grouped_leader_universe_size": grouped_leader_universe_size,
        "leader_events_detected": len(leader_events),
        "follower_candidates_found": total_candidates,
        "signals_emitted": signals_emitted,
        "symbols_skipped": 0,
        "errors_count": 0,
    }
    if run_id is not None:
        metrics["near_miss_count"] = near_miss_count
    if settings.leader_follower_debug_mode:
        metrics["debug_mode"] = True
    metrics["event_date"] = event_date.isoformat()
    return metrics


def run_detection_for_date(
    db: Session,
    event_date: dt.date,
    run_id: int | None = None,
    *,
    idempotent: bool = False,
) -> dict[str, object]:
    """Run leader-follower detection for a specific event_date. For replay/backfill.

    Uses event_date explicitly (skips compute_event_date). When idempotent=True,
    create_signals skips existing signals and returns (created, skipped).
    """
    from backend.app.data.repositories.leader_follower_signal_repo import LeaderFollowerSignalRepository
    from backend.app.data.repositories.price_data_repo import PriceDataRepository
    from backend.app.data.repositories.stock_group_repo import StockGroupRepository
    from backend.app.data.repositories.stock_repo import StockRepository

    settings = get_settings()
    stock_repo = StockRepository(db)
    price_repo = PriceDataRepository(db)
    stock_group_repo = StockGroupRepository(db)
    signal_repo = LeaderFollowerSignalRepository(db)

    grouped_symbols = stock_group_repo.get_all_symbols()
    if not grouped_symbols:
        return {
            "input_universe_size": len(stock_repo.list()),
            "grouped_leader_universe_size": 0,
            "leader_events_detected": 0,
            "follower_candidates_found": 0,
            "signals_emitted": 0,
            "signals_skipped_duplicate": 0,
            "event_date": event_date.isoformat(),
        }

    leader_events, _ = detect_leaders(db, event_date, grouped_symbols, run_id=run_id)
    allowed_pairs = _get_allowed_pairs_for_signals(db, event_date)
    candidates_map: dict[int, list[tuple[str, str]]] = {}
    total_candidates = 0
    for event in leader_events:
        candidates = select_follower_candidates(event, stock_group_repo, price_repo, event_date)
        if allowed_pairs is not None:
            candidates = [
                (follower_symbol, group_id)
                for follower_symbol, group_id in candidates
                if (event.leader_symbol, follower_symbol) in allowed_pairs
            ]
        candidates_map[event.id] = candidates
        total_candidates += len(candidates)

    result = create_signals(
        leader_events,
        candidates_map,
        signal_repo,
        settings.leader_follower_cooldown_days,
        event_date,
        idempotent=idempotent,
    )
    if isinstance(result, tuple):
        signals_emitted, signals_skipped = result
    else:
        signals_emitted = result
        signals_skipped = 0

    return {
        "input_universe_size": len(stock_repo.list()),
        "grouped_leader_universe_size": len(grouped_symbols),
        "leader_events_detected": len(leader_events),
        "follower_candidates_found": total_candidates,
        "signals_emitted": signals_emitted,
        "signals_skipped_duplicate": signals_skipped,
        "event_date": event_date.isoformat(),
    }


def load_symbol_to_primary_group_map(
    stock_group_repo: StockGroupRepository,
) -> dict[str, str]:
    """Build symbol -> primary_group_id map.

    For symbols in multiple groups, primary group = lexicographically smallest group_id.
    Returns only symbols that have at least one group.
    """
    pairs = stock_group_repo.get_all_symbol_group_pairs()
    all_groups: dict[str, list[str]] = {}
    for symbol, group_id in pairs:
        if symbol not in all_groups:
            all_groups[symbol] = []
        all_groups[symbol].append(group_id)

    result: dict[str, str] = {}
    for symbol, group_ids in all_groups.items():
        if group_ids:
            result[symbol] = min(group_ids)
    return result
