# Feature Specification: Leader-Follower Signal Detection

**Feature Branch**: `003-leader-follower-signal-detection`
**Created**: 2026-03-19
**Status**: Draft
**ROADMAP**: New feature (Phase 3/4 candidate)
**Input**: Leader-follower signal detection — detect leader stock movements and identify high-probability follower stocks with delayed movement

## Clarifications

### Session 2026-03-19

- Q: Leader "significant move" criteria — return % and/or volume? → A: Both required — Leader must meet BOTH return % threshold AND volume ratio threshold.
- Q: Relationship mapping storage for MVP? → A: DB table only — New table (e.g. `stock_groups`: group_id, stock_symbol FK stocks.symbol); no JSON-in-config for group membership in MVP.
- Q: How is `strength_score` computed for MVP? → A: Weighted combination — `w_r * norm(|return_pct|) + w_v * norm(volume_ratio)` with configurable weights in `config.py`; values normalized to [0, 1] before weighting; final score clamped to [0, 1].
- Q: Reference date for a detection run? → A: Single as-of date — **`event_date` = latest `price_data.date` among tracked symbols** in scope for this run. All leader/follower metrics for that run use this one date. Symbols with no row for `event_date` (or insufficient prior row for 1-day return) are skipped with log; per PRD §5.0 do not stop the job.
- Q: Cooldown window for (leader, follower) deduplication? → A: 1 day — Default cooldown: do not emit a new signal for the same (leader_symbol, follower_symbol) pair if one already exists within the **same calendar day** (or within 1 calendar day; configurable). MVP default = 1 day.

---

## Brownfield Context

This spec reflects **current repo reality**, not idealized architecture:

- **External API boundary**: Reddit and Yahoo live in `backend/app/services/`; only Alpaca uses `backend/app/clients/`. This feature must NOT assume a clean client/service split. Price/volume data comes from `YahooFinanceService` and `PriceDataRepository` today.
- **Retry**: No shared `backend/app/utils/retry.py` exists. Do not require a broad retry refactor. Use existing patterns (e.g., per-symbol failure isolation).
- **Schema debt**: `RedditPostData.stock_symbol` is a placeholder. This feature is **multi-symbol by design**; avoid single-symbol-per-event assumptions. New models must support leader+follower relationships.
- **Job observability**: `job_run_history` exists; some jobs lack `max_instances=1`/`coalesce=True`. This feature MUST define its own scheduler safeguards and observability; do not assume all existing jobs meet them.
- **Repository injection**: Services create repos inline today. Prefer designs that improve testability incrementally; do not require full DI refactor.
- **Type checking**: mypy may be partially enforced. Encourage typed interfaces; do not assume strict enforcement repo-wide.

---

## Problem Statement

- We want to exploit **lead-lag relationships** between stocks in the same sector or related groups.
- The current system detects unusual activity (volume, price, sentiment) **per symbol** but does not explicitly model **propagation** from leaders to followers.
- Follower stocks in correlated groups often move after a leader; capturing this pattern can identify delayed opportunities.
- The feature must fit into the **current signal pipeline** without requiring a platform rewrite. It integrates with existing data (price, volume) and notification/alert patterns.

---

## Goals

1. **Detect significant leader movements** — Identify stocks that have moved meaningfully (price and/or volume).
2. **Identify candidate follower stocks** — Find stocks in the same group that have not yet moved.
3. **Quantify lag and catch-up potential** — Track time between leader move and follower move; estimate opportunity.
4. **Produce a structured signal** — Emit a signal that can be evaluated, backtested, and later traded.
5. **Preserve traceability** — Raw market inputs → derived events → signals. No fabrication; deterministic where possible.

---

## Non-Goals

- **No trading execution** — Signals inform decisions; no automated order placement.
- **No real-time ultra-low-latency** — Daily or intraday batch is acceptable for MVP.
- **No assumption of specific sentiment source** — Feature may use price/volume only; Reddit is optional enrichment if available.
- **No broad repository architecture cleanup** — Stay within current patterns.
- **No mandatory migration** of Reddit/Yahoo into `clients/` as part of this feature.
- **No global retry/refactor** — Unless a separate spec scopes it.

---

## Definitions

| Term | Definition |
|------|------------|
| **Leader** | A stock that exhibits a **significant** price and/or volume movement within a defined time horizon, making it a candidate source of propagation. |
| **Follower** | A stock in the same **group** as a leader that has not yet moved significantly and may exhibit delayed movement in the same direction. |
| **Lag** | The time elapsed between the leader’s move and the follower’s move. Measured in trading periods (e.g., days) or calendar time. |
| **Propagation event** | The detection of a leader move at time T, which triggers evaluation of follower candidates in the same group. |
| **Confirmation** | Criteria that a follower has “moved” in a way that validates the signal (e.g., breakout, volume increase, relative strength improvement). Pre-confirmation = candidate; post-confirmation = confirmed opportunity. |
| **Opportunity window** | The time interval after a leader move during which we expect a follower to move (e.g., 1–5 trading days). |
| **Outcome window** | The time interval over which we measure whether a follower actually moved (for evaluation and backtesting). |

