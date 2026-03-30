# Slice: Run envelope (reproducibility metadata)

**Status:** ✅ Dataclass + JSON serde implemented; ⏳ Optional persistence on `daily_strategy_merit_runs` **not** implemented (no schema migration yet).

## Purpose

Attach a **small, stable JSON object** to any research run so a future you (or an agent) can answer:

- Which **universe** (label + symbol fingerprint)?
- Which **date window**?
- Which **strategy family** / **run kind**?
- What **round-trip cost assumption** (bps) was used for interpretation?
- What **version** hint (`APP_VERSION` / `GIT_SHA`) was available in the environment?

This is **not** a substitute for full experiment tracking (DVC, MLflow); it is a **minimum audit trail** inside this app.

## Requirements (implemented)

**Type:** `ResearchRunEnvelope` in `research_execution/run_envelope.py`.

**Factory:** `ResearchRunEnvelope.from_context(...)` accepts:

- `run_kind`, `strategy_family`, `eval_start`, `eval_end`
- `universe_label` (human-readable, e.g. `under50b_first100`)
- `symbols: list[str]` — normalized to uppercase dedup set for `symbol_count` and **SHA-256 fingerprint** (first 16 hex chars of hash of sorted JSON array)
- `cost_round_trip_bps`
- optional `notes`

**Serialization:** `to_json_dict()` uses ISO date strings; `from_json_dict()` round-trips for tests.

**Version fields:** `git_sha_or_version` populated from `os.environ.get("APP_VERSION")` or `os.environ.get("GIT_SHA")` when set.

**Config default:** `research_default_round_trip_cost_bps` in `config.py` documents a **default assumption** for envelopes; simulators may override.

## Planned extensions

1. **Embed in merit JSON** — merge `envelope.to_json_dict()` under key `run_envelope` when persisting merit/bundle (requires product decision: always vs opt-in flag).
2. **DB column** — optional `envelope_json TEXT` on `daily_strategy_merit_runs` to query by fingerprint without parsing full `report_json` (migration in `database.py` pattern).
3. **Recipe YAML** — optional `envelope:` block passed through `research recipe` (018).

## Acceptance (when persistence is added)

- At least one integration test: merit run row contains expected `run_envelope.symbols_fingerprint_sha256_16` for a fixed symbol list.
- Document CLI flag in `integration-conventions.md`.
