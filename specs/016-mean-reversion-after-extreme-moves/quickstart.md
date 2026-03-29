# Quickstart: Extreme move research (016)

## Prerequisites

- `stocks` + `price_data` populated (see 015 quickstart for DB alignment).
- Same DB for CLI and API.

## Backfill

```bash
python -m backend.app.cli backfill extreme-move \
  --start 2025-02-01 --end 2026-03-20 --replace-range
```

Optional: `--symbols AAPL,MSFT`.

## Evaluate

```bash
python -m backend.app.cli evaluate extreme-move \
  --start 2025-02-01 --end 2026-03-20 --limit 2000
```

## API

```bash
curl -s "http://127.0.0.1:8000/api/extreme-move/evaluation/summary?since_date=2025-02-01&until_date=2026-03-20&limit=2000"
```

## Config

`extreme_move_up_threshold_pct`, `extreme_move_down_threshold_pct`, `extreme_move_research_horizons`, `extreme_move_research_min_close` in `config.py` / env.

## Quality gate

Apply **docs/SIGNAL_EVALUATION_CHECKLIST.md** before robustness or paper trading.
