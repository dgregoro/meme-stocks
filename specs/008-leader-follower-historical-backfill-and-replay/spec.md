# Feature Specification: Leader-Follower Historical Backfill and Replay

**Feature Name**: leader-follower-historical-backfill-and-replay
**Feature ID**: 008
**Created**: 2026-03-23
**Status**: Draft
**Input**: Replay leader-follower detection across historical dates using Alpaca market data to generate historical signals and accelerate evaluation.

---

## Problem Statement

- Current leader-follower evaluation has too few signals and too little historical depth to judge usefulness.
- Live accumulation (one event date per day) is too slow.
- We need a way to replay historical dates and generate historical signals using the same detection logic.
- The repo already has an Alpaca integration (minute bars for intraday; Alpaca API also supports daily bars) and a Yahoo/PriceData pipeline used by live leader-follower. We can leverage Alpaca for historical daily bars to avoid depending solely on live Yahoo accumulation.

---

## Goals

- Replay leader-follower detection across a historical date range.
- Use only data available as of each replay date (no lookahead).
- Generate historical signals with valid historical `signal_date` values.
- Make those signals immediately usable by existing evaluation endpoints.
- Keep the replay practical, incremental, and consistent with existing repo patterns.

---

## Non-Goals

- No full portfolio backtest engine.
- No intraday trade execution simulation.
- No transaction cost model.
- No live trading integration changes.
- No strategy redesign.

---

## User Stories

### User Story 1: Backfill a historical date range

As a developer or researcher,
I want to replay leader-follower detection for a historical date range,
so that I can generate older signals and evaluate them immediately.

**Acceptance criteria:**

- A backfill command/job supports:
  - `start_date`
  - `end_date`
  - optional `dry_run`
  - optional `persist`
- Replay processes dates sequentially (chronological order).
- Summary includes:
  - days processed
  - leaders detected
  - candidates found
  - signals emitted

---

### User Story 2: Avoid obvious lookahead bias

As a developer or researcher,
I want replay to use only data available up to each historical date,
so that evaluation results are not contaminated by future information.

**Acceptance criteria:**

- Leader detection for a replay date uses only historical bars up to that date.
- Follower candidate logic uses only data available at that date.
- The spec explicitly defines the bar/time assumptions used for replay.

**Bar/time assumptions:**

- For replay date D, leader detection uses: `list_for_stock(symbol)` filtered to `date <= D`, with at least `MIN_BARS_FOR_LEADER` (5) bars ending on D. This matches current `detect_leaders` behavior.
- Follower candidate logic uses: bars for each candidate with `date <= D`, last two bars ending on D for return check. Matches current `select_follower_candidates`.
- No bar with `date > D` is ever used when processing date D. Current service logic already filters with `bars_on_or_before` and `bars_on_date`; replay must ensure PriceData for the replay range does not inadvertently include future bars when running for D, or the existing filters are sufficient (they are, as long as we process chronologically and do not mix dates).
- Historical data backfill: when backfilling PriceData for symbols over [start_date, end_date], we insert bars in chronological order. When we run detection for date D, we have bars up to at least D. Having bars for D+1, D+2, etc. in the DB is fine because `detect_leaders` and `select_follower_candidates` filter to `<= event_date`. The critical rule: **do not use any computed value (e.g. forward return, future close) that depends on a bar with date > D when processing D.**

---

### User Story 3: Reuse existing evaluation APIs

As a developer or researcher,
I want historical replay signals to work with the existing evaluation endpoints,
so that I do not need a separate evaluation pipeline.

**Acceptance criteria:**

- Backfilled signals are persisted in a format compatible with current evaluation endpoints.
- Evaluation APIs can include replay-generated signals in normal summaries.
- No schema change to `LeaderFollowerSignal` required for compatibility; evaluation reads `leader_symbol`, `follower_symbol`, `signal_date` etc., which are identical for live and replay signals.

---

