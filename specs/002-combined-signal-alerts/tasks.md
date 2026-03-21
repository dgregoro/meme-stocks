# Tasks: Combined Signal Alerts

**Input**: Design documents from specs/002-combined-signal-alerts/
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = Multi-signal alignment, US2 = Alert explanation
- Include exact file paths in descriptions

## Path Conventions

- Backend: `backend/app/`, `backend/tests/`
- Config: `backend/app/config.py`
- Migration: `backend/app/data/database.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config and schema extension

- [x] T001 Add combined signal config to backend/app/config.py: combined_signal_weight_sentiment, combined_signal_weight_price, combined_signal_weight_volume, combined_signal_weight_rsi (floats, defaults 2/2/1/1), combined_signal_threshold (float, default 4), combined_signal_alerts_only (bool, default False)
- [x] T002 Add signal_metadata column (Text, nullable) to notifications table via migration in backend/app/data/database.py; check column exists before adding; idempotent
- [x] T003 Add signal_metadata mapped_column to Notification model in backend/app/models/notification.py (Text, nullable=True)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Combined signal service with aggregation logic; serialization helpers; adapter for heterogeneous detectors

**Checkpoint**: combined_signal_service complete and testable before notification_service refactor

- [x] T004 [P] Create SignalEvaluated and CombinedEvaluation dataclasses in backend/app/services/combined_signal_service.py (signal_type, raw_value, fired, contribution, reason; symbol, signals_evaluated, combined_score, threshold, threshold_met, evaluation_timestamp)
- [x] T005 Add serialize_signal_metadata(ev: CombinedEvaluation) -> str and parse_signal_metadata(s: str | None) -> dict | None in backend/app/services/combined_signal_service.py; handle invalid/empty input (return None for parse)
- [x] T006 Add evaluate(signals: list[SignalEvaluated]) -> CombinedEvaluation in backend/app/services/combined_signal_service.py: sum contributions, compare to threshold from config; include all signals in signals_evaluated
- [x] T007 Add adapter logic in backend/app/services/combined_signal_service.py to normalize ActivitySignal and PriceTrend.rsi_signal into SignalEvaluated; missing/None inputs yield SignalEvaluated with fired=False, contribution=0
- [x] T008 Add unit tests in backend/tests/test_combined_signal_service.py: one signal => threshold_met False; two+ signals score < threshold => threshold_met False; two+ signals score >= threshold => threshold_met True; missing input => no crash; serialize/parse round-trip; parse invalid JSON => None

---

## Phase 3: User Story 1 - Alerts Only When Multiple Signals Align (Priority: P1)

**Goal**: Combined alerts created when combined_score >= threshold; single-signal cases produce no combined alert; feature flag controls individual vs combined-only behavior

**Independent Test**: Unit/integration tests: one signal => no combined alert; two+ score >= threshold => combined alert; combined_signal_alerts_only=false => individual + combined coexist; combined_signal_alerts_only=true => only combined

### Tests for User Story 1

- [x] T009 [P] [US1] Add test_one_signal_no_combined_alert in backend/tests/test_notification_service.py (mock single signal, assert no combined notification)
- [x] T010 [P] [US1] Add test_multiple_signals_above_threshold_creates_combined_alert in backend/tests/test_notification_service.py
- [x] T011 [P] [US1] Add test_per_symbol_failure_continues_others in backend/tests/test_notification_service.py or test_scheduler_service.py
- [x] T012 [P] [US1] Add test_combined_signal_alerts_only_false_coexist and test_combined_signal_alerts_only_true_suppress_individual in backend/tests/test_notification_service.py

### Implementation for User Story 1

- [x] T013 [US1] Refactor generate_notifications_for_stock in backend/app/services/notification_service.py: gather volume/price/sentiment from activity_detector, RSI from pattern_analyzer; normalize to SignalEvaluated via adapter; call combined_signal_service.evaluate
- [x] T014 [US1] When evaluation.threshold_met in backend/app/services/notification_service.py: create Notification with type='combined_signal', signal_metadata=serialize_signal_metadata(evaluation)
- [x] T015 [US1] When combined_signal_alerts_only=False: create individual notifications as today (volume, price, sentiment) AND combined when threshold met; when True: only create combined when threshold met
- [x] T016 [US1] Wrap per-symbol logic in try/except in notification_service or scheduler; log and continue on exception (FR-007)
- [x] T017 [US1] Build human-readable message for combined alert from signals_evaluated (fired signals summary) in backend/app/services/notification_service.py

**Checkpoint**: US1 complete; combined alerts created; feature flag works; per-symbol failure does not stop job

---

## Phase 4: User Story 2 - Alert Explanation (Priority: P2)

**Goal**: Combined alerts include signal_metadata with evaluation_timestamp, combined_score, threshold, signals_evaluated; API returns it

**Independent Test**: GET /api/notifications returns signal_metadata for type='combined_signal'; structure matches contract

### Tests for User Story 2

- [x] T018 [P] [US2] Add test_notification_api_returns_signal_metadata_for_combined_type in backend/tests/test_notification_service_api.py; verify evaluation_timestamp, combined_score, threshold, signals_evaluated shape

### Implementation for User Story 2

- [x] T019 [US2] Extend NotificationResponse in backend/app/api/notifications.py to include optional signal_metadata: dict | None (Pydantic model)
- [x] T020 [US2] When building response in backend/app/api/notifications.py: if n.signal_metadata, parse_signal_metadata(n.signal_metadata) and include in response; else null/omit
- [x] T021 [US2] Ensure datetime in signal_metadata serialized as ISO 8601 in backend/app/services/combined_signal_service.py serialize_signal_metadata

**Checkpoint**: US2 complete; API returns signal_metadata for combined alerts; structure matches contracts/notification-api.md

---

## Phase 5: Polish & Cross-Cutting

- [x] T022 Run ./scripts/verify.sh; fix any failures
- [x] T023 Update docs/ROADMAP.md tracking table: mark Phase 2 Task 2.5 (combined-signal alerts) complete when implemented
- [x] T024 Run pytest backend/tests/ --cov=backend/app; ensure no coverage regression on new code paths

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1: No dependencies
- Phase 2: Depends on Phase 1 (config, model column)
- Phase 3 (US1): Depends on Phase 2 (combined_signal_service)
- Phase 4 (US2): Depends on Phase 3 (combined alerts exist) and Phase 1 (signal_metadata column)
- Phase 5: Depends on Phases 1–4

### Within Phase 2

- T004 before T005, T006, T007 (dataclasses first)
- T005, T006, T007 can overlap
- T008 after T004–T007

### Within Phase 3

- T013–T017 are sequential (refactor → create combined → flag logic → per-symbol guard → message)
- Tests T009–T012 can run in parallel

### Within Phase 4

- T019 before T020
- T021 can be done with T005 (serialize)

### Parallel Opportunities

- T001, T002, T003 can run in parallel after planning
- T004, T009–T012, T018 are parallelizable within their phases
- T019 and T021 can overlap with other work

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (US1) — tests and implementation
4. **STOP and VALIDATE**: Trigger notification-check, list notifications, verify combined alerts and feature flag
5. Add Phase 4 (US2) for API metadata exposure

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Combined alerts created; feature flag works
3. Phase 4 → API exposes signal_metadata
4. Phase 5 → Verification and docs

---

## Summary

- **Total tasks**: 24 (T001–T024)
- **Phase 1**: 3 tasks (config, migration, model)
- **Phase 2**: 5 tasks (service, helpers, adapter, tests)
- **Phase 3 (US1)**: 9 tasks (4 test, 5 implementation)
- **Phase 4 (US2)**: 4 tasks (1 test, 3 implementation)
- **Phase 5**: 3 tasks (verify, docs, coverage)
- **MVP scope**: Phases 1–3 (combined alerts with feature flag)
- **Parallel opportunities**: T001–T003; T004; T009–T012; T018; T019
