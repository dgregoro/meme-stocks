# Quickstart: Leader-Follower Pair Filtering and Ranking

**Feature**: 009-leader-follower-pair-filtering-and-ranking

## Prerequisites

- Backend running (e.g., `podman-compose up` or `uvicorn backend.app.main:app`)
- Historical signals in DB (run backfill if needed: `python -m backend.app.cli backfill leader-follower --start 2025-02-02 --end 2025-03-19`)
- API base: `http://localhost:8000` or `http://127.0.0.1:8000`

## 1. Ranked Pairs (default sort: avg_return_1d desc)

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/pairs/ranked?limit=10" | jq .
```

Expect pairs sorted by 1d avg return (highest first).

## 2. Filtered Pairs (only high-quality)

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/pairs/filtered?limit=25" | jq .
```

Expect pairs that pass thresholds; `total_before_filter` and `total_after_filter` in response.

## 3. Override Thresholds (query params)

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/pairs/filtered?min_signal_count=2&min_avg_return_1d=0.5&min_win_rate_1d=0.55&limit=20" | jq .
```

## 4. Sort by Alternative Metric

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/pairs/ranked?sort_by=win_rate_1d&sort_order=desc&limit=10" | jq .
```

## 5. Date Range Filter

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/pairs/ranked?since_date=2025-02-01&until_date=2025-03-31&limit=15" | jq .
```

## Verification

- `total_before_filter` >= `total_after_filter` for filtered endpoint
- Pairs in filtered view have `filter_status: "pass"` (when included)
- Response includes `thresholds_applied` for transparency
