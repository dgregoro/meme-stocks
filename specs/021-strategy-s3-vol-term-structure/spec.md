# Feature Specification: Daily strategy S3 — Volatility term structure regime

**Feature Branch**: `021-strategy-s3-vol-term-structure`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Implement **S3** from the strategy program (`docs/STRATEGY_EXPLORATION.md`, `docs/STRATEGY_TESTING_PLAN.md` §3 Phase B): daily **VIX** vs **medium-term implied vol** (e.g. **VIX3M**) to label **regimes**, then evaluate **regime-conditional equity** behavior with the same operational discipline as **S1/S2** (preflight, checklist, optional merit persistence).

## Clarifications

### Session 2026-03-29

- Q: Primary macro vol data provider for S3 ingest? → A: **Yahoo Finance** — **^VIX** and **^VIX3M** via a dedicated module under **`backend/app/clients/`** with retries and typed errors (option **A**).
- Q: Default methodology for data-driven spread/ratio buckets? → A: **Prior-only expanding percentiles** — at each date **t**, percentile cutoffs use only observations with dates **≤ t**; labeling starts only after **`s3_regime_min_history_days`** (config) prior observation days exist; causal / no future macro leakage (option **A**).
- Q: Default regime bucket count (normal mode)? → C: **4** buckets (**quartiles**); default **`s3_regime_bucket_count = 4`** in `config.py`, overridable (option **C**).
- Q: Default bucketing feature (normal mode)? → A: **`VIX − VIX3M` (difference)** as default; **`VIX / VIX3M` (ratio)** optional via config with **documented guards** when denominator is non-positive / too small (option **A**).
- Q: Default **`s3_regime_min_history_days`**: minimum prior **qualifying** days before labeling? → A: **252** (`config.py` default); **qualifying** = calendar dates **≤ t** with **non-null** fields needed for the active feature (both **VIX** and **VIX3M** for spread/ratio; vix-only mode per narrow policy) (option **A**).

## User Scenarios & Testing

### User Story 1 — Ingest and store macro vol series (Priority: P1)

As a **researcher**, I want **daily** closes for **^VIX** and **^VIX3M** from **Yahoo Finance** (via **`backend/app/clients/`**) **stored by date** so evaluations are **reproducible** without ad hoc re-fetching.

**Why this priority**: Without persisted macro inputs, regime labels drift and audits fail.

**Independent Test**: Ingest a short mocked date range → DB rows match fixture; re-run ingest is **idempotent** (no duplicate logical dates per series); provider failure raises a **typed** error with provider context (PRD §5.0).

**Acceptance Scenarios**:

1. **Given** valid provider responses for dates *D…D+k*, **When** ingestion runs, **Then** each date has **VIX close** and **medium-term index close** (or documented **NULL** policy when a series is unavailable).
2. **Given** a provider **rate limit** or **network failure**, **When** ingestion runs, **Then** the job **logs**, **surfaces** failure, and does **not** write placeholder values.

---

### User Story 2 — Label volatility term-structure regimes (Priority: P1)

As a **researcher**, I want **regime labels** (e.g. backwardation vs contango; **default = quartiles on spread (VIX − VIX3M)**; **ratio optional** via config) computed from **pre-registered** rules (documented defaults in `config.py` + spec) so we avoid **post-hoc** threshold shopping on the full sample.

**Why this priority**: Regime definition **is** the hypothesis carrier for S3.

**Independent Test**: Pure-function tests: fixed VIX/VIX3M series → deterministic regime ids; **missing** input date → no label or explicit **skip** with reason (documented).

**Acceptance Scenarios**:

1. **Given** the default feature **VIX − VIX3M** (or **ratio** mode per config with safe handling), **When** **prior-only expanding** percentiles are applied at each date **t** using only history **≤ t** after **`s3_regime_min_history_days`** is satisfied, **Then** each eligible equity date maps to **one of 4** regimes by default (**quartiles**; `s3_regime_bucket_count` overridable).
2. **Given** only **VIX** is available (operator enables **narrow** mode), **When** labeling runs, **Then** behavior is **explicitly degraded** (e.g. level/vol-of-vix buckets only) and JSON reports **`regime_mode": "vix_only_proxy"`** (exact key names implementer’s choice but must be stable).

