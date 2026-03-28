# Feature Specification: Leader-Follower Sector ETF Confirmation

**Feature Name**: leader-follower-sector-etf-confirmation
**Feature ID**: 013
**Created**: 2026-03-27
**Status**: Draft
**Branch (suggested)**: `013-leader-follower-sector-etf-confirmation`

---

## Executive summary

This feature adds **sector ETF confirmation** as an **optional gate** on leader-follower **execution** (paper trading and any path that simulates trades from stored signals). Trades are only allowed when a **simple, explainable** sector trend/momentum check passes for a **mapped sector ETF**, using **existing daily price data**—no new signal generator, no ML, no intraday stack. The goal is **fewer false positives** and **better interpretability**, with parameters **grid-able** in walk-forward optimization (`010`) and rolling robustness (`012`).

---

## Problem statement

- **No sector context today**: Leader-follower signals fire and simulate **without** regard to whether the **broader sector** is supportive. Follower moves may be **idiosyncratic noise** relative to sector flow.
- **Robustness shows instability**: Rolling robustness (`012`) and single-split optimization (`010`) show **regime dependence**; a plausible driver is **misalignment** between the pair move and sector momentum (e.g., semiconductors for chip leaders).
- **Hypothesis**: Signals are **more reliable when sector momentum aligns** with the direction of the tradeable hypothesis (e.g., long-bias execution only when sector return/trend is non-adverse or positive, per configurable rules).
- **Risk without gating**: Many simulated trades may be **noise**; researchers cannot **filter ex post** by sector in a consistent way until sector context is **computed and stored**.

---

## Goals

- Add **sector-aware filtering** to **reduce false positives** (expected: **same or lower** trade count when the filter is on; not a volume-increasing feature).
- Improve **interpretability** of results via **explicit sector metrics** at decision time.
- Keep rules **simple, testable, and documented** (method id + parameters in config snapshots).
- **Integrate seamlessly** with:
  - `PaperTradingConfig` / `compute_paper_trading_metrics` / paper run persistence
  - Walk-forward optimization and rolling robustness **grids/candidates** (sector params are first-class config fields)
- **Persist sector context** in evaluation/paper outputs for debugging and API consumers.

---

## Non-goals

- **No** predictive sector models, ML, or factor engines.
- **No** advanced statistics beyond simple trend/return rules (see Functional Requirements).
- **No** dynamic ETF selection beyond a **documented static map** (extendable, but not “learned”).
- **No** real-time streaming; **daily** (existing bar) resolution is sufficient for MVP.
- **No** full industry classification product; **minimal** `symbol → ETF` mapping only.
- **No** UI-heavy visualization (JSON/fields on existing APIs suffice).
- **No** intraday sector modeling in MVP.

---

## User stories

### User Story 1: Apply sector confirmation filter (Priority: P1)

As a **developer**,
I want to **require sector alignment** before a paper trade is taken,
so that **weak or unsupported** signals are **skipped** deterministically.

**Why this priority**: Core product behavior; without gating, the feature delivers no value.

**Acceptance criteria**

- When sector confirmation is **enabled**, a signal that would otherwise open a **follower** position is **skipped** if the sector check **fails** (exact skip semantics defined in Functional Requirements).
- When **disabled** (default or explicit), behavior matches **today’s** paper trading (no sector filter).
- Skips are **counted** (e.g., extend existing `skipped_count` or add a dedicated counter) and visible in metrics/debug output.
- Failures in sector data (missing ETF, missing dates) are handled per **PRD §5.0**: **explicit** behavior—either skip with logged reason or fail fast for **misconfiguration**; **no silent** “treat as pass.”

**Independent test**: Run simulation on a fixed DB fixture with synthetic prices; toggling sector gate changes **trade list** and skip counts predictably.

---

### User Story 2: Configure sector rules (Priority: P1)

As a **researcher**,
I want to **tune sector confirmation parameters**,
so that I can **evaluate** their impact on performance in optimization/robustness runs.

**Why this priority**: Without tunable rules, the gate cannot be studied or compared.

**Acceptance criteria**

- Configurable parameters (names illustrative; implement with stable JSON keys):

  | Parameter | Purpose |
  |-----------|---------|
  | `sector_confirmation_enabled` | bool |
  | `sector_trend_method` | enum, e.g. `ma_above`, `rolling_return`, `combined` |
  | `sector_trend_window` | int (trading days; e.g. 5, 10, 20) |
  | `minimum_sector_return_pct` | float; floor for rolling-window sector return when method uses it |
  | `require_positive_trend` | bool; when true, sector must satisfy “positive trend” per method |
  | `sector_etf_symbol` | optional override per run; if unset, use **static map** from leader/follower symbol |

- All parameters are part of **`PaperTradingConfig`** (or an embedded sub-object) so **one JSON** grid continues to drive `010`/`012`.
- Invalid combinations (e.g., unknown `sector_trend_method`) raise **clear validation errors**.

**Independent test**: Unit tests for each `sector_trend_method` against a small price series; config parse rejects bad inputs.

