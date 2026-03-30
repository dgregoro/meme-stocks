# Feature Specification: Shared research execution platform (020)

**Feature Branch**: `020-shared-research-execution`
**Created**: 2026-03-29
**Status**: Active (core implemented; extended slices planned)
**Input**: Cross-strategy costs, metrics, window splits, run metadata; planned daily backtest and walk-forward harness.

## Clarifications

### Session 2026-03-29

- Q: Interactive `/speckit.clarify` loop? → A: **Deferred** — planning run used `SPECIFY_FEATURE=020-shared-research-execution` on `main`; assumptions documented in `research.md` and slice markdown files.
- Q: Primary consumer for v1? → A: **CLI + services** — same process as `evaluate daily-strategy` and future simulators; no new HTTP API required for 020 core.

## User Scenarios & Testing

### User Story 1 - Reuse one cost and drawdown convention (Priority: P1)

As a researcher implementing a new daily strategy simulator, I want round-trip cost and drawdown math **imported from one module** so leader-follower and daily strategies stay consistent.

**Why this priority**: Prevents silent divergence in reported returns.

**Independent Test**: `pytest backend/tests/test_research_execution.py` + leader-follower paper tests still pass after refactor.

**Acceptance Scenarios**:

1. **Given** gross return + cost in percent points, **When** `apply_round_trip_cost` is called, **Then** net matches documented formula.
2. **Given** an equity curve, **When** `max_drawdown_from_equity` runs, **Then** peak-to-trough matches prior leader-follower behavior.

---

### User Story 2 - Split evaluation windows consistently (Priority: P1)

As a researcher running rolling merit or walk-forward jobs, I want **calendar and trading-day chunking** defined once.

**Why this priority**: Rolling merit already depends on split logic; centralizing avoids drift.

**Independent Test**: `test_daily_strategy_merit` split tests + `test_research_execution` window tests.

**Acceptance Scenarios**:

1. **Given** inclusive calendar range and N, **When** `split_calendar_range` runs, **Then** sub-ranges cover all days without overlap or gaps.

---

### User Story 3 - Attach reproducibility metadata to runs (Priority: P2)

As an operator, I want a **small JSON envelope** (universe fingerprint, cost bps, version hint) I can merge into run outputs.

**Why this priority**: Audit trail for “what was tested” without a full ML experiment DB.

**Independent Test**: `ResearchRunEnvelope.from_context` round-trip in `test_research_execution.py`.

---

### User Story 4 - Generic daily backtest skeleton (Priority: P3 — planned)

As a researcher, I want signal → entry/exit on `price_data` → net PnL series **without** leader-follower signal rows.

**Independent Test**: Synthetic bars in unit test (see `daily-simple-backtest.md`).

---

### Edge Cases

- Missing bars on entry/exit → skip trade; log reason; no fabricated prices.
- Empty symbol list for envelope → validation error or explicit empty fingerprint (documented).
- `SPECIFY_FEATURE` or branch `020-*` must resolve to `specs/020-shared-research-execution/` for Spec Kit scripts.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `research_execution` package with costs, metrics, window splits, and `ResearchRunEnvelope` (implemented).
- **FR-002**: Daily-frequency merit rolling MUST use shared window split functions (implemented).
- **FR-003**: Leader-follower paper trading MUST import shared cost and drawdown helpers (implemented).
- **FR-004**: New simulators MUST use `*_gross` / `*_net` naming per `net-metrics-reporting.md` when adding net series.
- **FR-005**: **Implemented (library)** — `run_daily_simple_long_only_backtest` in `research_execution/daily_simple_backtest.py` (long-only, fixed horizon, `same_close` / `next_open`; see `daily-simple-backtest.md`). DB/CLI wiring optional.
- **FR-006**: **Implemented (library)** — `run_walk_forward_windows` in `research_execution/walk_forward_harness.py` with `strict` flag (CLI flag deferred).

### Key Entities

- **ResearchRunEnvelope**: run_kind, strategy_family, eval window, universe_label, symbol fingerprint, cost_round_trip_bps, optional git/version, notes.
- **MeritRun (existing)**: `daily_strategy_merit_runs` — may gain optional embedded envelope (planned).

### Non-Functional

- **NF-001**: Deterministic pure helpers where no I/O; unit tests must not require network.
- **NF-002**: Align with PRD §5.0 — no silent failures in simulators; explicit skips with reasons.

## Out of Scope

- Regulatory performance advertising, live order routing.
- Full portfolio optimization or multi-asset factor models.
