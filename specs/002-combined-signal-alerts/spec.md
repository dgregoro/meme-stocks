# Feature Specification: Combined Signal Alerts

**Feature Branch**: `002-combined-signal-alerts`  
**Created**: 2026-03-13  
**Status**: Draft  
**ROADMAP**: Phase 2.5 (PLAN.md, PRD FR-3.7)  
**Input**: Combined Signal Alerts — aggregate multiple signals before generating alerts

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alerts Only When Multiple Signals Align (Priority: P1)

As a user monitoring meme stocks, I want alerts to be generated only when multiple independent signals converge (sentiment, price, volume, technical indicators) so that I receive fewer false positives and higher-quality notifications.

**Why this priority**: Core value of the feature; without multi-signal convergence, the improvement over current behavior is minimal.

**Independent Test**: Can be tested by simulating various signal combinations and verifying that alerts are created only when the combined score meets the threshold.

**Acceptance Scenarios**:

1. **Given** only one signal fires (e.g., volume spike alone), **When** the aggregation layer evaluates, **Then** no alert is generated.
2. **Given** multiple signals fire (e.g., sentiment spike + price breakout + volume spike), **When** the combined score meets or exceeds the threshold, **Then** an alert is generated.
3. **Given** multiple signals fire but the combined score is below the threshold, **When** evaluated, **Then** no alert is generated.

---

### User Story 2 - Alert Explanation (Priority: P2)

As a user receiving an alert, I want to see which signals contributed to it and their individual values so that I can understand why the alert was triggered and make informed decisions.

**Why this priority**: Explainability is a core requirement; users must trust and interpret alerts.

**Independent Test**: Can be tested by generating an alert and verifying that the structured explanation lists all contributing signals with their values.

**Acceptance Scenarios**:

1. **Given** an alert is generated, **When** the user views it, **Then** the alert includes a list of which signals fired and their individual values.
2. **Given** an alert is generated, **When** the user views it, **Then** the alert includes the combined score.
3. **Given** multiple alerts for different symbols, **When** the user views them, **Then** each alert has its own explanation tied to that symbol and evaluation time.

---

### Edge Cases

- What happens when a signal source returns no data? The aggregation layer treats missing signals as not firing; the score is computed from available signals only.
- How does the system handle a symbol with no price or sentiment data? No alert is generated; per-symbol failures must not crash the job (per PRD §5.0).
- What is the minimum number of signals required? Configurable; the threshold defines when an alert fires (e.g., score ≥ N).
- How are weights and thresholds determined? Configurable via application configuration; no hardcoded magic numbers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST aggregate signals from existing analysis components (sentiment, price, volume, technical indicators) per ticker before deciding whether to create an alert.
- **FR-002**: Each signal type MUST contribute to a weighted combined score; weights MUST be configurable.
- **FR-003**: Alerts MUST be generated only when the combined score meets or exceeds a configurable threshold.
- **FR-004**: Each alert MUST include structured metadata describing which signals fired, their individual values, and the combined score.
- **FR-005**: The aggregation layer MUST consume outputs from existing detectors (sentiment, price, volume, RSI) without modifying those components.
- **FR-006**: Missing or unavailable signals MUST be treated as non-contributing (score = 0 for that signal); the system MUST NOT fabricate values.
- **FR-007**: Per-symbol evaluation failures MUST be logged and MUST NOT stop evaluation of other symbols or the job itself (per PRD §5.0).

### Key Entities

- **Signal**: A single indicator (e.g., sentiment spike, price breakout, volume spike, RSI threshold). Has a type, value, and optional contribution to the combined score.
- **Combined Evaluation**: The result of aggregating signals for a ticker at a point in time. Includes which signals fired, their values, the combined score, and whether the threshold was met.
- **Alert**: A notification created when the combined score meets the threshold. Includes the structured explanation (signals fired, values, combined score).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Alerts are generated only when at least two signal types contribute and the combined score meets the configured threshold.
- **SC-002**: Every generated alert includes structured metadata (signals fired, individual values, combined score) that can be displayed or logged.
- **SC-003**: False positives from single-signal noise decrease compared to the current independent-alert behavior (qualitative improvement; can be validated by manual review).
- **SC-004**: Per-symbol failures do not cause job failure; the system continues evaluating other symbols.

## Assumptions

- Existing signal detectors (activity_detector, pattern_analyzer, sentiment_analyzer) remain unchanged; the aggregation layer consumes their outputs.
- Weights and threshold are stored in configuration (e.g., config module); illustrative values (sentiment +2, price +2, volume +1, RSI +1, threshold) are starting points.
- Notification storage format may need extension to hold the structured explanation (metadata field or similar); the spec does not prescribe storage schema.
- RSI and pattern signals are available from existing components; if not yet implemented, those slots contribute 0 until implemented.
- No ML model; scoring is deterministic and rule-based.
- No UI changes; alerts are consumed by existing notification list/detail endpoints.
