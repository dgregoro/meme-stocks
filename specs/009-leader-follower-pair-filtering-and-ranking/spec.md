# Feature Specification: Leader-Follower Pair Filtering and Ranking

**Feature Name**: leader-follower-pair-filtering-and-ranking
**Feature ID**: 009
**Created**: 2026-03-23
**Status**: Draft
**Input**: Filter and rank leader-follower pairs based on historical signal performance to improve signal quality by selecting only the most promising relationships.

---

## Problem Statement

- The system currently generates follower candidates based on stock groups (`stock_groups` table). All symbols in a group are treated as potential followers when a leader is detected.
- Not all leader-follower relationships within a group are useful. Analysis of backfilled evaluation data shows:
  - Strong short-term (1d) performance: 68.5% win rate, 1.09% avg return
  - Weak or decaying performance at 3d and 5d (53.7% and 46.3% win rates, negative medians)
  - Performance concentrated in specific pairs (e.g., semis: INTC, MU, AMAT, AMD)
  - Some pairs produce negative or noisy results (e.g., AVGO→NVDA -5% 1d avg)
- Without filtering, weak pairs dilute overall signal quality and can produce misleading evaluation metrics.
- We need a systematic, data-driven way to rank and filter pairs using historical performance so that only high-quality relationships are used for future signal generation and analysis.

---

## Goals

- Rank pairs by historical performance (primarily short-term, e.g., 1d).
- Filter out weak or negative-performing pairs.
- Provide a clear and explainable selection mechanism.
- Improve overall signal quality without increasing system complexity.
- Enable inspection of which pairs are being used and why.

---

## Non-Goals

- No black-box models or machine learning.
- No real-time adaptive learning or dynamic online learning systems.
- No attempt to fully optimize trading strategy or portfolio.
- No removal of existing `stock_groups`-based structure (for now).
- No trading execution logic.
- No complex statistical modeling.

---

## User Stories

### User Story 1: View ranked pairs

As a developer or researcher,
I want to see leader-follower pairs ranked by performance,
so that I can identify the strongest relationships.

**Acceptance criteria:**

- API returns pairs sorted by:
  - `avg_return_1d` (default)
  - Optional alternative metrics: `win_rate_1d`, `signal_count`, `avg_return_3d`, `avg_return_5d`
- Response includes:
  - `leader_symbol`
  - `follower_symbol`
  - `signal_count`
  - `win_rate_1d`
  - `avg_return_1d`
  - Optional 3d/5d metrics

---

### User Story 2: Filter pairs by quality

As a developer or researcher,
I want to filter out weak pairs,
so that only high-quality relationships are considered.

**Acceptance criteria:**

- Configurable thresholds (via config or query params):
  - `min_signal_count` (e.g., >= 3)
  - `min_avg_return_1d` (e.g., > 0.5%)
  - `min_win_rate_1d` (e.g., > 55%)
- Pairs failing thresholds are excluded from "filtered view".
- Empty-state behavior: return empty list when no pairs pass.

---

### User Story 3: Identify and exclude bad pairs

As a developer or researcher,
I want to explicitly identify harmful pairs,
so that they can be excluded from future signals.

**Acceptance criteria:**

- API or logic can identify:
  - Pairs with negative `avg_return_1d`
  - Pairs below win-rate threshold
- Optional blacklist capability (config or DB-backed) for manual exclusion of known-bad pairs.

---

### User Story 4: Use filtered pairs in signal generation (optional, configurable)

As a developer or researcher,
I want to restrict signal generation to high-quality pairs,
so that emitted signals are more reliable.

**Acceptance criteria:**

- Feature flag or config:
  - `enable_pair_filtering_for_signals` = true/false (default: false)
- When enabled:
  - Follower candidates are filtered by allowed pairs (whitelist from filtered view).
- When disabled:
  - System behaves as today (no filtering at signal generation).

---

### User Story 5: Inspect why a pair is included/excluded

As a developer or researcher,
I want to understand why a pair passed or failed filtering,
so that I can trust the system.

**Acceptance criteria:**

- API response includes:
  - Metrics used for filtering
  - Thresholds applied
  - Pass/fail status (or explicit reason for exclusion)

---

## Functional Requirements

### 1. Pair ranking

- Rank pairs using:
  - `avg_return_1d` (primary sort by default)
  - `win_rate_1d` (secondary or alternative)
  - `signal_count` (alternative, useful for stability)
- Allow sorting by:
  - `avg_return_1d`
  - `win_rate_1d`
  - `signal_count`
  - Optional: `avg_return_3d`, `avg_return_5d`

### 2. Minimum sample size enforcement

- Require:
  - `signal_count >= configurable threshold` (e.g., `min_signal_count`)
- Pairs below threshold:
  - Either excluded from ranked/filtered views, or
  - Marked as "insufficient data" with explicit flag in response

