# Pairs Ranking and Filtering API Contract

**Feature**: 009-leader-follower-pair-filtering-and-ranking
**Base path**: `/api/leader-follower`

## GET /pairs/ranked

**Purpose**: Return leader-follower pairs sorted by chosen metric. Optional threshold filtering.

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| since_date | date? | — | Filter signals with signal_date >= |
| until_date | date? | — | Filter signals with signal_date <= |
| leader | str? | — | Filter by leader symbol |
| follower | str? | — | Filter by follower symbol |
| limit | int | 100 | Max pairs returned (1–500) |
| sort_by | str | avg_return_1d | Sort metric: avg_return_1d, win_rate_1d, signal_count, avg_return_3d, avg_return_5d |
| sort_order | str | desc | asc or desc |
| min_signal_count | int? | config | Override config; exclude pairs below |
| min_avg_return_1d | float? | config | Override config |
| min_win_rate_1d | float? | config | Override config |

### Response

```json
{
  "pairs": [
    {
      "leader_symbol": "MU",
      "follower_symbol": "INTC",
      "signal_count": 3,
      "1d": {"win_rate": 0.67, "avg_return_pct": 2.3},
      "3d": {"win_rate": 1.0, "avg_return_pct": 4.95},
      "5d": {"win_rate": 0.67, "avg_return_pct": 80.26},
      "filter_status": "pass",
      "thresholds_applied": {"min_signal_count": 2, "min_avg_return_1d": 0.0, "min_win_rate_1d": 0.5}
    }
  ],
  "total": 43,
  "thresholds_applied": {"min_signal_count": 2, "min_avg_return_1d": 0.0, "min_win_rate_1d": 0.5}
}
```

**Empty state**: `{"pairs": [], "total": 0, "thresholds_applied": {...}}`

---

## GET /pairs/filtered

**Purpose**: Return only pairs that pass all quality thresholds. Excludes weak/harmful pairs.

### Query Parameters

Same as `/pairs/ranked`, plus pairs are filtered (not just sorted). `sort_by` and `sort_order` apply to the filtered result.

### Response

```json
{
  "pairs": [ ... ],
  "total_before_filter": 43,
  "total_after_filter": 18,
  "thresholds_applied": {"min_signal_count": 2, "min_avg_return_1d": 0.0, "min_win_rate_1d": 0.5}
}
```

**Empty state**: `{"pairs": [], "total_before_filter": N, "total_after_filter": 0, "thresholds_applied": {...}}`

---

## GET /pairs/blacklist (Optional, MVP: return empty)

**Purpose**: Return manually excluded pairs. If not implemented, return empty list.

### Response

```json
{
  "pairs": []
}
```
