# Quickstart: Leader-Follower Signal Evaluation

**Feature**: 007-leader-follower-signal-evaluation-and-review

## Prerequisites

- Backend running (e.g. `uvicorn backend.app.main:app --reload`)
- At least one leader-follower signal in DB
- Price data for follower symbols

## Verification Steps

### 1. Summary

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/summary" | jq .
```

Expect: `total_signals`, `by_horizon` with 1d/3d/5d metrics.

### 2. Pairs

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/pairs?limit=10" | jq .
```

Expect: `pairs` array with leader/follower and per-horizon metrics.

### 3. Signals (signal-level outcomes)

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/signals?limit=5" | jq .
```

Expect: `signals` array with entry_price and horizon outcomes.

### 4. Top / Bottom pairs

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/top-pairs?n=5&horizon=1d" | jq .
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/bottom-pairs?n=5&horizon=1d" | jq .
```

Expect: ranked pairs by metric.

### 5. Filters

```bash
curl -s "http://127.0.0.1:8000/api/leader-follower/evaluation/summary?since_date=2026-03-01&leader=INTC" | jq .
```

Expect: filtered results.

## Empty State

When no signals exist: summary returns zeros; pairs/signals/top/bottom return empty lists.
