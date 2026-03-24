# Research: Leader-Follower Historical Backfill

**Feature**: 008-leader-follower-historical-backfill-and-replay
**Date**: 2026-03-23

## 1. Alpaca Daily Bars

**Decision**: Use Alpaca `fetch_bars_page` with `timeframe="1Day"` for historical daily OHLCV.

**Rationale**:
- Alpaca API v2 supports `timeframe`: 1Min, 1Hour, 1Day.
- Current `AlpacaDataClient.fetch_bars_page` accepts `timeframe` (default 1Min); pass "1Day".
- For historical requests (end date in past), `_effective_end` returns the past end — no safe-end clamping.
- Daily bars map directly to PriceData schema (date, open, high, low, close, volume).

**Alternatives considered**:
- Yahoo historical: Simpler (already have fetch_historical_prices) but spec requires Alpaca.
- Minute bars aggregated to daily: Overkill; Alpaca supports 1Day natively.

---

## 2. Historical End-Time Clamping

**Decision**: For requests where `end < now - safety`, do not clamp. Alpaca client's `_effective_end` uses `min(end, safe_end)`. When end is in the past, end < safe_end, so no clamping.

**Rationale**: Verified in client code: `return min(end, safe)` — past end passes through.

**Alternatives considered**: Add explicit "historical mode" bypass — unnecessary; current behavior correct.

---

## 3. Data Backfill Strategy

**Decision**: Pre-fill PriceData for entire [start_date, end_date] range (with lookback) before replay loop. Then run detection per date. Detection logic filters to `<= event_date`; having future bars in DB is safe.

**Rationale**:
- Simpler: one data pass, then N detection passes.
- Avoids per-date Alpaca calls (would hit rate limits).
- Spec confirms: "Having bars for D+1, D+2 in DB is fine because detect_leaders filters to <= event_date."

**Alternatives considered**:
- Incremental backfill per date: More API calls; slower; same outcome.

---

## 4. Dry-Run Cooldown

**Decision**: Maintain in-memory `dict[(leader, follower), date]` for last signal date. Pass to a variant of `create_signals` or simulate in replay loop: when emitting (dry-run), update dict; when checking cooldown, consult dict instead of DB.

**Rationale**: Spec: "For dry-run, maintain in-memory cooldown state." `exists_within_cooldown` hits DB; dry-run does not persist, so we need equivalent logic in memory.

**Alternatives considered**:
- Persist to temp table then rollback: Heavy; not needed.

---

## 5. Idempotency Check

**Decision**: Add `LeaderFollowerSignalRepository.exists_for(leader, follower, signal_date) -> bool`. Before insert in persist mode, check; skip if exists.

**Rationale**: Spec requires idempotent behavior for safe reruns. Simple existence check is sufficient.

**Alternatives considered**:
- Unique constraint + catch integrity error: Less explicit; harder to report "skipped" count.
