# Evaluation API Contract

**Feature**: 007-leader-follower-signal-evaluation-and-review
**Base path**: `/api/leader-follower/evaluation`

## Common Query Parameters

| Param       | Type   | Default | Description                          |
|-------------|--------|---------|--------------------------------------|
| since_date  | date?  | —       | Filter signals with signal_date >=   |
| until_date  | date?  | —       | Filter signals with signal_date <=   |
| leader      | str?   | —       | Filter by leader symbol              |
| follower    | str?   | —       | Filter by follower symbol            |
| limit       | int    | 50      | Max items (pairs/signals)            |
| min_sample  | int    | 2       | Minimum sample for pair rankings     |
| horizons    | str?   | —       | Optional comma list: 1,3,5           |

## GET /summary

**Purpose**: Aggregate metrics (counts, win rate, avg return by horizon).

**Response**:
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

**Empty state**: zeros and empty by_horizon when no signals.

---

## GET /pairs

**Purpose**: Pair-level aggregates with filters.

**Response**:
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

**Empty state**: empty list.

---

## GET /signals

**Purpose**: Signal-level rows with outcomes.

**Response**:
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

**Empty state**: empty list.

---

## GET /top-pairs

**Purpose**: Top N pairs by chosen metric.

**Query params** (add to common): `n` (default 10), `metric` (default `avg_return_pct`), `horizon` (default `1d`).

**Response**: Same shape as /pairs, limited to top N.

**Empty state**: empty list when no pairs meet min_sample.

---

## GET /bottom-pairs

**Purpose**: Bottom N pairs by chosen metric.

**Query params**: Same as /top-pairs.

**Response**: Same shape as /pairs, limited to bottom N.

**Empty state**: empty list when no pairs meet min_sample.

---

## Related Endpoints (009 — Pair Filtering & Ranking)

**Base path**: `/api/leader-follower` (not under /evaluation)

| Endpoint | Purpose |
|----------|---------|
| `GET /pairs/ranked` | Pairs sorted by metric (avg_return_1d, win_rate_1d, signal_count, etc.); optional filtering when `enable_pair_filtering_for_signals` is True |
| `GET /pairs/filtered` | All pairs with `filter_status` (pass/fail/insufficient_data), `total_before_filter`, `total_after_filter`; threshold overrides via query params |
| `GET /pairs/blacklist` | Manually excluded pairs (MVP: always `[]`) |

See `specs/009-leader-follower-pair-filtering-and-ranking/contracts/pairs-api.md` for full contract.
