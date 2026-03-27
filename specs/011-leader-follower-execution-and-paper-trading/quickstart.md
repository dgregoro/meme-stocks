# Quickstart: Leader-Follower Paper Trading (011)

## Prerequisites

- Database with `leader_follower_signals` and `price_data` for followers (e.g. after backfill).
- From project root, Python env with `backend` on `PYTHONPATH`.

## Run simulation (CLI)

```bash
python -m backend.app.cli simulate leader-follower \
  --start 2025-02-01 \
  --end 2026-03-20 \
  --entry next_open \
  --exit fixed_days \
  --holding_days 3 \
  --max_positions_per_event 2 \
  --cost_pct 0.1
```

Optional: `--min_pair_score 0.5`, `--exit early_exit`.

Expect: printed summary with `run_id`, cumulative return, drawdown, trade count.

## Query results (API)

```bash
curl -s http://127.0.0.1:8000/api/leader-follower/paper-trading/runs | jq .
curl -s http://127.0.0.1:8000/api/leader-follower/paper-trading/1 | jq .
curl -s http://127.0.0.1:8000/api/leader-follower/paper-trading/1/equity-curve | jq .
```

## Verify

```bash
./scripts/verify.sh
```
