# Feature Specification: Volume spike vs baseline signal research

**Feature Name**: volume-spike-vs-baseline-signal-research
**Feature ID**: 015
**Created**: 2026-03-28
**Status**: Draft
**Branch (suggested)**: `015-volume-spike-vs-baseline-signal-research`

---

## Executive summary

This feature adds a **research-only** pipeline to detect **unusual daily volume** relative to each symbol’s **rolling baseline** (from existing `price_data`), classify spikes by **same-day price behavior**, **persist** candidate events, and **evaluate** short-horizon forward returns (1d / 3d / 5d trading days) with **separable hypotheses** by event type. It intentionally avoids ML, live trading, portfolio logic, and a full paper-trading engine in MVP. It should **mirror patterns** already used for leader-follower evaluation (`leader_follower_evaluation_service`, read-only evaluation routes under `/api/leader-follower/evaluation/*`) and historical backfill CLI style (`backfill leader-follower`), adapted for a **single-symbol, daily-bar** signal family.

---

## Problem statement

- The **pair-based leader-follower** strategy has **not shown stable robustness** across rolling time splits; it is **regime- and relationship-dependent** and operationally heavy.
- A **simpler signal** grounded in **each stock’s own history** may **generalize more predictably** for research, even if it is not ultimately profitable.
- **Unusual volume relative to a stock’s baseline** may coincide with:
  - renewed attention,
  - informed or coordinated flow,
  - or setups for **continuation**, **reversal**, or **volatility expansion**—these are **distinct hypotheses** and must stay **separable** in outputs.
- The codebase already has **ingestion**, **daily `price_data`**, **evaluation-style aggregations**, and **CLI/API** patterns; we need a **disciplined, minimal** way to **detect**, **store**, and **evaluate** volume-spike events without entangling them with leader-follower tables or execution.

---

## Goals

- Detect **volume spikes** using **volume_ratio = day_volume / baseline_volume** with a **configurable baseline window** (e.g. rolling mean or median over N trading days).
- **Classify** each detected event into **simple, interpretable** categories from **same-day return**: `spike_up`, `spike_down`, `spike_flat` (thresholds configurable).
- **Evaluate** forward returns at **1d, 3d, 5d** trading days (aligned with existing `leader_follower_evaluation_horizons` style and trading-day logic where practical—e.g. `label_service` / price repo conventions).
- Support **summary and breakdowns** by **event_type**, **symbol**, and **date range** to judge whether any variant has **stable** signal quality (research framing, not production claims).
- **Reuse** `PriceDataRepository` and existing **read-only API** + **Typer CLI** patterns; keep schema **additive** and **narrow**.

---

## Non-goals

- **No** machine learning, scoring models, or black-box predictors.
- **No** portfolio construction, position sizing, or risk limits.
- **No** live trading, broker integration, or alerts in MVP.
- **No** broad multi-signal ensemble combining leader-follower, Reddit, sentiment, etc.
- **No** optimization grids over **dozens** of thresholds in v1 (a **small** fixed default set or single default profile is enough).
- **No** full **paper trading engine** for this signal in MVP (evaluation is **computed on demand** or via explicit research outputs, like much of 007 evaluation).
- **No** mandatory **news** or **sentiment** inputs (optional future hooks only as comments or extension points).

---

## Important framing

- This is **signal research**, not a **production trading strategy**.
- **Simplicity** and **interpretability** outweigh feature richness.
- **Hypotheses stay separable**: aggregation dimensions must include **event_type** so continuation- vs reversal-leaning stories are not blended by default.

---

## User stories

### User Story 1: Detect volume spike events (Priority: P1)

As a **developer or researcher**,
I want to identify when a stock’s **volume is unusually high** relative to its **own recent baseline**,
so that I can evaluate whether those events matter.

**Acceptance criteria**

- Detection uses **daily** `price_data.volume` (and close for classification).
- **Baseline** is a **rolling** statistic over **W** prior **trading days** ending the day **before** the candidate day (no same-day leakage into baseline).
- **volume_ratio** is defined and stored; event fires when **volume_ratio ≥ configured threshold**.
- **W**, **threshold**, and baseline **statistic** (mean vs median—see Open Questions) are **configurable** via config and/or CLI flags.