---

## User Scenarios & Testing

### User Story 1 - Leader Event Detection (Priority: P1)

As a user running the system, I want leader events to be detected when a stock in my tracked universe exhibits a significant price or volume move, so that I can identify stocks that may drive follower movements.

**Why this priority**: Foundation for the entire feature; without leader detection, nothing else works.

**Independent Test**: Can be tested by seeding price_data with a known move, running leader detection, and asserting the correct leader event is emitted with expected metrics.

**Acceptance Scenarios**:

1. **Given** price_data and volume history for symbol X, **When** X moves beyond configured threshold (return %, volume spike), **Then** a leader event is created with symbol, timestamp, move type, and magnitude.
2. **Given** no significant move in any tracked stock, **When** leader detection runs, **Then** no leader events are created.
3. **Given** multiple stocks move significantly, **When** leader detection runs, **Then** one leader event per qualifying stock is created.

---

### User Story 2 - Follower Candidate Selection (Priority: P2)

As a user, I want follower candidates to be identified from stocks in the same group as a leader that have not yet moved, so that I can evaluate potential delayed opportunities.

**Why this priority**: Core value; transforms leader events into actionable candidates.

**Independent Test**: Can be tested by creating a leader event, providing a group mapping (e.g., sector ETF), and asserting the correct follower candidates are returned with exclusion of already-moved stocks.

**Acceptance Scenarios**:

1. **Given** a leader event for symbol A and a group containing A and B, **When** B has not moved significantly, **Then** B is a follower candidate.
2. **Given** a leader event for A and B has already moved, **When** candidate selection runs, **Then** B is excluded.
3. **Given** no group mapping for A, **When** candidate selection runs, **Then** no followers for A (or empty result).

---

### User Story 3 - Opportunity Signal Generation (Priority: P3)

As a user, I want structured opportunity signals (leader, follower, strength, metrics) to be generated and persisted so that I can evaluate, backtest, and act on them.

**Why this priority**: Delivers the final output of the feature.

**Independent Test**: Can be tested by running the full pipeline (leader → candidates → signals) and asserting a signal record exists with required fields.

**Acceptance Scenarios**:

1. **Given** a leader event and follower candidates, **When** signal generation runs, **Then** a structured signal is created with leader, follower, grouping source, timestamp, strength score, and input metrics.
2. **Given** a signal is created, **When** the user queries signals via API, **Then** the signal is returned with full traceability.
3. **Given** confirmation logic is disabled (MVP), **When** signal generation runs, **Then** signals represent pre-confirmation candidates; confirmation is a future extension.

---

### Edge Cases

- **Leader move is idiosyncratic** — No followers move; signal is a false positive. Store outcome for evaluation.
- **Stale upstream data** — Price/volume data is missing or old. Do not fabricate; skip or log; do not crash the job.
- **Ambiguous group relationships** — Multiple groups contain the same stock. **Primary group** for follower selection must be **deterministic**: use the **lexicographically smallest `group_id`** among rows containing that symbol. Document in implementation; same rule in tests.
- **Repeated leader events** — Same leader fires multiple times. Avoid duplicate signals for same (leader, follower) within cooldown window; **MVP default = 1 calendar day** (configurable).
- **Empty universe** — No tracked stocks or no price data. Job completes successfully with zero events; log clearly.

---

## Functional Requirements

### 1. Leader Detection (FR-LEADER)

- **FR-LEADER-001**: Detect significant movement using **configurable thresholds**. A stock qualifies as a leader only when it meets **BOTH** conditions: (a) absolute return % over the time horizon ≥ threshold, AND (b) volume ratio (vs rolling average) ≥ threshold. Neither condition alone is sufficient.
- **FR-LEADER-002**: Be explicit about **time horizon**: MVP supports daily bars (from `price_data`); intraday is future scope if parquet feature store is used.
- **FR-LEADER-005**: Each **run** uses a **single as-of `event_date`**: the **maximum `price_data.date`** (latest calendar date) among rows for **tracked** symbols in the universe for this job. Leader detection and follower comparison use this `event_date` for 1-day return and volume ratio. If a symbol has no price row for `event_date`, or lacks a prior trading day row needed for return, **skip that symbol** and increment a skip counter; do not fabricate; do not fail the job.
- **FR-LEADER-003**: Use existing `PriceDataRepository` and `YahooFinanceService` (or equivalent) for price/volume. Do not assume new data sources.
- **FR-LEADER-004**: Per-symbol detection failures MUST be logged and MUST NOT stop evaluation of other symbols (per PRD §5.0).

