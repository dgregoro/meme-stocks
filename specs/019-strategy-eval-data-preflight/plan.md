# Plan: 019 — Strategy evaluation data preflight & optional auto-fetch

**Status:** Not implemented — handoff for a separate agent.

**Problem:** Commands such as `evaluate daily-strategy` (`s1`, `s2`, `s1-merit`, `s2-merit`, `eval-bundle`) run against the local DB. If a symbol is missing from `stocks` or `price_data` does not cover the eval window with enough history, evaluation returns **zero events** and merit **checklist failures** (`evaluable_count < min`). That reads like a failed strategy but is usually **missing prerequisites**. The JSON may include `symbols_skipped` hints, yet nothing **verifies** or **repairs** data before the heavy run.

**Goal:** Before (or as the first phase of) strategy testing, **verify** that required data exists for the requested symbols and date range; if not, **optionally attempt** to populate it using **existing** seed/backfill paths and external clients, with **explicit** logging and failures per PRD reliability rules.

---

## Scope

### In scope

1. **Preflight checks** (read-only) for daily-strategy evaluation entrypoints:
   - Symbol exists in `stocks` (or document “auto-seed symbol list” behavior if aligned with product).
   - Sufficient `price_data` rows / trading-day coverage for `[eval_start, eval_end]` **plus** the **warm-up** bars required by the strategy (see “Bar budget” below).
   - Clear structured result: `ready | missing_stock | insufficient_history | gaps` (exact enum is implementer’s choice) with per-symbol detail.

2. **Optional auto-remediation** (opt-in via flag, not silent default — see “CLI UX”):
   - **Missing `Stock` row:** invoke existing stock seed path (e.g. `seed stocks` logic or shared service) for requested symbols / known groups — **reuse** code paths; do not duplicate Alpaca HTTP in the evaluate command.
   - **Missing or thin `price_data`:** invoke existing **daily backfill** for the symbol(s) over a computed date range that covers eval window + warm-up (use the same provider client / retry helpers as `backfill` CLI).
   - Respect **rate limits** and **config** (`backend/app/config.py`); surface typed errors on provider failure.

3. **Integration point:** Prefer a small **service** (e.g. `strategy_eval_data_preflight.py` under `backend/app/services/`) called from `backend/app/cli/commands/evaluate.py` **before** `run_*_evaluation` / `run_*_merit_*` / `run_strategy_merit_bundle`. Keep API routes unchanged unless ROADMAP explicitly extends this to HTTP.

4. **Tests:** Unit tests for preflight logic (mock DB / repos); at least one test that auto-fetch delegates to mocked backfill/seed (no real network).

### Out of scope (unless ROADMAP expands)

- Automatic fetch for **non-daily** data, **intraday** strategies, or **event tables** (`extreme_move_events`, `volume_spike_events`) unless a follow-up spec ties them to the same preflight.
- Changing merit **math** or checklist thresholds.
- **Default-on** network fetch without user opt-in (policy: explicit failure is better than surprising API usage).
- Bulk universe backfill for `--all-stocks` without caps (if implemented, require `--confirm` or a hard symbol cap documented in CLI help).

---

## Bar budget (contract for implementer)

Derive minimum required calendar/trading days from existing strategy code so preflight stays in sync:

- **S1:** Uses settings such as `daily_strategy_realized_vol_window`, `daily_strategy_volume_z_window`, `daily_strategy_regime_lookback_days`, `daily_strategy_regime_min_prior_days`, and horizons from `daily_strategy_horizons`. Mirror the same `min_needed` / warm-up logic already used in `run_s1_evaluation` / merit aggregation (see `daily_frequency_strategy_research.py`).
- **S2:** Uses gap/MA parameters from settings; mirror `run_s2_evaluation` / merit paths.

**Preflight must require** at least that many **valid bars before** `eval_start` (and enough forward data for horizons through `eval_end`). If the codebase already centralizes “min bars,” call that helper; if not, extract a single function **used by both** evaluation and preflight to avoid drift.

---

## CLI UX (recommended)