**Independent test**: Synthetic or fixture prices where volume jumps 3× baseline produce an event; non-spike days do not.

---

### User Story 2: Classify spike type (Priority: P1)

As a **developer or researcher**,
I want to distinguish whether the volume spike occurred with **up**, **down**, or **flat** same-day price action,
so that I can test **different hypotheses separately**.

**Acceptance criteria**

- Each persisted event has **event_type** ∈ {`spike_up`, `spike_down`, `spike_flat`}.
- Classification uses **same-day return** (e.g. close vs prior close), with **configurable** high/low flat bands (e.g. ±ε %).
- Rules are **documented** in spec/research notes; no hidden composite labels in MVP.

**Independent test**: Controlled return series flip labels across thresholds predictably.

---

### User Story 3: Evaluate outcomes (Priority: P1)

As a **developer or researcher**,
I want to see **forward returns** after each spike event,
so that I can see if there is **continuation**, **reversal**, or **no edge**.

**Acceptance criteria**

- Horizons **1d, 3d, 5d** **trading days** forward from **event_date** (or from **next** trading day—**one convention chosen and documented** to avoid look-ahead).
- Per horizon (and overall): **count**, **win rate** (e.g. return > 0), **avg return %**, **median return %**.
- Results can be **broken out by event_type** and, where implemented, by symbol.
- Missing forward prices → event **excluded** from that horizon’s stats with explicit **evaluable_count** (no fabricated returns).

**Independent test**: Known price path yields known forward returns for a single event.

---

### User Story 4: Backfill historically (Priority: P2)

As a **developer or researcher**,
I want to **backfill** volume spike events across **date ranges**,
so that I can build **sample size** quickly.

**Acceptance criteria**

- CLI supports a **replay/backfill** command over `[start, end]` (pattern: `python -m backend.app.cli …` analogous to `backfill leader-follower`).
- Idempotent or **deduplicated** persistence (e.g. unique **(symbol, event_date)** or explicit upsert policy).
- Uses **existing** DB session and **price_data** only; no new mandatory external API for MVP.

**Independent test**: Running backfill twice does not duplicate rows (or documents intentional replace mode).

---

### User Story 5: Inspect signal quality (Priority: P2)

As a **developer or researcher**,
I want to inspect **best/worst symbols** and **event types**,
so that I can see if the idea is **broad** or **concentrated**.

**Acceptance criteria**

- Read-only **API** and/or **CLI** can group results by **symbol**, **event_type**, and **date range**.
- “Top/bottom” views respect **minimum sample size** or expose **n** prominently (007-style caution).

**Independent test**: API returns stable JSON shape; empty range returns explicit empty summary, not 500.

---

## Functional requirements

### FR-1. Baseline volume calculation

- Input: ordered **daily** bars for symbol with **volume** and **close**.
- Baseline window: **W** trading days **strictly before** event date.
- Baseline value: **mean or median** of volume over that window (product decision in Open Questions; implementation must support **one** in MVP and leave the other as a **config switch** if low cost).
- **baseline_volume** > 0 required; if baseline missing or zero → **no event** (or explicit skip reason in logs for backfill).

### FR-2. Spike threshold

- **volume_ratio = volume_event / baseline_volume**.
- Event if **volume_ratio ≥ T**; **T** configurable (defaults recommended in supplement below).
- Optional MVP guardrails (Open Questions): **minimum dollar volume**, **minimum price**, or **minimum baseline volume** to reduce penny-name noise.

### FR-3. Price-action classification

- Same-day return: **(close_event / close_prev) - 1** (or documented alternative).
- **spike_up**: return ≥ **up_threshold**.
- **spike_down**: return ≤ **down_threshold** (negative).
- **spike_flat**: otherwise (band between up/down thresholds).
- Thresholds are **configurable** percentages or decimals consistent with rest of codebase.

### FR-4. Persistence (`VolumeSpikeEvent` conceptual model)

New table (name may be `volume_spike_events` or equivalent), minimum fields:

| Field | Purpose |
|-------|---------|
| `id` | PK |
| `symbol` | Ticker |
| `event_date` | Date of spike (trading day) |
| `volume` | Day volume |
| `baseline_volume` | Baseline aggregate used |
| `volume_ratio` | Ratio |
| `same_day_return_pct` | For auditability |
| `event_type` | `spike_up` \| `spike_down` \| `spike_flat` |
| `created_at` | Insert time |

Optional for MVP if kept minimal: `baseline_window_days`, `threshold_used`, `config_hash` for reproducibility.

### FR-5. Evaluation support

- Load events + **PriceDataRepository** forward bars; use **trading-day** stepping consistent with existing evaluation/label logic.
- Aggregates: by **event_type**, **symbol**, **horizon**, **date range**.
- Output shape analogous to 007 summary sections: counts, win rate, avg/median return, **evaluable_count** per horizon.

### FR-6. CLI support

- **`backfill volume-spike`** (or nested under `research` if that matches roadmap): `--start`, `--end`, universe selection consistent with existing patterns (e.g. tracked stocks, optional symbol list).
- **`evaluate volume-spike`** (or query-only via API first): print or export summary; exact naming to match `backend.app.cli` conventions.
- **Typer** options: follow existing underscore flags where the project standardizes (see CLI help for leader-follower).

### FR-7. API support (read-only)

New router prefix suggested: **`/api/volume-spike`** (or `/api/research/volume-spike` if research namespace is preferred later).

| Endpoint | Purpose |
|----------|---------|
| `GET .../events` | List/filter events (symbol, date range, event_type, pagination) |
| `GET .../evaluation/summary` | Global + by_horizon + by_event_type |
| `GET .../evaluation/by-symbol` | Aggregates per symbol |
| `GET .../evaluation/by-type` | Aggregates per event_type |

Errors: **PRD Appendix C** structured errors; no raw tracebacks.

### FR-8. Brownfield compatibility

- **Daily** `price_data` only for MVP unless intraday reuse is trivial.
- **Additive** SQLite migration in `database.py` (`_migrate_*` pattern).
- **No** changes to leader-follower signal schema required for MVP.
- Services: **repository → service → API route** per `docs/ARCHITECTURE.md`.
- Tests: **unit** for pure detection math; **integration** for API with in-memory DB.

---

## Data requirements

- **Historical daily** OHLCV in **`price_data`** for symbols under study.
- Existing **stock** / **universe** listing as today’s backfill uses (tracked stocks or configured list).
- **No** new mandatory external data feed for MVP.

---

## Risks and tradeoffs

| Risk | Mitigation |
|------|------------|
| Spikes ubiquitous in illiquid tickers | Optional liquidity/price filters; document concentration |
| Hypothesis fishing across many thresholds | Cap v1 to **one** default profile + document extensions |
| Continuation vs reversal narratives conflict | **Always** segment by **event_type** and report **n** |
| Overlap with corporate actions | Out of scope for MVP; document assumption (raw volume) |

---

## Brownfield constraints

- Keep logic **explainable in one screen of code** for detection + classification.
- Prefer **one new event table** + **one service** + **one router** over a generic “event framework.”
- Reuse **`PriceDataRepository`** (`get_for_date`, `list_dates_for_symbol`, batch patterns as needed).

---

## Open questions

1. **Baseline statistic**: **mean** vs **median** volume? (Median is more robust to one-off past spikes; mean is more standard—pick one default, allow config.)
2. **Low-price / low-liquidity stocks**: exclude in MVP (e.g. min close, min avg dollar volume) or include with warnings?
3. **Minimum absolute dollar volume** on spike day: required or optional?
4. **Gap vs intraday move**: MVP uses **close/close** same-day return only; treat **overnight gap** separately in a later iteration?
5. **Primary hypothesis for v1 narrative**: continuation, reversal, or **agnostic typing only**? (Recommendation in supplement.)

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| 007 Leader-follower evaluation | Template for **horizons**, **summary metrics**, **read-only** evaluation API style |
| 008 Historical backfill / replay | Template for **CLI backfill** and date-range processing |
| `PriceDataRepository` | **Source of truth** for daily volume and close |
| `label_service` / trading-day helpers | **Reuse** for forward return calendar logic where applicable |
| 011 Paper trading | **Not** required for MVP; evaluation is research-grade |

