# Feature Specification: Leader-Follower Execution and Paper Trading

**Feature Branch**: `011-leader-follower-execution-and-paper-trading`
**Created**: 2026-03-24
**Status**: Draft
**Input**: User description: "011-leader-follower-execution-and-paper-trading"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — See whether the strategy pays off after costs (Priority: P1)

A researcher or portfolio analyst needs to turn historical leader-follower **signals** into **simulated trades** with explicit entry and exit prices, gross and net returns, and holding length—so they can judge if a documented edge (e.g. from prior evaluation) still holds once execution and costs are applied.

**Why this priority**: Without simulated P&L, it is impossible to claim the strategy is actionable; this is the core value of the feature.

**Independent Test**: Run a simulation over a chosen historical window with default rules and confirm that each recorded trade has entry/exit prices, times, holding length, gross return, and net return after a single configurable cost deduction.

**Acceptance Scenarios**:

1. **Given** historical signals and daily price history for follower symbols over a window, **When** the user runs a simulation, **Then** each executed trade includes entry price, exit price, entry time, exit time, trading-day holding length, gross return (%), and net return (%) after costs.
2. **Given** a follower day with no usable price bar at the required entry or exit, **When** the simulation processes that signal, **Then** the trade is skipped and the skip is counted (no silent fabrication of prices).

---

### User Story 2 — Control how entries and exits are modeled (Priority: P2)

The same user needs to vary **how** a position is opened and closed (e.g. enter on the next session open vs. same-day close; exit after a fixed number of trading days vs. an early exit rule)—so scenarios match different realism assumptions without changing the underlying signal set.

**Why this priority**: Different execution assumptions materially change outcomes; configurability is required for credible what-if analysis.

**Independent Test**: Run two simulations with the same signals and window but different entry/exit modes and confirm results differ only as expected (deterministically reproducible for identical configuration).

**Acceptance Scenarios**:

1. **Given** a configurable entry mode (next trading session open vs. same-day close) and exit mode (fixed holding length vs. early exit rule), **When** the user selects a combination, **Then** the engine applies the documented rules consistently for every trade.
2. **Given** a default holding length and a maximum number of follower positions per leader **event** (same leader and signal date), **When** the simulation runs, **Then** at most that many follower trades are taken per event, chosen by a clear ranking (strength of relationship first, then tie-breakers), and the same configuration always yields the same trade list.

---

### User Story 3 — Review portfolio-level outcomes and retrieve results (Priority: P3)

The user needs **cumulative** performance, drawdown, win rate, and an equity progression—plus **access** to saved runs and per-trade detail (including pagination for large runs)—so they can compare runs and share results.

**Why this priority**: Trade-level output alone is insufficient for risk and drawdown assessment; retrieval supports collaboration and audit.

**Independent Test**: After a simulation completes, list saved runs, open one run for summary and paginated trades, and fetch an equity progression; confirm a missing run yields a clear “not found” style response without exposing internal error details.

**Acceptance Scenarios**:

1. **Given** one or more completed simulation runs, **When** the user lists runs, **Then** they see identifiers, date range, and headline metrics (e.g. trade count, cumulative return, drawdown) sufficient to choose a run.
2. **Given** a valid run identifier, **When** the user requests detail, **Then** they receive the configuration used, summary metrics, and trades (paginated if many), and **When** they request the equity progression, **Then** they receive ordered points that match the sequential compounding of net returns per trade.

---

### Edge Cases

- **No signals** in the window: simulation completes with zero trades and zero cumulative return; no crash.
- **No price data** for a symbol on a required day: skip that trade; count skips.
- **Identical configuration** run twice: same trade set and same aggregate metrics (deterministic).
- **Many signals on the same leader-event**: only top-N followers per event (configurable), ranked deterministically.
- **Invalid or unknown run identifier** on retrieval: user-facing failure without raw technical error content.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST convert eligible historical signals into simulated long-only follower trades with explicit entry and exit prices, gross return, and net return after a single configurable round-trip cost (percentage points).
- **FR-002**: The system MUST support configurable entry behavior (next session open vs. same-day close) and exit behavior (fixed trading-day horizon vs. early exit per the rule defined in assumptions).
- **FR-003**: The system MUST cap how many follower trades are taken per leader **event** (leader + signal date), selecting candidates by a defined ranking order and optional minimum strength filter.
- **FR-004**: The system MUST compute portfolio-level metrics: cumulative return, maximum drawdown on the equity path, trade count, win rate (net > 0), and average net return per trade.
- **FR-005**: The system MUST persist each simulation run with its configuration and aggregate results, and persist each executed trade with enough detail to audit entry/exit and returns.
- **FR-006**: The system MUST allow users to list runs, inspect a run (summary + trades with pagination), and obtain an equity curve for a run.
- **FR-007**: The system MUST support running the same simulation from a command-line interface with parameters equivalent to the configurable execution and cost options.
- **FR-008**: The system MUST treat missing prices as “skip trade” and increment a skip count; it MUST NOT invent prices or returns.

### Key Entities

- **Simulation run**: A single execution over a date range with a frozen set of rules and costs; stores aggregate metrics and a link to its trades.
- **Simulated trade**: One row per executed follower signal outcome: leader, follower, signal date, entry/exit prices and times, holding length, gross and net returns, optional link back to the originating signal.
- **Leader–follower event**: The grouping of all signals sharing the same leader and signal date; used for ranking and position caps.

### Assumptions

- **Early exit rule**: If enabled, exit at the first trading day after entry where the session close is below the entry price; otherwise exit at the fixed horizon (same calendar of trading days as “fixed days” exit).
- **Cost model**: One round-trip cost per trade is subtracted from gross return (percentage points); not split into separate commission and spread unless extended later.
- **Equity path**: Equal notional per trade; sequential compounding of net returns in run order.
- **Trading calendar**: Determined from available daily price history for each symbol (no separate exchange calendar in scope).
- **Signals and prices** are produced elsewhere; this feature consumes them as inputs.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any simulation window with at least one eligible trade, the user can report **total net return** after costs and **maximum drawdown** on the equity path, expressed as percentages.
- **SC-002**: For a fixed configuration and inputs, repeating the simulation yields **identical** trade lists and aggregate metrics (determinism).
- **SC-003**: The user can answer **“What fraction of trades were profitable after costs?”** (win rate) and **“What was the average net return per trade?”** for any completed run.
- **SC-004**: When price data is missing for a required leg, the user sees **fewer executed trades than raw signals** and a **non-zero skip count** (or explicit zero when nothing was skipped).
- **SC-005**: Users can **retrieve** a saved run’s configuration and results without re-running the simulation.

---

## Out of Scope

- Live trading, broker connectivity, or order routing.
- Rich graphical dashboards (tables and exports are sufficient).
- Shorting, options, leverage, or borrow costs.
- Portfolio optimization across multiple correlated strategies beyond the simple sequential equity model defined here.