### User Story 4: Control persistence and reruns

As a developer or researcher,
I want replay to be safe to rerun,
so that I can backfill incrementally without creating uncontrolled duplicates.

**Acceptance criteria:**

- Replay supports idempotent or clearly bounded persistence behavior.
- The spec defines how duplicate historical signals are prevented or handled.
- Existing cooldown or duplicate logic is applied in a historically coherent way.

**Duplicate prevention:**

- Before inserting a signal for (leader, follower, signal_date), check if one already exists. If so, skip (idempotent).
- Cooldown: when processing date D, `exists_within_cooldown(leader, follower, D, cooldown_days)` checks for signals with `signal_date >= D - cooldown_days`. During replay we process chronologically and persist before moving to the next date, so cooldown state is correct. For dry-run, maintain an in-memory structure (e.g. last_signal_date per (leader, follower)) to simulate cooldown across dates.

**Optional replace mode:**

- If `--replace-range` or similar is provided: delete existing signals in [start_date, end_date] before replay, then run. Use with care. Default: idempotent (no replace).

---

### User Story 5: Understand replay progress and failures

As a developer or operator,
I want replay runs to expose progress, warnings, and failures,
so that I can trust the backfill process.

**Acceptance criteria:**

- Replay emits structured progress or summary output.
- Missing bars, skipped dates, and API failures are visible.
- Failures do not silently corrupt results.

---

## Functional Requirements

### 1. Historical date range replay

- Support replay over a configurable date range [start_date, end_date].
- Dates processed in chronological order.
- Replay respects trading-day availability: skip dates that are weekends/holidays if no price data exists, or process only dates where we have data for the universe.

### 2. Historical data access via Alpaca

- Use the existing Alpaca integration to fetch historical daily bars.
- Alpaca `v2/stocks/bars` supports `timeframe=1Day`; current `AlpacaDataClient.fetch_bars_page` accepts `timeframe` (default `1Min`). Add a wrapper or use `timeframe="1Day"` to fetch daily OHLCV for symbols over a date range.
- Map Alpaca daily bar response (open, high, low, close, volume, timestamp) to `PriceData` / `PriceBar` format and persist.
- Paging: Alpaca returns paginated results; handle `next_page_token` when fetching large ranges.
- For historical requests (end date in the past), `_effective_end` clamping to "now - safety" does not restrict; past end dates pass through.
- Do not assume unlimited historical access; document Alpaca plan limits if known (e.g. free plan historical depth).

### 3. Replay-time leader detection

- For each replay date D, run leader detection using the grouped leader universe and only bars with `date <= D`.
- Current `detect_leaders(db, event_date, symbols, run_id)` already filters to `bars_on_or_before`. Replay needs a variant: `run_detection_for_date(db, event_date, run_id)` or equivalent that uses `event_date` instead of `compute_event_date()`. The latter returns max(price_data.date), which for replay we override with the target date D.

### 4. Replay-time follower candidate generation and signal emission

- For each replay date, apply current `select_follower_candidates` and `create_signals`.
- Cooldown: `exists_within_cooldown` checks the `leader_follower_signals` table. During persist-mode replay, we insert signals as we go, so cooldown is correct. For dry-run, pass an in-memory cooldown structure or a temporary "replay signal buffer" that `create_signals` can consult.

### 5. Persistence model

- Historical replay signals are persisted as `LeaderFollowerSignal` rows. Same model, same evaluation compatibility.
- Optional: store `metrics_json` with `{"source": "replay"}` or `{"replay_run_id": "..."}` for traceability. Low priority for MVP.
- No new tables required for MVP. If replay batches need to be replaceable later, a `source` or `replay_run_id` column could be added; defer until justified.

### 6. Dry-run vs persist mode

- **Dry-run**: Compute summary counts (days processed, leaders, candidates, signals) without persisting to DB. Use in-memory cooldown across dates.
- **Persist**: Write historical signals to `leader_follower_signals`. Idempotent: skip if (leader, follower, signal_date) exists.