---

## Requirements traceability (concise)

| ID | Requirement |
|----|-------------|
| FR-015-001 | Rolling baseline volume and ratio with configurable window and threshold |
| FR-015-002 | Three-way event_type from same-day return |
| FR-015-003 | Persist VolumeSpikeEvent rows with audit fields |
| FR-015-004 | Forward returns 1d/3d/5d with aggregates by type and symbol |
| FR-015-005 | CLI backfill + evaluate (or API-first with CLI thin wrapper) |
| FR-015-006 | Read-only REST endpoints under `/api/volume-spike/...` |
| FR-015-007 | Tests + structured errors; no ML; no live trading |

---

# Supplement: Pre-plan guidance (not a plan or task list)

## Recommended MVP implementation approach

1. **Model + migration** for `volume_spike_events` with unique constraint on **(symbol, event_date)** (or documented dedupe).
2. **Pure functions** in a small module: `baseline_volume(...)`, `classify_spike_type(...)`, `detect_spike_for_day(...)` for testability.
3. **`VolumeSpikeEventRepository`** + **`volume_spike_service`**: `backfill_range(db, start, end, config)`, `load_events(...)`, `evaluate_events(...)`.
4. **Evaluation** initially **on-demand** from stored events + `PriceDataRepository` (no second heavy persistence layer for forward returns unless needed later).
5. **API** read-only router registered in `main.py`; **CLI** two commands mirroring backfill/evaluate naming elsewhere.
6. **Config**: new `Settings` keys with defaults (baseline window, ratio threshold, return bands)—no hardcoded magic in services.

## Likely files and modules affected

- `backend/app/models/volume_spike_event.py` (new)
- `backend/app/data/repositories/volume_spike_event_repo.py` (new)
- `backend/app/services/volume_spike_detection_service.py` and/or `volume_spike_evaluation_service.py` (new; may be one file if tiny)
- `backend/app/data/database.py` — `_migrate_volume_spike_events` + `init_db` hook
- `backend/app/api/volume_spike.py` (new router)
- `backend/app/main.py` — `include_router`
- `backend/app/cli.py` — Typer commands
- `backend/app/config.py` — thresholds and windows
- `backend/tests/test_volume_spike_*.py` (new)

## Top three implementation mistakes to avoid

1. **Look-ahead / leakage**: including **event-day volume** in the baseline or using **future** closes for classification.
2. **Silent drops**: missing forward bars should **reduce evaluable_count** and be **visible** in API output, not impute returns.
3. **Scope creep**: building a **generic event bus**, **ML layer**, or **paper trading** before the **first** end-to-end backfill + summary proves the pipeline.

## Recommendation: initial default thresholds (starting point only)

- **Baseline window W**: **20** trading days.
- **Baseline statistic**: start with **median** volume (robust); expose **mean** via config if cheap.
- **Spike ratio T**: **3.0** as primary default; optional research profile at **2.0** and **5.0** documented but not required in v1 code paths beyond config.
- **Same-day return bands** (for flat): **±0.5%** if using close/close; **≥ +0.5%** → `spike_up`, **≤ −0.5%** → `spike_down`, else `spike_flat`. Tune via config, not scattered literals.

## Recommendation: continuation vs reversal vs all three types

- **Emit and persist all three** event types from day one so hypotheses stay **separable**.
- **Primary MVP analytic lens**: **agnostic**—report **all** types side-by-side at each horizon without picking a “winner” in code.
- **Narrative focus** for first research readout: emphasize **spike_up** vs **spike_down** (continuation vs mean-reversion intuition) and use **spike_flat** as a **control bucket** for “volume without directional close”; avoid declaring a single primary hypothesis in the implementation until data is reviewed.

---

## Document control

- **Plan** (`plan.md`) and **tasks** (`tasks.md`) are **out of scope** for this document iteration per author instructions; run `/speckit.plan` and `/speckit.tasks` when ready.