---

### User Story 3: Evaluate impact in optimization and robustness (Priority: P2)

As a **researcher**,
I want sector filtering **included in optimization and robustness runs**,
so that I can measure **consistency** and **trade-offs** (fewer trades vs quality).

**Why this priority**: Aligns with existing research workflow; depends on US1–US2.

**Acceptance criteria**

- Sector-related fields appear in **`010`** grid / **`012`** candidates like any other `PaperTradingConfig` axis (subject to existing **grid caps**).
- Reported metrics reflect **only executed** trades after gating (same as today’s semantics for skipped signals).
- Stored run/config JSON shows sector parameters so runs are **reproducible**.

**Independent test**: Two optimization grid points differ only by `sector_confirmation_enabled`; results differ in **trade counts** and returns when sector gate binds.

---

### User Story 4: Inspect sector context (Priority: P2)

As a **developer**,
I want **sector conditions** alongside trades and evaluations,
so that I can **debug** and explain behavior.

**Why this priority**: Essential for trust and research iteration.

**Acceptance criteria**

- **Paper trades** (and/or evaluation records, where applicable) include **sector fields** such as:
  - `sector_etf_symbol` used
  - `sector_close` or relevant price snapshot
  - `sector_ma` or `sector_rolling_return_pct` (depending on method)
  - `sector_confirmation_passed` (bool)
  - optional `sector_skip_reason` when skipped
- **API** responses that return paper trades or evaluation detail **expose** these fields (read paths only unless existing APIs already mutate).
- **Leader-follower evaluation** outputs (007-style metrics) can attach **summary** sector stats where a row represents a tradable event—**bounded** scope: MVP may be **paper trades only** if evaluation schema extension is disproportionate; spec prefers **both** when low-cost.

**Independent test**: API/CLI inspection shows non-null sector fields when gate enabled and ETF data exists.

---

## Functional requirements

### FR-1. Stock → sector ETF mapping

- Maintain a **static**, **version-controlled** mapping: `stock_symbol → primary_sector_etf_symbol`.
- Examples (illustrative; implementation may start here and grow):

  | Symbols | ETF |
  |---------|-----|
  | NVDA, AMD, INTC | SMH |
  | AAPL, MSFT | XLK |
  | TSLA | XLY |

- **Unmapped** symbols: defined behavior—**skip** sector gate (treat as pass) **with logged warning**, or **fail** if `sector_confirmation_enabled` and strict mode; MVP default: **documented** in `research.md` / quickstart (**recommend**: skip gate + warning so a few unmapped names don’t break batches).
- Mapping lives in a **single module** or config-driven table; **easy to extend** without schema migrations where possible.

### FR-2. Sector data ingestion

- Use **existing** daily price pipeline (`price_data`, Yahoo/yfinance path already used by the app).
- Ensure **mapped ETF tickers** can be resolved and stored like any other symbol (scheduler/seed/bootstrap documentation update as needed).
- **No** separate ingestion microservice.

### FR-3. Sector trend calculation (MVP methods)

Support **simple**, composable methods (exact enums in implementation plan):

1. **`ma_above`**: Compare sector **close** on signal/effective date to **moving average** over `sector_trend_window` **prior** trading days (no leakage: use only data ≤ decision date).
2. **`rolling_return`**: Sector **return over** `sector_trend_window` trading days ending on decision date; require `return_pct >= minimum_sector_return_pct` (or `> 0` if param zero).
3. **`combined`**: Pass only if **both** `ma_above` and `rolling_return` pass (same window or allow separate windows in plan phase if needed; MVP may use **one** window for both).

Additional rules:

- **`require_positive_trend`**: When true, **tighten** interpretation (e.g., for `ma_above`, close must be **strictly above** MA by a configurable epsilon **or** document as “close > MA”; for rolling return, strictly positive excess over minimum).
- All calculations use **existing** `PriceDataRepository` (or equivalent) and follow **timezone/date** conventions used elsewhere.

**Example (illustrative)**:

```text
sector_trend = sector_close_today > MA(sector_close, window=10)
sector_return_ok = rolling_return_pct(window=10) >= minimum_sector_return_pct
pass = sector_trend AND sector_return_ok   # when method = combined
```

### FR-4. Gating integration point

- Apply gate at **simulation entry** time when converting a `LeaderFollowerSignal` into a **paper trade** (same layer as `min_pair_score`, max positions per event, etc.).
- **Leader symbol’s** mapped ETF is the **default** reference; **document** whether follower ETF overrides—MVP: **leader’s group sector** ETF (one ETF per signal event) to avoid ambiguity.
- Deterministic ordering: compute sector snapshot → evaluate pass/fail → then existing entry/exit rules.

### FR-5. Persistence and observability

- Extend **paper trade** model (or adjacent JSON column) with sector fields listed in US4.
- **Migration** for SQLite additive columns; **backward compatible** reads (nulls for old rows).
- Logging: **warning** when ETF missing for mapped symbol; **info** summary for batch runs (counts pass/fail/skip-data).

