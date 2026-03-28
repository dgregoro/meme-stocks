# Feature Specification: Leader-Follower Signal Evaluation and Review

**Feature Name**: leader-follower-signal-evaluation-and-review
**Feature ID**: 007
**Created**: 2026-03-22
**Status**: Draft
**Input**: Evaluate emitted leader-follower signals to determine whether they have predictive value and which relationships are strongest or weakest.

---

## Problem Statement

The system can emit leader-follower signals, but there is not yet a structured way to evaluate whether those signals are useful. Without evaluation, we cannot tell whether:

- Signals have positive forward returns
- Certain leader/follower pairs are better than others
- Cooldown and duplicate behavior are helping or hurting

We need a minimal, inspectable evaluation layer before adding more complexity.

---

## Goals

- Measure signal performance over forward time windows
- Summarize signal frequency and quality
- Identify strongest and weakest leader/follower pairs
- Quantify duplicate/overlap behavior
- Provide outputs that support both debugging and research

---

## Non-Goals

- No claim of production trading readiness
- No full backtesting engine
- No advanced transaction cost model
- No optimization of thresholds in this feature
- No expansion into new strategies

---

## User Stories

### User Story 1: View summary performance

As a developer or researcher,
I want to view summary metrics for leader-follower signals,
so that I can tell whether the feature is producing potentially useful signals.

**Acceptance criteria:**

- API or report returns:
  - Total signal count
  - Signals per day
  - Win rate at 1d / 3d / 5d
  - Average forward return at 1d / 3d / 5d
  - Median forward return if practical
- Metrics are based on actual emitted signals and available price data

---

### User Story 2: Evaluate by leader/follower pair

As a developer or researcher,
I want to see results grouped by leader/follower pair,
so that I can identify which relationships look promising and which look weak.

**Acceptance criteria:**

- Results can be grouped by:
  - Leader symbol
  - Follower symbol
  - Leader/follower pair
- For each pair, provide:
  - Signal count
  - Win rate
  - Average forward return
  - Sample size visibility

---

### User Story 3: Review best and worst pairs

As a developer or researcher,
I want to inspect top-performing and worst-performing pairs,
so that I can decide what relationships to trust, prune, or investigate further.

**Acceptance criteria:**

- API or report can return top/bottom pairs by chosen metric
- Includes minimum sample size protection or clearly exposes sample size
- Does not hide small-sample caveats

---

### User Story 4: Understand duplicate and overlap behavior

As a developer or researcher,
I want to quantify duplicate or overlapping signals,
so that I can understand whether repeated alerts are inflating counts or reducing usefulness.

**Acceptance criteria:**

- Evaluation includes:
  - Duplicate/overlap count
  - Repeated signals for same leader/follower pair within a defined window
  - Visibility into cooldown effects where practical

---

### User Story 5: Review individual signal outcomes

As a developer or researcher,
I want to inspect individual signals with realized forward outcomes,
so that I can manually sanity-check the evaluation logic.

**Acceptance criteria:**

- API can return signal-level rows including:
  - `run_id` (or equivalent run reference)
  - Signal timestamp
  - Leader symbol
  - Follower symbol
  - Entry/reference price
  - Forward returns at evaluation horizons
  - Outcome flags (win/loss by horizon)

---

## Functional Requirements

### 1. Evaluation horizons

- Support at least:
  - 1 trading day
  - 3 trading days
  - 5 trading days
- Be explicit about how horizons are computed from signal timestamps and available price bars
- Use **trading days** (sessions), not calendar days, for consistency with `label_service` and `PriceLabel`
- Reference: `LeaderFollowerSignal.signal_date` is the event date; forward return is from close on signal_date to close on target trading session(s) later

### 2. Signal-level outcome computation

- For each emitted signal, compute:
  - **Reference/entry price**: Follower close on `signal_date` (or nearest prior trading day if missing)
  - **Forward price**: Follower close at each horizon
  - **Forward return**: `close[target] / close[reference] - 1` per horizon
- Handle missing price data explicitly: return `null`/omit; do not fail silently
- Signal targets the **follower** symbol (the candidate to potentially move after the leader)
- Reuse `PriceDataRepository` and trading-day logic similar to `label_service.compute_and_store_forward_returns`

### 3. Summary metrics

- Provide summary metrics including:
  - Total signal count
  - Signals per day
  - Win rate by horizon (proportion where forward return > 0)
  - Average forward return by horizon
  - Optional median return if easy to compute and useful

### 4. Pair-level metrics

- Aggregate by (leader_symbol, follower_symbol) pair
- Include:
  - Sample count
  - Win rate
  - Average forward return
  - Best/worst ranking support

### 5. Duplicate / overlap analysis