### 7. Replay observability

- Summary output includes:
  - `days_processed`
  - `days_skipped` (e.g. no data, weekend)
  - `leaders_detected` (total)
  - `candidates_found` (total)
  - `signals_emitted` (total)
  - `signals_skipped_duplicate` (idempotent skips)
  - `missing_data_warnings` (dates or symbols with insufficient bars)
  - `errors` (e.g. Alpaca fetch failures)
- Log at INFO: each date started/completed; at WARNING: skipped date, missing bars; at ERROR: API failure.

### 8. Brownfield compatibility

- Reuse `LeaderFollowerSignalRepository`, `PriceDataRepository`, `leader_follower_service.detect_leaders`, `select_follower_candidates`, `create_signals`.
- Extract or add `run_detection_for_date(db, event_date, run_id)` that bypasses `compute_event_date` and uses the given date.
- Add a replay/backfill module (e.g. `leader_follower_replay_service.py` or `backfill_service.py`) that orchestrates: data backfill → per-date detection → summary.
- Keep implementation minimal; no separate replay framework.

---

## Data Requirements

- **Existing Alpaca integration**: `AlpacaDataClient`; extend usage to `timeframe="1Day"` for historical daily bars.
- **PriceData**: Populate with Alpaca daily bars for replay symbols and date range. Existing schema.
- **Stock groups**: `stock_groups` for grouped leader universe (unchanged).
- **LeaderFollowerSignal**: Persist replay signals; evaluation APIs already consume this.

---

## Risks / Tradeoffs

| Risk | Mitigation |
|------|-------------|
| Lookahead bias | Strict filter: only bars with `date <= replay_date`. Document in spec. |
| Duplicate or inconsistent cooldown during replay | Process chronologically; persist before next date; idempotent insert. |
| Alpaca rate limits / paging / entitlement | Use existing retry; handle paging; document plan limits. |
| Large date ranges slow | Process in batches; log progress; allow resumability later. |
| Missing historical bars | Skip date or symbol; log warning; do not fabricate. |

---

## Brownfield Constraints

- Prefer minimal extensions to the current pipeline.
- Avoid major schema redesign.
- Avoid full backtester scope creep.
- Keep MVP daily/coarse enough to be reliable and understandable.

---

## Open Questions

1. **Daily bars only for MVP?**
   Live detection uses `PriceData` (daily OHLCV from Yahoo). Alpaca can provide 1Day bars. Recommendation: **yes, daily bars only for MVP**. Matches current leader logic exactly.

2. **Cooldown across replayed dates?**
   Apply same cooldown as live: when processing D, check for existing signals (leader, follower) with `signal_date >= D - cooldown_days`. For persist mode, existing `exists_within_cooldown` works. For dry-run, maintain in-memory `{(leader, follower): last_signal_date}`.

3. **Tag replay signals separately?**
   Optional `metrics_json` or future `source` column. Recommendation: **defer**. Evaluation treats all signals alike; tagging can be added later if needed for filtering.

4. **CLI-only vs API-triggerable?**
   See Appendix recommendation.

---

## Existing Repo Context

### Leader-follower pipeline

- `run_detection(db, run_id)` in `leader_follower_service.py`
- Uses `compute_event_date(price_repo, stock_repo)` → max(price_data.date)
- `detect_leaders(db, event_date, symbols)` uses `price_repo.list_for_stock(symbol)` filtered to `date <= event_date`
- `select_follower_candidates` and `create_signals` same pattern
- Needs: `run_detection_for_date(db, event_date, run_id)` that skips `compute_event_date` and uses passed `event_date`

### Alpaca client

- `backend/app/clients/alpaca_data_client.py`
- `fetch_bars_page(symbols, start, end, timeframe="1Min", ...)` — supports timeframe param
- Alpaca API: `timeframe` can be `1Min`, `1Hour`, `1Day`
- For historical: end in past → no safe-end clamping issue

