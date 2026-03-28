# Data Model: Leader-Follower Pair Filtering and Ranking

**Feature**: 009-leader-follower-pair-filtering-and-ranking

## Overview

No new database tables for MVP. Filtering and ranking operate on existing evaluation output. All pair metrics come from `aggregate_by_pair()` which aggregates `LeaderFollowerSignal` rows.

---

## Existing Entities (Unchanged)

| Entity | Source | Use |
|--------|--------|-----|
| `LeaderFollowerSignal` | `leader_follower_signals` | Source of (leader, follower, signal_date); evaluation aggregates these |
| `PriceData` | `price_data` | Used by evaluation for forward returns |
| `StockGroup` | `stock_groups` | Candidate universe; unchanged |

---

## In-Memory / API Structures

### RankedPairItem (API Response)

Extended from existing `EvalPairItem` with optional metadata:

| Field | Type | Description |
|-------|------|-------------|
| leader_symbol | str | Leader symbol |
| follower_symbol | str | Follower symbol |
| signal_count | int | Number of signals for this pair |
| 1d | object | { win_rate, avg_return_pct } |
| 3d | object | { win_rate, avg_return_pct } |
| 5d | object | { win_rate, avg_return_pct } |
| filter_status | str? | "pass" \| "fail" \| "insufficient_data" (for filtered endpoint) |
| thresholds_applied | object? | { min_signal_count, min_avg_return_1d, min_win_rate_1d } |

### Filter Metadata (Response Metadata)

| Field | Type | Description |
|-------|------|-------------|
| total_before_filter | int | Pairs before applying thresholds |
| total_after_filter | int | Pairs after applying thresholds |
| thresholds_applied | object | Actual thresholds used (config or query override) |

---

## Optional Future Persistence (Out of MVP Scope)

| Entity | Purpose | When |
|--------|---------|------|
| `pair_blacklist` | Manual exclusion of known-bad pairs | If blacklist needed beyond config |
| `allowed_pairs_cache` | Cached filtered pairs for signal job | If evaluation becomes expensive |
