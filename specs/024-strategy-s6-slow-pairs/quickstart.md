# Quickstart: S6 slow pairs

## Preconditions

- `seed stocks` + daily `price_data` for leg A and leg B (Alpaca backfill or equivalent).
- Optional: `evaluate daily-strategy s6 ... --preflight-only` to verify overlap.

## Single pair evaluation (JSON)

```bash
python -m backend.app.cli evaluate daily-strategy s6 \
  --symbol AAPL --leg-b SPY \
  --start 2023-01-03 --end 2024-06-28
```

## Pooled merit (multiple leg A vs fixed SPY)

```bash
python -m backend.app.cli evaluate daily-strategy s6-merit \
  --start 2023-01-03 --end 2024-06-28 \
  --symbols AAPL,MSFT --leg-b SPY
```

## Automated bundle + persistence

```bash
python -m backend.app.cli evaluate daily-strategy eval-bundle \
  --strategy s6 --start 2023-01-03 --end 2024-06-28 \
  --symbols AAPL,MSFT --leg-b SPY --rolling-splits 3
```

## Tunables (env)

- `S6_BETA_WINDOW_DAYS`, `S6_ZSCORE_WINDOW_DAYS`, `S6_REGIME_MIN_HISTORY_DAYS`, `S6_REGIME_N_BUCKETS`, `S6_LOAD_BUFFER_CALENDAR_DAYS`

## Tests (local)

```bash
pytest backend/tests/test_s6_slow_pairs.py backend/tests/test_daily_frequency_evaluations.py -k s6 -v
```