### Price data flow

- Live: `SchedulerService._collect_price_data` → Yahoo → `PriceData`
- Replay: new path — Alpaca daily bars → `PriceData` (for replay symbols/range)

### Evaluation

- `LeaderFollowerEvaluationService` and `/api/leader-follower/evaluation/*` read `LeaderFollowerSignal` — no changes needed for replay signals

---

## Appendix: Implementation Guidance

### Recommended MVP Implementation Approach

1. **Alpaca daily bar fetch**
   Add `fetch_daily_bars` or use `fetch_bars_page(..., timeframe="1Day")` in a small service that maps Alpaca response → PriceData rows. Batch symbols and handle paging. Write to PriceData for symbols in the grouped universe over the requested range.

2. **Replay orchestration**
   Create `leader_follower_replay_service.py` with `run_backfill(start_date, end_date, dry_run, persist)`. For each trading day D in range:
   - Ensure PriceData exists for needed symbols up to D (call backfill for [D - lookback, D] if any missing)
   - Call `run_detection_for_date(db, D, run_id)` (new helper)
   - In dry-run: collect metrics only; maintain in-memory cooldown
   - In persist: write signals (idempotent check); cooldown via DB
   - Accumulate summary counts

3. **Extract run_detection_for_date**
   Factor from `run_detection`: a variant that takes `event_date` explicitly and skips `compute_event_date`. Reuse `detect_leaders`, `select_follower_candidates`, `create_signals`.

4. **CLI command**
   Add `python -m backend.app.cli backfill leader-follower --start YYYY-MM-DD --end YYYY-MM-DD [--dry-run]` that invokes the replay service.

### Likely Files / Modules Affected

| Path | Change |
|------|--------|
| `backend/app/clients/alpaca_data_client.py` | Use `timeframe="1Day"`; possibly add `fetch_daily_bars_for_range` helper |
| `backend/app/services/leader_follower_replay_service.py` | **New** — backfill PriceData from Alpaca, orchestrate replay |
| `backend/app/services/leader_follower_service.py` | Add `run_detection_for_date(db, event_date, run_id)` |
| `backend/app/cli.py` | Add `backfill leader-follower` command |
| `backend/tests/test_leader_follower_replay_service.py` | **New** — unit/integration tests |
| `backend/app/data/repositories/leader_follower_signal_repo.py` | Optional: `exists_for(leader, follower, signal_date)` for idempotency |

### Top 3 Implementation Mistakes to Avoid

1. **Lookahead when backfilling**
   When pre-loading PriceData for [start, end], it is safe to insert all bars. Detection filters to `<= event_date`. The mistake: using any future bar in a computation (e.g. accidentally using "next day close" in a condition). The current logic does not; keep it that way.

2. **Cooldown in dry-run**
   Dry-run does not persist signals, so `exists_within_cooldown` would see nothing. You must maintain an in-memory cooldown state (e.g. `{(leader, follower): last_signal_date}`) and pass it through the dry-run loop, or simulate `create_signals` with a mock that tracks what *would* have been emitted.

3. **Over-fetching or blocking on Alpaca**
   Fetch in reasonable batches (e.g. 50 symbols, 1 month per request). Use paging. Do not block the entire replay on one failed symbol; log and skip, continue with others.

### Recommendation: CLI-Only First vs API-Triggerable

**Recommendation: CLI-only for MVP.**

- **Rationale:** Replay is a batch operation that can take minutes to hours. Fits CLI better than a synchronous API call. API would need async/job semantics to avoid timeouts.
- **CLI:** `python -m backend.app.cli backfill leader-follower --start ... --end ...` — simple, scriptable, no timeout risk.
- **API later:** If needed, add `POST /api/jobs/leader-follower-backfill` that enqueues a background job or spawns a subprocess. Defer until CLI is proven useful.