### 3. Filtering logic

- Configurable thresholds (via `config.py` and optionally query override):
  - `min_signal_count`
  - `min_avg_return_1d`
  - `min_win_rate_1d`
- Filtering applied consistently across:
  - GET `/pairs/ranked`
  - GET `/pairs/filtered`
  - Optional signal-generation path when enabled

### 4. API endpoints

Define endpoints:

| Endpoint | Purpose |
|----------|---------|
| GET `/api/leader-follower/pairs/ranked` | Pairs sorted by chosen metric; optional threshold filters |
| GET `/api/leader-follower/pairs/filtered` | Pairs that pass all quality thresholds |
| GET `/api/leader-follower/pairs/blacklist` (optional) | Manually excluded pairs; empty list if not used |

**Query parameters (common):**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| since_date | date? | — | Filter signals with signal_date >= |
| until_date | date? | — | Filter signals with signal_date <= |
| leader | str? | — | Filter by leader symbol |
| follower | str? | — | Filter by follower symbol |
| limit | int | 100 | Max pairs returned |
| sort_by | str | avg_return_1d | Sort metric: avg_return_1d, win_rate_1d, signal_count |
| sort_order | str | desc | asc or desc |
| min_signal_count | int? | config | Override config threshold |
| min_avg_return_1d | float? | config | Override config threshold |
| min_win_rate_1d | float? | config | Override config threshold |

**Response schema (per pair):**

```json
{
  "leader_symbol": "MU",
  "follower_symbol": "INTC",
  "signal_count": 3,
  "1d": {"win_rate": 0.67, "avg_return_pct": 2.3},
  "3d": {"win_rate": 1.0, "avg_return_pct": 4.95},
  "5d": {"win_rate": 0.67, "avg_return_pct": 80.26},
  "filter_status": "pass",
  "thresholds_applied": {"min_signal_count": 2, "min_avg_return_1d": 0.5, "min_win_rate_1d": 0.55}
}
```

**Empty-state behavior:**

- Return `{"pairs": []}` when no pairs meet criteria.
- Include `thresholds_applied` and `total_before_filter` in response metadata when useful.

### 5. Integration with signal generation (optional)

- When `enable_pair_filtering_for_signals` is true:
  - Before emitting a signal for (leader, follower), check that (leader, follower) is in the allowed-pairs set.
  - Allowed set = result of filtered pairs API (or equivalent logic) at job runtime.
- When disabled:
  - No change; existing `select_follower_candidates` uses `stock_groups` only.
- Must not break existing pipeline when disabled.

### 6. Transparency and observability

- Expose in API responses:
  - Thresholds used (config or per-request override)
  - Number of pairs before/after filtering (when applicable)
  - Optional: distribution of metrics (min, max, median) for context

### 7. Brownfield compatibility

- Reuse existing evaluation data and repositories:
  - `LeaderFollowerSignalRepository`
  - `PriceDataRepository`
  - `run_evaluation` and `aggregate_by_pair` from `leader_follower_evaluation_service`
- Avoid duplicating evaluation logic; filter/rank on top of existing pair aggregates.
- Keep implementation incremental and testable.

---

## Data Requirements

- **Existing evaluation results**: Pair-level metrics from `aggregate_by_pair()` (leader, follower, signal_count, 1d/3d/5d win_rate and avg_return_pct).
- **Leader-follower signals**: `leader_follower_signals` table.
- **Price data**: Already used by evaluation for forward-return computation.
- **Stock groups**: Remain unchanged; used for candidate universe. Filtering is an additional layer.

**No new tables required** for MVP. Optional: `pair_blacklist` or `allowed_pairs` table if persistence of manual overrides is needed.

---

## Risks / Tradeoffs

| Risk | Mitigation |
|------|------------|
| Overfitting to recent data | Use configurable date range; document that thresholds reflect historical sample |
| Over-filtering (removing too many pairs) | Conservative defaults; expose before/after counts; make thresholds configurable |
| Small sample sizes misleading rankings | Enforce `min_signal_count`; mark or exclude pairs with insufficient data |
| Performance instability across time | Document that rankings are backward-looking; recommend periodic re-evaluation |

---

## Brownfield Constraints

- Prefer using existing evaluation outputs (`run_evaluation`, `aggregate_by_pair`).
- Avoid large schema changes.
- Keep filtering configurable and reversible (feature flag off = no filtering).
- Avoid introducing heavy computation in hot paths; ranking/filtering is O(n) over pairs, which is small.
- Existing `GET /evaluation/top-pairs` and `GET /evaluation/bottom-pairs` already provide some ranking; new endpoints extend this with explicit filtering and transparency.

---

## Open Questions

1. **Caching**: Should ranking be recomputed on demand (current evaluation is on-demand) or cached? Recommendation: on-demand for MVP; cache only if performance becomes an issue.