### FR-6. Configuration and validation

- Defaults: `sector_confirmation_enabled=false` so **brownfield** behavior unchanged.
- `PaperTradingConfig.from_json_dict` accepts new keys; unknown keys for this feature rejected or ignored per existing conventions (prefer **strict** for `sector_*` prefix).
- Document in **`docs/PLAN.md`** or feature **quickstart** how gates interact with **`010`/`012`**.

---

## Key entities (conceptual)

- **Sector mapping entry**: `stock_symbol`, `etf_symbol`, optional `notes`.
- **Sector snapshot** (ephemeral or JSON on trade): prices/returns/flags at decision time.
- **Extended paper trade**: existing row + sector_* fields.

---

## Edge cases

- **Insufficient ETF history** for window: treat as **fail** (skip trade) or **pass with warning**—pick one in **plan/research**; default **fail** when enabled (conservative).
- **ETF halts / flat series**: rolling return or MA undefined—same as insufficient history.
- **Multiple followers per leader event**: sector evaluated **once per event** or per trade attempt—document; MVP per **signal row** is acceptable if simpler.
- **Options paper trades** (if any): sector gate applies only to **stock** leg or **documented** exclusion.

---

## Brownfield compatibility

- **Does not** change leader-follower **detection** output schema by default; filtering is **execution-only** unless evaluation explicitly consumes sector fields later.
- **Scheduler jobs** unchanged except where they ingest ETF symbols (documentation/seed).
- **API**: additive fields; follow **PRD Appendix C** for errors.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| ETF data gaps | Clear skip reason; metrics show data-missing skips |
| Over-filtering kills all trades | `enabled=false` default; tune windows in grid |
| Wrong mapping | Static map + tests; easy MR to fix mapping |
| Look-ahead bias | Use only past bars; unit tests on date boundaries |

---

## Open questions (for plan/research phase)

1. **Strict vs lenient** for unmapped symbols when sector gate on?
2. **Single ETF per signal** from leader’s symbol only, or primary sector from **`stock_groups` metadata** if present?
3. **Evaluation service (007)** scope in MVP: paper trades only vs also extend signal evaluation tables?
4. Separate **`sector_trend_window_ma`** / **`sector_trend_window_return`** for `combined`, or single window for MVP?

---

## Success criteria

- [ ] With sector gate **off**, paper metrics **match** pre-013 behavior within numerical tolerance on representative fixtures.
- [ ] With gate **on**, **fewer or equal** trades vs off on same data; skips are auditable via stored fields.
- [ ] At least one **optimization** grid dimension can toggle sector params and produce **different** ranked outcomes when sector binds.
- [ ] **API** returns sector fields for new paper trades; documented in contract/quickstart when implemented.

---

## Relation to existing features

| Feature | Relationship |
|---------|----------------|
| 003 / signals | Signals unchanged; gate at execution |
| 007 evaluation | Optional sector fields in outputs |
| 010 optimization | Grid includes sector params |
| 011 paper trading | Core integration surface |
| 012 robustness | Same `PaperTradingConfig`; cross-split comparison |

---

## Supplement: implementation guidance (informal)

1. Add `backend/app/config` or **`sector_etf_map.py`** with dict + tests.
2. **`SectorConfirmationService`** (pure functions + price repo): `evaluate_sector_gate(symbol, as_of_date, cfg) -> SectorSnapshot | SkipReason`.
3. Wire into **`leader_follower_paper_trading_service`** at signal→trade selection boundary.
4. Alembic or **SQLite migrate** hook for new columns on `leader_follower_paper_trades` (or JSON `metadata` column if already present—prefer explicit columns for queryability).
5. Extend **optimization grid** `ALLOWED_GRID_KEYS** in walk-forward / robustness loaders.
6. Tests: pure **trend math**, integration **paper run** with mocked prices, **one API** test for new fields.

---

## Requirements traceability (Spec Kit)

### Functional Requirements (numbered)

- **FR-001**: System MUST provide a static, extensible stock→sector ETF mapping.
- **FR-002**: System MUST compute sector trend/momentum from existing daily `price_data` only.
- **FR-003**: System MUST support `ma_above`, `rolling_return`, and `combined` methods with `sector_trend_window` and `minimum_sector_return_pct` / `require_positive_trend` semantics as specified.
- **FR-004**: System MUST apply sector gating inside paper trading execution when `sector_confirmation_enabled` is true.
- **FR-005**: System MUST persist sector context on paper trades (or defined persistence surface) for inspection.
- **FR-006**: System MUST allow sector parameters in optimization (`010`) and robustness (`012`) configs without breaking existing grids.
- **FR-007**: System MUST default sector confirmation to **disabled** for backward compatibility.

### Measurable outcomes (technology-agnostic where possible)

- **SC-001**: Researchers can turn sector gating on/off and see a documented change in **trade count** and **skip breakdown**.
- **SC-002**: 100% of new paper trades with gate enabled store **which ETF** and **whether** confirmation passed.
