# Feature Specification: Combined Signal Alerts

**Feature Branch**: `002-combined-signal-alerts`
**Created**: 2026-03-13
**Status**: Draft
**ROADMAP**: Phase 2, Task 2.5 (combined-signal alerts), PRD FR-3.7
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

## Product Behavior: Combined vs. Individual Alerts

**Default behavior (safe rollout)**: Individual alerts (volume, price, sentiment) continue to be created as today. Combined alerts are created in addition when the combined score meets the threshold. Both coexist.

**When `combined_signal_alerts_only=true`**: Only combined alerts are created; individual alerts are suppressed. Use for rollout after validating combined behavior.

**Config name**: `combined_signal_alerts_only` (bool, default `false`).

**Migration/rollout**: Operators leave default (`false`) to preserve current behavior. Set to `true` when ready to rely solely on combined alerts. No data migration required; flag is runtime-only.

**Operator expectation**: With default, users see both individual and combined alerts. With `true`, users see only combined alerts (fewer, higher-quality).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST aggregate signals from **currently available** analysis components (sentiment, price, volume; RSI if present) per ticker before deciding whether to create a combined alert.
- **FR-002**: Each signal type MUST contribute to a weighted combined score; weights MUST be configurable.
- **FR-003**: Combined alerts MUST be generated only when the combined score meets or exceeds a configurable threshold.
- **FR-004**: Each combined alert MUST include structured metadata with evaluation_timestamp, combined_score, threshold, and signals_evaluated (all evaluated signals, with fired/contribution).
- **FR-005**: The aggregation layer MUST consume outputs from existing detectors. Lightweight adapter logic to normalize heterogeneous detector outputs is acceptable; detectors themselves are NOT modified.
- **FR-006**: Missing or unavailable signal sources MUST contribute 0 to the score; the system MUST NOT fabricate values. Volume-confirmation logic (ROADMAP 2.4) is out of scope unless already present.
- **FR-007**: Per-symbol evaluation failures MUST be logged and MUST NOT stop evaluation of other symbols or the job itself (per PRD §5.0).
- **FR-008**: When `combined_signal_alerts_only=false` (default), individual alerts continue to be created as today; combined alerts are created in addition. When `true`, only combined alerts are created.

### Key Entities

- **SignalEvaluated**: A single signal evaluated for a ticker. Has signal_type, raw_value, fired (bool), contribution, optional reason. All evaluated signals appear in metadata for debugging.
- **CombinedEvaluation**: The result of aggregating signals for a ticker. Includes signals_evaluated (all), combined_score, threshold, evaluation_timestamp, threshold_met.
- **Alert**: A notification when combined_score ≥ threshold. Includes signal_metadata with evaluation_timestamp, combined_score, threshold, signals_evaluated.

## Success Criteria *(mandatory)*

### Testable Scenario Matrix

| Scenario | Input | Expected Outcome | Test Method |
|----------|-------|------------------|-------------|
| One signal only | e.g., volume spike alone | No combined alert | Unit/integration test with mocked signals |
| Two+ signals, score below threshold | e.g., sentiment + volume, weights sum < threshold | No combined alert | Unit test |
| Two+ signals, score ≥ threshold | e.g., sentiment + volume + price, weights sum ≥ threshold | Combined alert created with signal_metadata | Unit/integration test |
| Missing signal input | One or more detectors return None | No crash; score computed from available signals only | Unit test with partial inputs |
| Per-symbol failure | Exception for symbol X | Logged; evaluation continues for other symbols | Integration test |
| Default config | `combined_signal_alerts_only=false` | Individual alerts created; combined alerts created when threshold met | Integration test |
| Combined-only config | `combined_signal_alerts_only=true` | Only combined alerts created; no individual alerts | Integration test |

### Measurable Outcomes

- **SC-001**: Combined alerts are generated only when combined_score ≥ threshold; single-signal-only cases produce no combined alert.
- **SC-002**: Every combined alert includes signal_metadata with evaluation_timestamp, combined_score, threshold, and signals_evaluated (including fired and contribution per signal).
- **SC-003**: Missing signal sources contribute 0; score is deterministically computed from available inputs.
- **SC-004**: Per-symbol failures do not cause job failure; the system continues evaluating other symbols.
- **SC-005**: With default config, individual alerts coexist with combined alerts; with combined-only config, only combined alerts are created.

## Assumptions

- Aggregation consumes **currently available** signals only: activity_detector (volume, price, sentiment), pattern_analyzer (RSI if present). Missing sources contribute 0.
- Volume-confirmed pattern logic (ROADMAP 2.4) is NOT in scope unless already present in the codebase.
- Detector outputs may be heterogeneous; lightweight adapter logic in combined_signal_service or notification_service to normalize into a common structure is acceptable. Detectors themselves are NOT modified.
- Weights and threshold in config.py; `combined_signal_alerts_only` controls rollout.
- Notification model extended with signal_metadata column (Text + JSON serialization; see data-model.md).
- No ML model; scoring is deterministic and rule-based.
- No UI changes; alerts consumed by existing notification list/detail endpoints.