---

### User Story 3 — Evaluate equity by regime (Priority: P1)

As a **researcher**, I want **`evaluate daily-strategy s3`** (single-symbol or small set) to report **forward returns** (horizons consistent with S1/S2 settings unless S3-specific keys are added) **conditional on regime** and vs an **unconditional baseline** on the same calendar/trading days, so I can compare buckets **without** leaking future macro.

**Why this priority**: Delivers the core S3 research loop described in `STRATEGY_TESTING_PLAN.md`.

**Independent Test**: Synthetic `price_data` + synthetic macro fixtures → known bucket counts and mean returns; **no network** in unit tests.

**Acceptance Scenarios**:

1. **Given** aligned dates between **equity bars** and **macro table**, **When** `s3` runs, **Then** output JSON includes **per-regime** stats and **evaluable counts**, and **skips** dates with missing macro or insufficient forward bars **with reasons** (no imputation).
2. **Given** 019-style preflight flags, **When** equity data is missing, **Then** behavior **matches** S1/S2 preflight contract (`--preflight-only`, `--ensure-data`).

*(Subcommand name for Story 3: **`s3`**, parallel to `s1` / `s2`.)*

---

### User Story 4 — S3 merit + bundle parity (Priority: P2)

As a **researcher**, I want **`s3-merit`** and **`eval-bundle --strategy s3`** to mirror **S1/S2**: pooled merit report, **checklist**, optional **`--splits`** / **`--split-mode`**, **`--no-persist`**, and **`ResearchRunEnvelope`-compatible** metadata where applicable (020).

**Why this priority**: Automates the gate described in `SIGNAL_EVALUATION_CHECKLIST.md` / strategy testing plan.

**Independent Test**: `pytest` on merit aggregation with mocked DB + macro rows; rollup JSON shape **compatible** with existing `daily_strategy_merit_runs` persistence (`strategy_id` = `s3` or documented canonical id).

**Acceptance Scenarios**:

1. **Given** a multi-split rolling merit run, **When** `s3-merit` completes, **Then** JSON includes **split summaries** and **stability** fields **analogous** to S1/S2 (implementer maps fields; document mapping in `plan.md` / `research.md`).
2. **Given** `DAILY_STRATEGY_MERIT_PERSIST_RUNS=true`, **When** `s3-merit` runs without `--no-persist`, **Then** a row is stored and **`strategies merit-runs show`** can retrieve it.

---

### Edge Cases

- **Misaligned calendars**: Macro is **calendar daily**; equity may miss days — join on **date** with explicit handling (skip vs ffill **forbidden** for prices; macro forward-fill policy **must be explicit** and conservative; default **no ffill** for VIX).
- **Ratio mode**: If **`s3_regime_use_ratio`** (or equivalent) is true, **skip** labeling (with reason) when **VIX3M ≤ 0** or below a small **config epsilon**; never divide by zero.
- **Corporate holidays**: Index may publish when some stocks do not — **primary alignment: equity `price_data` dates** drive which rows get a regime label and forward return; macro is joined **by calendar date** (no price ffill); missing macro on an equity date → **skip** with reason.
- **Stale provider data**: If latest bar is older than *N* calendar days, **warn** in stderr/JSON (`data_freshness` field).
- **Duplicate ingestion**: Same **logical date** for a stored series MUST **upsert** idempotently; **latest successful ingest overwrites** prior values for that date (log at INFO).

## Requirements

### Functional Requirements