2. **Thresholds**: Should filtering thresholds be static (config) or configurable per request? Recommendation: config defaults with optional query-param override for exploration.

3. **Persistence**: Should filtered pairs be persisted or computed dynamically? Recommendation: computed dynamically from evaluation data; optional persistence only for blacklist if needed.

4. **Future**: Should we eventually replace `stock_groups` with learned relationships? Out of scope for this feature; keep as open design question.

---

## Appendix: Current Evaluation Output Reference

Existing `/api/leader-follower/evaluation/pairs` returns:

```json
{
  "pairs": [
    {
      "leader_symbol": "INTC",
      "follower_symbol": "MU",
      "signal_count": 3,
      "1d": {"win_rate": 0.67, "avg_return_pct": 2.30},
      "3d": {"win_rate": 1.0, "avg_return_pct": 4.95},
      "5d": {"win_rate": 0.67, "avg_return_pct": 80.26}
    }
  ]
}
```

Existing `/api/leader-follower/evaluation/top-pairs` and `/bottom-pairs` provide top/bottom N by metric with `min_sample`; new ranked/filtered endpoints extend this with explicit threshold filtering and pass/fail transparency.

---

## Implementation Guidance (Post-Spec)

### Recommended MVP Implementation Approach

1. **Phase 1: API layer only**
   - Add `GET /pairs/ranked` and `GET /pairs/filtered` that reuse `run_evaluation` + `aggregate_by_pair`.
   - Apply sort and filter in-memory on the pair list; no schema changes.
   - Add config keys: `leader_follower_pair_min_signal_count`, `leader_follower_pair_min_avg_return_1d`, `leader_follower_pair_min_win_rate_1d`.

2. **Phase 2: Transparency**
   - Add `filter_status` and `thresholds_applied` to each pair (or to response metadata).
   - Add `total_before_filter` / `total_after_filter` to filtered endpoint response.

3. **Phase 3: Signal-generation integration (optional)**
   - Add `enable_pair_filtering_for_signals` to config.
   - When enabled, inject an allowed-pairs check into `select_follower_candidates` (or a wrapper): load filtered pairs once per run, then filter candidates against that set.

4. **Phase 4: Blacklist (optional, defer if not needed)**
   - Simple config list: `leader_follower_pair_blacklist` as comma-separated "LEADER:FOLLOWER" strings.
   - Or a small DB table if manual overrides are required.

### Likely Files/Modules Affected

| File | Changes |
|------|---------|
| `backend/app/config.py` | Add `leader_follower_pair_min_signal_count`, `leader_follower_pair_min_avg_return_1d`, `leader_follower_pair_min_win_rate_1d`, `enable_pair_filtering_for_signals` |
| `backend/app/api/leader_follower.py` | Add routes: `GET /pairs/ranked`, `GET /pairs/filtered`; optionally `GET /pairs/blacklist` |
| `backend/app/services/leader_follower_evaluation_service.py` | Optional: `filter_pairs_by_thresholds()`, `rank_pairs()` helpers—or keep logic inline in API |
| `backend/app/services/leader_follower_service.py` | When filtering enabled: add allowed-pairs check in `select_follower_candidates` or `create_signals` path |
| `backend/tests/test_leader_follower_api.py` | Add tests for ranked/filtered endpoints |
| `specs/007-leader-follower-signal-evaluation-and-review/contracts/evaluation-api.md` | Extend with new endpoint contracts |

### Top 3 Implementation Mistakes to Avoid

1. **Duplicating evaluation logic**: Do not re-implement `run_evaluation` or `aggregate_by_pair`. Call them, then sort/filter the result. Any new computation should sit on top of existing outputs.

2. **Over-filtering by default**: Start with conservative defaults (e.g., `min_signal_count=2`, `min_avg_return_1d=0`, `min_win_rate_1d=0.5`). With only ~54 evaluable signals and 43 unique pairs, aggressive thresholds will exclude almost everything. Let users tighten via config or query params.

3. **Blocking signal generation on filtered-pairs API**: When `enable_pair_filtering_for_signals` is true, compute the allowed set from evaluation data *inside the job*, not by calling an HTTP endpoint. Keep the dependency internal (service → evaluation service) to avoid coupling and failure modes.

### Recommendation: Default vs Feature Flag

**Filtering in signal generation: behind a feature flag, default OFF.**

- **`enable_pair_filtering_for_signals`**: default `false`
- **Rationale**: Filtering changes observable behavior (fewer signals). Users should opt in after validating that their thresholds and backfill sample produce a sensible allowed set. API endpoints for ranked/filtered pairs can be always-on (they are read-only and exploratory).

**Ranked/filtered API endpoints**: always available, no feature flag.

- These are additive and do not change existing behavior. They support exploration and debugging.
