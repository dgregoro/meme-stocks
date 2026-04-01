# Data model: S7 rule discovery (logical)

No new SQL tables in MVP. Artifacts are **files** and **in-memory structures**.

## Feature matrix row

| Field | Type | Notes |
|-------|------|--------|
| `date` | date | Trading bar date |
| `symbol` | str | Uppercase ticker |
| `ret_1d_pct` | float | Close-to-close % return (signal day, backward) |
| `rv_w` | float \| null | Realized vol of log returns, window from config |
| `vol_z_w` | float \| null | Log-volume z-score, window from config |
| `fwd_h_pct` | float \| null | Forward close-to-close % over horizon `h` (label) |

## Search run result (JSON)

| Field | Type | Notes |
|-------|------|--------|
| `kind` | str | e.g. `s7_rule_discovery_search` |
| `train_end` | date | Last **inclusive** train date for threshold fitting |
| `n_rules_evaluated` | int | After dedupe / caps |
| `rule_results` | list | Per-rule train/test summary metrics |
| `research_envelope` | object | `ResearchRunEnvelope.to_json_dict()` |
| `warnings` | list[str] | Multiple-testing / methodology |

## Rule candidate (logical)

| Field | Notes |
|-------|--------|
| `feature` | Column name (e.g. `rv_w`) |
| `direction` | `gt` or `lte` |
| `threshold` | Float from train quantile |