- **FR-001**: System MUST persist **daily** macro vol inputs for S3 from **Yahoo Finance** (**^VIX**, **^VIX3M** closes) in SQLite with **calendar date** as primary lookup key, **`provider = yahoo_finance`**, and ingest metadata sufficient for audit. **VIX3M** MAY be null only when **narrow / vix-only** mode is explicitly enabled (User Story 2).
- **FR-002**: All **external HTTP** for these series MUST go through **`backend/app/clients/`** (dedicated Yahoo chart/history or shared helper used elsewhere) with shared **retry/backoff** and **typed errors** (provider, endpoint, status).
- **FR-003**: System MUST expose **deterministic** regime labeling: **default methodology = prior-only expanding percentiles** (history **≤ t** only; **no** train-window leakage). **`s3_regime_min_history_days`** MUST be **config-driven** with **default `252`** — count of **qualifying** prior calendar dates (non-null **VIX** and **VIX3M** when using spread/ratio; narrow / vix-only rules documented separately). **Default `s3_regime_bucket_count = 4`** (quartiles). **Default regime feature = spread** (**VIX − VIX3M**); **ratio** mode MUST be **opt-in** in config. Each eval/merit JSON MUST echo **`regime_label_method`**, **`s3_regime_feature`** (`spread_diff` \| `vix_vix3m_ratio`), **`s3_regime_min_history_days`**, **`s3_regime_bucket_count`**, and vix-only / narrow mode when applicable.
- **FR-004**: System MUST implement **`evaluate daily-strategy s3`** (mirroring `s1` / `s2`) producing **structured JSON** with regime-conditioned forward returns and skips.
- **FR-005**: System MUST implement **`s3-merit`** and support **`eval-bundle --strategy s3`** with checklist and split behavior **consistent** with S1/S2 unless spec amendments record intentional differences.
- **FR-006**: System MUST integrate **019 preflight** for equity `price_data` on S3 entrypoints; optional **`--ensure-data`** MUST follow the same policy as S1/S2.
- **FR-007**: System MUST update **`backend/app/services/strategy_catalog.py`** S3 **`tooling`** to **`implemented`** when FR-004–FR-005 are met; **`cli_hint`** MUST list real commands.
- **FR-008**: New thresholds (**`s3_regime_min_history_days`** (default **252**), **`s3_regime_bucket_count`** (default **4**), **`s3_regime_use_ratio`** (default **false**), ratio **denominator floor** / epsilon if needed, horizons, optional absolute-cut overrides) MUST live in **`backend/app/config.py`** with sane defaults (no magic numbers in service code).

### Key Entities

- **`VolTermStructureObservation`** (working name): `date`, `vix_close`, `vix3m_close` (nullable in vix-only mode), optional derived **`spread`**, `provider` (e.g. `yahoo_finance`), `ingested_at`.
- **`S3RegimeLabel`** (working name): either columns on observation row or child table: `date`, `regime_id`, `regime_version` / `rule_hash` for reproducibility.
- **Evaluation / merit JSON**: regime buckets, baselines, checklist booleans — align field naming with existing **`daily_strategy_merit_*`** reports where possible.

### Non-functional

- **NF-001**: Unit tests MUST be **deterministic**; external APIs **mocked**.
- **NF-002**: PRD **§5.0** — no silent catch-all; meaningful logs for ingestion and eval skips.
- **NF-003**: Ingestion job or CLI MUST be safe to **retry** (idempotent writes).

### Out of scope (v1)

- **HMM** / ML regime classifiers, **options-implied full surface**, **intraday** VIX.
- **Portfolio** or **multi-name** optimization beyond **evaluating** a **symbol list** / merit universe like S1/S2.
- **HTTP API** routes unless **ROADMAP** is updated separately.
- **Short equity** or **hedge-ratio** construction beyond simple **long-only** baseline comparisons (can be **phase 2**).

## Success Criteria

### Measurable Outcomes

- **SC-001**: From repo root, **`python -m backend.app.cli evaluate daily-strategy s3 --help`** documents flags and exits **0** (once implemented).
- **SC-002**: **≥15** new **unit** tests cover ingestion (mocked), labeling, and eval/merit **happy path + one provider-failure path** (no real network required for CI).
- **SC-003**: A **documented** example command in **`quickstart.md`** (added at implement time) reproduces a **small** eval on **fixture or seeded** data.
- **SC-004**: **`strategies list`** shows S3 **`implemented`** after delivery; evidence JSON remains optional.

## References

- `docs/STRATEGY_EXPLORATION.md` — S3 idea, results table
- `docs/STRATEGY_TESTING_PLAN.md` — §3 Phase B, S3 subsection
- `docs/SIGNAL_EVALUATION_CHECKLIST.md` — merit gate
- `specs/019-strategy-eval-data-preflight` — equity readiness
- `specs/020-shared-research-execution` — shared costs / splits / envelope
- `backend/app/services/daily_frequency_strategy_research.py` — S1/S2 patterns to mirror