- Define what counts as a duplicate or overlapping signal:
  - Same (leader, follower) pair within a configurable window (e.g., N trading days)
  - Cooldown currently suppresses repeats; emitted signals are post-cooldown
- Quantify:
  - Repeated same-pair signals inside a chosen window (e.g., 5 or 10 days)
  - Proportion of signals that are "repeat" vs "first" for that pair in window
- Keep this practical and minimal
- Optional: Surface cooldown-suppressed counts from `LeaderFollowerCandidate` if available and useful

### 6. Review APIs

Define read-only endpoints under `/api/leader-follower/evaluation/`:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/leader-follower/evaluation/summary` | Aggregate metrics (counts, win rate, avg return by horizon) |
| `GET /api/leader-follower/evaluation/pairs` | Pair-level aggregates with filters |
| `GET /api/leader-follower/evaluation/signals` | Signal-level rows with outcomes |
| `GET /api/leader-follower/evaluation/top-pairs` | Top N pairs by chosen metric |
| `GET /api/leader-follower/evaluation/bottom-pairs` | Bottom N pairs by chosen metric |

**Query parameters (common):**

- `since_date`, `until_date` — filter signals by `signal_date`
- `leader` — filter by leader symbol
- `follower` — filter by follower symbol
- `limit` — max items to return (with sensible default)
- `min_sample` — minimum sample size for pair-level metrics (e.g., 2 or 3)

**Response shape (summary):**

```json
{
  "total_signals": 42,
  "signals_per_day": 2.1,
  "date_range": {"since": "2026-03-01", "until": "2026-03-22"},
  "by_horizon": {
    "1d": {"win_rate": 0.55, "avg_return_pct": 0.3, "median_return_pct": 0.1, "evaluable_count": 40},
    "3d": {"win_rate": 0.52, "avg_return_pct": -0.2, "median_return_pct": 0.0, "evaluable_count": 35},
    "5d": {"win_rate": 0.48, "avg_return_pct": -0.5, "median_return_pct": -0.1, "evaluable_count": 30}
  },
  "duplicate_overlap": {"repeat_pair_in_window": 3, "window_days": 5}
}
```

**Response shape (pairs):**

```json
{
  "pairs": [
    {
      "leader_symbol": "INTC",
      "follower_symbol": "QCOM",
      "signal_count": 7,
      "1d": {"win_rate": 0.57, "avg_return_pct": 0.4},
      "3d": {"win_rate": 0.43, "avg_return_pct": -0.3},
      "5d": {"win_rate": 0.43, "avg_return_pct": -0.6}
    }
  ]
}
```

**Response shape (signals):**

```json
{
  "signals": [
    {
      "id": 7,
      "signal_date": "2026-03-20",
      "created_at": "2026-03-22T21:32:39Z",
      "leader_symbol": "INTC",
      "follower_symbol": "QCOM",
      "entry_price": 245.50,
      "1d": {"forward_return_pct": 0.2, "win": true},
      "3d": {"forward_return_pct": -0.5, "win": false},
      "5d": {"forward_return_pct": null, "win": null}
    }
  ]
}
```

**Empty-state behavior:**

- Summary: return zeros and empty by_horizon when no signals
- Pairs: return empty list
- Signals: return empty list
- Top/bottom pairs: return empty list when no pairs meet min_sample

### 7. Time range support

- Support evaluating a configurable time range
- Minimal filters: `since_date`, `until_date`, `leader`, `follower`
- Horizon selection: all horizons computed by default; optional `horizons=1,3,5` query param if we want to reduce computation

### 8. Brownfield compatibility

- Reuse existing stored signals (`LeaderFollowerSignal`)
- Compute evaluation from `LeaderFollowerSignal` + `PriceData` (follower symbol)
- Use existing `PriceDataRepository`, `LeaderFollowerSignalRepository`
- No new tables required for MVP unless persistence is explicitly chosen
- Follow `backend/app/api/leader_follower.py` patterns for new routes
- Register evaluation router under leader-follower prefix

---

## Data Requirements

- **Existing emitted signals**: `LeaderFollowerSignal` (leader_symbol, follower_symbol, signal_date, etc.)
- **Price data**: `PriceData` for follower symbols to compute forward returns
- **Run metadata**: `JobRunHistory` / run_id if linked (signals do not currently store run_id; `created_at` and `signal_date` are available)
- **Optional**: `LeaderFollowerCandidate` for cooldown/overlap context only if useful and low cost

---

## Risks / Tradeoffs

- **Small sample size** can make results misleading — always expose sample count
- **Missing future price data** can bias results if not handled explicitly — exclude or null such signals
- **Average return alone** may hide unstable behavior — median and win rate help
- **Overlap analysis** can become overcomplicated — keep minimal (e.g., count same-pair signals within 5-day window)

---

## Brownfield Constraints

- Keep this practical and incremental
- Prefer read-only APIs and lightweight aggregation
- Avoid major schema redesign unless clearly necessary
- Do not build a full backtesting engine
- Make assumptions explicit (e.g., close-to-close, trading days)

---

## Open Questions

1. **Price reference**: Should forward returns use close-to-close daily bars or nearest available bar? *Recommendation: close-to-close on trading days, consistent with label_service.*

2. **Exclusion window**: Should evaluation exclude signals that do not yet have a full 5-day outcome window? *Recommendation: yes; expose `evaluable_count` per horizon so caller sees how many signals had outcomes.*

3. **Minimum sample for rankings**: Should pair rankings require a minimum sample count? *Recommendation: yes; default `min_sample=2` or 3; expose in response.*

4. **Cooldown visibility**: Should cooldown-suppressed opportunities be visible separately, or only emitted signals? *Recommendation: out of scope for MVP; only evaluate emitted signals.*

---

## Existing Repo Context

### Models

- `LeaderFollowerSignal`: id, leader_symbol, follower_symbol, group_id, signal_date, strength_score, leader_return_pct, leader_volume_ratio, created_at
- `PriceData`: stock_symbol, date, open, high, low, close, volume
- `PriceLabel`: symbol, trading_day, horizon_days, fwd_return (precomputed labels; can reuse logic, not necessarily the table)

### Repositories

- `LeaderFollowerSignalRepository`: `list_signals(limit, since_date, leader, group)` — needs `follower` filter for evaluation
- `PriceDataRepository`: `list_for_stock`, `get_for_date`, `list_in_date_range`
- `LabelService`: trading-day forward return computation pattern

### API

- `router` prefix: `/api/leader-follower`
- Patterns: Query params, Pydantic response models, `get_session` dependency

---

## Appendix: Implementation Guidance

### Recommended MVP Implementation Approach

1. **Evaluation service first**
   Create `backend/app/services/leader_follower_evaluation_service.py` with pure functions:
   - `compute_forward_return(symbol, ref_date, horizon_days, price_repo)` → float | None
   - `evaluate_signal(signal, price_repo, horizons)` → dict with entry_price, horizon outcomes
   - `aggregate_summary(signals, price_repo, horizons)` → summary dict
   - `aggregate_by_pair(signals, price_repo, horizons)` → list of pair dicts
   - Reuse trading-day logic from `label_service` (sorted dates, index-based target lookup)

2. **API layer second**
   Add evaluation router or extend `leader_follower.py`:
   - Load signals via `LeaderFollowerSignalRepository` with extended filters (follower, since_date, until_date)
   - Call evaluation service
   - Return structured responses

3. **Duplicate/overlap last**
   Simple pass: for each signal, count how many other signals exist for same (leader, follower) within a sliding window (e.g., 5 trading days). Add to summary.

### Likely Files / Modules Affected

| Path | Change |
|------|--------|
| `backend/app/services/leader_follower_evaluation_service.py` | New — evaluation logic |
| `backend/app/api/leader_follower.py` | Add evaluation routes (or new router) |
| `backend/app/data/repositories/leader_follower_signal_repo.py` | Add `follower` filter to `list_signals` if missing |
| `backend/app/main.py` | Register evaluation router if separate |
| `backend/tests/test_leader_follower_evaluation_service.py` | New — unit tests |
| `backend/tests/test_leader_follower_api.py` | Add evaluation endpoint tests |

### Top 3 Implementation Mistakes to Avoid

1. **Failing silently on missing price data**
   Do not assume price bars exist. Return `null` for forward return when follower has no close on target date; track `evaluable_count` separately from total signal count so callers see the difference.

2. **Mixing calendar days and trading days**
   Forward horizons must use trading sessions (actual PriceData dates), not `date + timedelta(days=N)`. Reuse the pattern from `label_service`: sorted dates per symbol, index-based lookup for h-th next session.

3. **Over-engineering overlap analysis**
   Keep duplicate/overlap minimal: a simple count of same-pair signals within a window. Do not build a full cooldown simulator or try to attribute "suppressed" signals in this feature.

### Recommendation: Computed vs Persisted Evaluation

**Recommendation: Compute on demand for MVP.**

- **Pros of on-demand:** No new tables, no sync burden, always consistent with current signals and price data. Evaluation is a read-only analytical view.
- **Cons of on-demand:** Slower for large signal sets; each request recomputes.

**When to persist:** If evaluation is called frequently (e.g., dashboard) and signal volume grows, consider a lightweight cache or materialized table updated by a periodic job. For initial rollout with tens to low hundreds of signals, on-demand is sufficient.

**If persisting later:** A table like `signal_evaluation` (signal_id, horizon_days, forward_return_pct, computed_at) could store outcomes. A batch job would backfill and update. Defer this until profiling shows need.
