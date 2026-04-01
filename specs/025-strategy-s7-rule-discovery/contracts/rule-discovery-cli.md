# Contract: `research rule-discovery` CLI

## `research rule-discovery build-matrix`

**Purpose**: Emit a deterministic CSV feature matrix for one symbol from `price_data`.

| Option | Required | Description |
|--------|----------|-------------|
| `--symbol` / `-s` | yes | Ticker |
| `--start` | yes | `YYYY-MM-DD` load from |
| `--end` | yes | `YYYY-MM-DD` load through |
| `--horizon` | yes | Forward return horizon in trading days (label column) |
| `--output` / `-o` | yes | CSV path |

**Output**: CSV header includes `date,symbol,ret_1d_pct,rv_w,vol_z_w,fwd_{h}_pct`.

**Errors**: Typer exit 1 if no rows or insufficient history; messages must name symbol and date range.

## `research rule-discovery run-search`

**Purpose**: Bounded grid over single-condition quantile rules; train/test split by date.

| Option | Required | Description |
|--------|----------|-------------|
| `--matrix` | yes | Path to CSV from `build-matrix` |
| `--train-end` | yes | Last **inclusive** date for fitting quantile thresholds |
| `--label` | no | Label column (default: infer `fwd_<h>_pct` from header) |
| `--ack-overfitting-risk` | yes | Must be passed; otherwise exit 1 |
| `--output` | no | JSON path (default: stdout only) |

**Output**: JSON with `kind`, `warnings`, `n_rules_evaluated`, `rule_results`, `research_envelope`.

**Prohibited**: No integration with `eval-bundle` or `daily-strategy` merit persistence in this contract revision.