### 2. Relationship Mapping (FR-REL)

- **FR-REL-001**: **MVP**: Stock-to-group relationships MUST be stored in a **relational table** (e.g. `stock_groups` with `group_id` and `stock_symbol` referencing `stocks.symbol`). Populate via SQL, seed script, or a future admin API — not via JSON blob in `config.py`. Sector ETF membership and learned/correlation-based mappings remain **future** scope unless expanded in a later spec.
- **FR-REL-002**: MVP favors **explicit, understandable** rows (one symbol may appear in multiple groups) over opaque learned relationships.
- **FR-REL-003**: Mapping MUST be **inspectable** via DB query; document schema in ARCHITECTURE or feature data-model note when implemented.
- **FR-REL-004**: When a symbol appears in **multiple** groups, use **primary group** = **lexicographically smallest `group_id`** for that symbol for follower selection in a single run; document in code and tests.

### 3. Follower Candidate Selection (FR-FOLLOWER)

- **FR-FOLLOWER-001**: Identify stocks in the same group as a leader that have **not yet moved significantly**.
- **FR-FOLLOWER-002**: Exclude stocks disqualified by **obvious weakness rules** (e.g., no price data, negative volume trend) — configurable.
- **FR-FOLLOWER-003**: Do not assume single-symbol-per-event; design for leader + one or more followers per signal/event.

### 4. Lag Measurement (FR-LAG)

- **FR-LAG-001**: Track time between leader move and follower move when outcome is observed.
- **FR-LAG-002**: Define what counts as a follower “move” (e.g., return % threshold, breakout, volume).
- **FR-LAG-003**: Store historical lag distributions in a way that is **inspectable and testable** (e.g., table or aggregate stats).

### 5. Signal Generation (FR-SIGNAL)

- **FR-SIGNAL-001**: Produce a structured **follower opportunity signal** containing:
  - leader stock symbol
  - follower stock symbol
  - grouping / relationship source (e.g., sector, predefined group name)
  - signal timestamp
  - strength/confidence score
  - time since leader move
  - relevant input metrics (leader move %, follower baseline, etc.)
- **FR-SIGNAL-002**: Signals MUST be deterministic and traceable from raw inputs.
- **FR-SIGNAL-003**: **`strength_score`** (0–1) MUST be computed as a **weighted combination** of normalized leader metrics: `w_r * norm(|return_pct|) + w_v * norm(volume_ratio)`, where `norm` maps each metric to [0, 1] using fixed caps documented in config (e.g. return capped at a max %, volume ratio capped at a max multiple). Weights `w_r` and `w_v` MUST be configurable in `config.py` and sum to 1.0. Result MUST be clamped to [0, 1]. Store raw leader `return_pct` and `volume_ratio` on the signal row for audit.

### 6. Confirmation Logic (FR-CONFIRM)

- **FR-CONFIRM-001**: Separate **pre-confirmation** (candidate) from **post-confirmation** (confirmed opportunity). MVP may emit only pre-confirmation signals.
- **FR-CONFIRM-002**: Support optional confirmation criteria: breakout, increasing volume, improving relative strength. Configurable; may be disabled for MVP.
- **FR-CONFIRM-003**: When confirmation is enabled, signals may have a `confirmed_at` timestamp and confirmation criteria met.

### 7. Persistence (FR-PERSIST)

- **FR-PERSIST-001**: Store:
  - detected leader events
  - follower candidates (or fold into signal with status)
  - generated opportunity signals
  - realized outcomes (for evaluation)
- **FR-PERSIST-002**: Be explicit: **new tables/models** for `leader_events`, `leader_follower_signals` (or equivalent), and **`stock_groups`** (group membership). Do not overload `notifications`; this is a distinct signal type. Optionally link signals to notifications for UX.
- **FR-PERSIST-003**: Avoid single-symbol field where relationship-aware modeling is needed. Leader and follower are distinct; grouping is a first-class attribute.
- **FR-PERSIST-004**: **Deduplication / cooldown**: Before emitting a signal for (leader_symbol, follower_symbol), check whether a signal for that pair already exists within the **cooldown window**. **MVP default = 1 calendar day**: do not create a new signal if one exists with `signal_date` within the last 1 calendar day. Config key: `leader_follower_cooldown_days` (int, default 1). Cooldown is measured from the candidate `signal_date` backward.

### 8. Observability (FR-OBS)

