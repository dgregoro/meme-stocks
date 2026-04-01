# Quickstart: S7 rule discovery

## Prerequisites

- SQLite with `price_data` for the symbol and range.
- Understanding that **multiple testing** inflates false positives; use hold-out and treat results as exploratory.

## Build matrix

```bash
python -m backend.app.cli research rule-discovery build-matrix \
  --symbol SPY \
  --start 2018-01-02 --end 2024-06-28 \
  --horizon 5 \
  --output data/research/s7_spy_h5_matrix.csv
```

## Run search (requires acknowledgement flag)

```bash
python -m backend.app.cli research rule-discovery run-search \
  --matrix data/research/s7_spy_h5_matrix.csv \
  --train-end 2021-12-31 \
  --ack-overfitting-risk \
  --output data/research/s7_spy_search.json
```

Inspect `warnings` and `n_rules_evaluated` before any narrative conclusion.