| Flag | Behavior |
|------|----------|
| `--ensure-data` (or `--fetch-missing`) | Run preflight; if checks fail, attempt seed + backfill once; then re-check; fail with structured stderr if still insufficient. |
| `--preflight-only` | Run checks only; print JSON or table; exit 0 even if missing (or exit non-zero — pick one and document; prefer non-zero for “not ready” in CI). |
| (default) | **Current behavior preserved:** no network; optional stderr line suggesting `--ensure-data` when skips occur (nice-to-have). |

**Exit codes:** Document clearly. Example: `0` = evaluation completed; `2` = preflight failed / data still insufficient after fetch; `1` = usage or unexpected error. Align with any existing CLI conventions in `backend/app/cli`.

---

## Reliability (PRD §5.0)

- No silent `except: pass`. Log provider failures with context (symbol, date range, provider).
- Auto-fetch must **not** crash the process on a single-symbol failure if evaluating many symbols: collect per-symbol errors, log, and fail the command with a summary.
- Do not log secrets. Honor existing `ExternalAPIError` / retry helpers under `backend/app/utils/retry.py` and clients under `backend/app/clients/`.
- Background jobs: N/A unless preflight is later invoked from scheduler (not in this spec).

---

## Implementation sketch

1. Add `ensure_strategy_eval_data(...)` (name TBD) in a new service module:
   - Inputs: `db`, strategy kind (`s1` \| `s2` \| `both` for bundle), symbols, `eval_start`, `eval_end`, `mode: preflight_only | ensure`.
   - Output: dataclass or dict: `status`, `per_symbol`, `actions_taken` (e.g. `seeded`, `backfilled_range`), `errors`.

2. Reuse:
   - `StockRepository`, `PriceDataRepository` for checks.
   - Existing **seed stock** and **backfill daily prices** service functions invoked by `seed` / `backfill` CLI — **import and call** those functions rather than shelling out to `python -m ...`.

3. Wire `evaluate daily-strategy` subcommands to call preflight when `--ensure-data` is set.

4. Update **`docs/STRATEGY_TESTING_PLAN.md`** (or `GETTING_STARTED`) with one paragraph: how to run eval with `--ensure-data` and when it calls Alpaca.

5. Update **`docs/ROADMAP.md`** with Phase 2 (or appropriate phase) task row for this spec when implementation starts.

---

## Files (expected)

| File | Action |
|------|--------|
| `backend/app/services/strategy_eval_data_preflight.py` (name TBD) | New — checks + orchestration |
| `backend/app/cli/commands/evaluate.py` | Add flags; call service before eval |
| `backend/app/services/daily_frequency_strategy_research.py` | Optional: extract shared `min_bars_for_strategy(...)` |
| `backend/tests/test_strategy_eval_data_preflight.py` | New |
| `docs/STRATEGY_TESTING_PLAN.md` | Short usage note |
| `docs/ROADMAP.md` | Task entry when claimed |

---

## Acceptance criteria

- [ ] With an empty or missing SPY row, `evaluate daily-strategy s1 --symbol SPY ... --ensure-data` (or merit equivalent) results in either populated data and a normal eval **or** a **clear** error after fetch attempt (no zero-event “fake” failure without explanation).
- [ ] With `--preflight-only`, no external API calls.
- [ ] Unit tests cover happy path (sufficient data), missing stock, insufficient bars, and fetch failure (mocked provider).
- [ ] `./scripts/verify.sh` passes.
- [ ] No new external HTTP outside `backend/app/clients/` patterns.

---

## Open questions for implementer / product

- Should `--ensure-data` default **off** globally but be **on** for `eval-bundle` only? (Spec recommends global opt-in for predictable behavior.)
- For `--all-stocks`, cap symbols or require `--max-symbols N` before auto-fetch to avoid accidental mass API usage.
- SQLite locking: sequential backfill per symbol vs one session; follow patterns used in existing backfill CLI.

---

## References

- `backend/app/services/daily_frequency_strategy_research.py` — merit / eval bar requirements and skip reasons.
- `backend/app/cli/commands/evaluate.py` — daily-strategy commands.
- `backend/app/cli/commands/seed.py`, `backfill.py` — existing automation to reuse.
- `docs/PRD.md` §5.0 — reliability principles.
- `docs/ARCHITECTURE.md` — layered architecture and CLI layout.