- **FR-OBS-001**: Every run MUST record: run status, input universe size, leader events detected, follower candidates detected, signals emitted, key warnings/failure counts.
- **FR-OBS-002**: Use `JobExecutionRepository.record_run` (or equivalent) with metrics_json and summary. Align with `job_run_history` pattern.
- **FR-OBS-003**: Scheduler job for this feature MUST set `max_instances=1`, `coalesce=True`, and appropriate `misfire_grace_time` to prevent overlap. Document in spec; implement in scheduler registration.

### 9. Integration Points (FR-INT)

- **FR-INT-001**: **Upstream**: Depends on `price_data` (and optionally `reddit_daily_feature` if sentiment is added later). Uses `PriceDataRepository`, `StockRepository`. No new external API required for MVP.
- **FR-INT-002**: **Pipeline placement**: New scheduled job (e.g., `leader_follower_detection`) runs after price collection. Composable; does not replace existing jobs.
- **FR-INT-003**: **Downstream**: API endpoint(s) for signals (e.g., `GET /api/leader-follower/signals`). Optional: create notifications for high-confidence signals (reuse `notifications` with type=`leader_follower` and structured signal_metadata).
- **FR-INT-004**: Reference existing modules: `activity_detector`, `notification_service`, `config.py`, `scheduler_service` patterns. Do not invent a greenfield subsystem.

---

## Data Requirements

| Data | Source | Required |
|------|--------|----------|
| Price time series | `price_data` via `PriceDataRepository` | Yes |
| Volume | Same (price_data.volume) | Yes |
| Stock universe | `stocks` via `StockRepository` | Yes |
| Group mappings | **`stock_groups`** (or equivalent) DB table | Yes |
| Historical correlation / co-movement | Future | No (MVP uses explicit groups) |
| Sector/ETF mappings | Future (can seed `stock_groups` from external file offline) | Optional |

MVP MUST NOT depend on unavailable data sources. Price and volume from existing `price_data` are sufficient.

---

## Evaluation / Success Criteria

| Metric | Target |
|--------|--------|
| % of signals where follower moves within outcome window | Measurable; establish baseline in backtest |
| Average return after signal over 1d, 5d, 10d | Track per signal; report aggregate |
| False positive rate | % of signals with no follower move |
| Lag distribution | Percentiles (p50, p90) of lag when follower moves |
| Stability across regimes | Compare performance in up/down/sideways markets (future) |
| Explainability | Every signal has leader, follower, group, metrics — no black box |

---

## Risks / Edge Cases

| Risk | Mitigation |
|------|------------|
| Leader move is idiosyncratic; no propagation | Store outcomes; evaluate hit rate; tune thresholds |
| Weak followers that never move | Exclude by weakness rules; cap candidate count |
| Overfitting to historical correlations | Use explicit groups; avoid opaque learned mapping in MVP |
| Stale or missing upstream data | Skip; log; do not fabricate; per-symbol failure isolation |
| Ambiguous group relationships | Primary group = lexicographically smallest `group_id`; deterministic |
| Duplicate/overlapping signals | Cooldown window (MVP default 1 day); deduplication before insert |

---

## Brownfield Design Constraints

- **Minimal, composable additions** — New service(s), new model(s), new API route(s). Follow Model → Repository → Service → API → Tests (ARCHITECTURE.md).
- **Compatibility** — Preserve existing scheduler/service/repository patterns. Inline repo creation is acceptable; prefer testability improvements where practical.
- **Typed interfaces** — Encourage; do not assume full mypy enforcement.
- **Schema changes** — Justified and incremental. New tables; no breaking changes to existing tables unless explicitly scoped elsewhere.
- **No broad cleanup** — Do not use this feature to refactor retry, clients/, or DI.

---

## Open Questions

1. ~~**How should "significant move" be defined for MVP?**~~ — **Resolved** (see Clarifications): Both return % AND volume ratio thresholds required.
2. **Fixed vs adaptive thresholds?** — MVP likely fixed; adaptive (e.g., relative to recent volatility) is future.
3. ~~**How should relationship mappings be represented initially?**~~ — **Resolved** (see Clarifications): DB table only (`stock_groups`-style), not config JSON.
4. **Leader detection: daily, intraday, or both?** — Daily bars from `price_data` are available; intraday requires parquet/Alpaca. MVP: daily.
5. **Minimum persistence for useful backtesting?** — leader_events + follower_signals + outcome (did follower move, lag) suffice. Need outcome storage for evaluation.

---

## Assumptions

- Price and volume from `price_data` are sufficient for leader detection. No new ingestion.
- Group membership is maintained in **`stock_groups`** (or equivalent table); operators seed or migrate data. No ML/correlation discovery in MVP.
- Existing `job_run_history` and `JobExecutionRepository` are used; no new observability infra.
- Notification integration is optional; signals can be consumed via dedicated API first.
- Constitution and `.cursorrules` apply; PRD §5.0 for reliability.
