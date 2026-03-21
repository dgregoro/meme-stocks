# Tasks: Leader-Follower Signal Detection

**Input**: Design documents from specs/003-leader-follower-signal-detection/
**Prerequisites**: plan.md, spec.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = Leader Event Detection, US2 = Follower Candidate Selection, US3 = Opportunity Signal Generation
- Include exact file paths in descriptions

## Path Conventions

- Backend: `backend/app/`, `backend/tests/`
- Config: `backend/app/config.py`
- Models: `backend/app/models/`
- Database: `backend/app/data/database.py`
- Main: `backend/app/main.py`

---

## Phase 1: Setup (Config, Models, Migration)

**Purpose**: Add config keys, create models, register in init_db. Blocks all subsequent work.

- [X] T001 Add leader_follower config to backend/app/config.py: leader_follower_enabled (bool, default False), leader_return_threshold_pct (float, default 5.0), leader_volume_spike_threshold (float, default 1.5), leader_follower_cooldown_days (int, default 1), follower_move_threshold_pct (float, default 3.0), leader_follower_job_hour (int, default 17), leader_follower_strength_weight_return (float, default 0.6), leader_follower_strength_weight_volume (float, default 0.4), leader_follower_norm_return_cap_pct (float, default 15.0), leader_follower_norm_volume_cap (float, default 4.0)
- [X] T002 [P] Create StockGroup model in backend/app/models/stock_group.py: id, group_id, stock_symbol (FK stocks.symbol), created_at; unique (group_id, stock_symbol)
- [X] T003 [P] Create LeaderEvent model in backend/app/models/leader_event.py: id, leader_symbol (FK stocks.symbol), event_date, return_pct, volume_ratio, direction ('up'|'down'), created_at
- [X] T004 [P] Create LeaderFollowerSignal model in backend/app/models/leader_follower_signal.py: id, leader_symbol (FK), follower_symbol (FK), group_id, signal_date, strength_score, leader_return_pct, leader_volume_ratio, metrics_json (Text nullable), created_at
- [X] T005 Register StockGroup, LeaderEvent, LeaderFollowerSignal in backend/app/main.py imports (models section) so Base.metadata.create_all picks them up
- [X] T006 Verify new tables created on init_db: stock_groups, leader_events, leader_follower_signals

---

## Phase 2: Foundational (Repositories, Group Loading)

**Purpose**: Repositories and group parsing. Required before leader detection and follower selection.

**Checkpoint**: Repos and group loader ready before user story implementation

- [X] T007 [P] Create StockGroupRepository in backend/app/data/repositories/stock_group_repo.py: get_groups_for_symbol(symbol) -> list[str] (ordered); get_symbols_in_group(group_id) -> list[str]; add(StockGroup)
- [X] T008 [P] Create LeaderEventRepository in backend/app/data/repositories/leader_event_repo.py: add(LeaderEvent), list_by_date(date), list_recent(limit)
- [X] T009 [P] Create LeaderFollowerSignalRepository in backend/app/data/repositories/leader_follower_signal_repo.py: add(LeaderFollowerSignal), exists_within_cooldown(leader, follower, since_date, cooldown_days), list_signals(limit, since_date, leader, group)
- [X] T010 Add load_symbol_to_primary_group_map(stock_group_repo) -> dict[str, str] in backend/app/services/leader_follower_service.py: for each symbol, primary group = lexicographically smallest group_id; return symbol -> primary_group_id
- [X] T011 Add unit test in backend/tests/test_leader_follower_service.py: load_symbol_to_primary_group_map with symbol in multiple groups returns smallest group_id

---

## Phase 3: User Story 1 - Leader Event Detection (Priority: P1) 🎯 MVP

**Goal**: Detect significant price/volume moves; create LeaderEvent records; per-symbol failures do not stop job

**Independent Test**: Seed price_data with known move; run leader detection; assert LeaderEvent created with correct return_pct, volume_ratio, direction

### Tests for User Story 1

- [X] T012 [P] [US1] Add test_leader_detected_when_return_and_volume_exceed_threshold in backend/tests/test_leader_follower_service.py: seed price_data (day1 close 100, day2 close 106, volume 2x avg); assert leader detected
- [X] T013 [P] [US1] Add test_no_leader_when_return_below_threshold in backend/tests/test_leader_follower_service.py: small move; assert no leader
- [X] T014 [P] [US1] Add test_no_leader_when_volume_below_threshold in backend/tests/test_leader_follower_service.py: return qualifies but volume does not; assert no leader
- [X] T015 [P] [US1] Add test_per_symbol_failure_continues_others in backend/tests/test_leader_follower_service.py: one symbol has no data; assert others evaluated; errors_count in metrics

### Implementation for User Story 1

- [X] T016 [US1] Add compute_event_date(price_repo, stock_repo) -> date | None in backend/app/services/leader_follower_service.py: max(price_data.date) across tracked symbols; return None if empty
- [X] T017 [US1] Add detect_leaders(db, event_date) -> list[LeaderEvent] in backend/app/services/leader_follower_service.py: get universe from StockRepository; for each symbol fetch PriceDataRepository.list_for_stock; require min 5 bars; compute return_pct and volume_ratio; apply BOTH thresholds; create LeaderEvent; per-symbol try/except with log and continue
- [X] T018 [US1] Persist LeaderEvent via LeaderEventRepository in backend/app/services/leader_follower_service.py detect_leaders; return list of created events
- [X] T019 [US1] Add leader detection unit tests for edge cases: insufficient bars skipped; multiple leaders; direction up vs down based on return sign

**Checkpoint**: US1 complete; leader detection produces LeaderEvent records; per-symbol failure isolated

---

## Phase 4: User Story 2 - Follower Candidate Selection (Priority: P2)

**Goal**: For each LeaderEvent, identify follower candidates in same group that have not moved; exclude already-moved symbols

**Independent Test**: Create LeaderEvent; provide group {A,B,C}; B moved, C did not; assert C is candidate, B excluded

### Tests for User Story 2

- [X] T020 [P] [US2] Add test_follower_candidate_excluded_when_already_moved in backend/tests/test_leader_follower_service.py: leader A, stock_groups {A,B,C} in group; B has return >= follower_move_threshold; assert B excluded
- [X] T021 [P] [US2] Add test_follower_candidate_included_when_not_moved in backend/tests/test_leader_follower_service.py: leader A, stock_groups {A,B,C}; C has small return; assert C is candidate
- [X] T022 [P] [US2] Add test_no_candidates_when_no_group_mapping in backend/tests/test_leader_follower_service.py: leader not in stock_groups; assert empty candidates

### Implementation for User Story 2

- [X] T023 [US2] Add select_follower_candidates(leader_event, stock_group_repo, price_repo, event_date) -> list[tuple[str,str]] in backend/app/services/leader_follower_service.py: get group members from StockGroupRepository (primary group = lex smallest group_id); exclude leader; for each candidate fetch price_data for event_date; compute return; exclude if abs(return) >= follower_move_threshold; return (follower_symbol, group_id) list
- [X] T024 [US2] Add select_follower_candidates for symbols with no price data: skip and do not crash; log

**Checkpoint**: US2 complete; follower candidates correctly excluded when already moved

---

## Phase 5: User Story 3 - Opportunity Signal Generation (Priority: P3)

**Goal**: Create LeaderFollowerSignal from leader + candidates; deduplicate by cooldown; persist; record run metrics; scheduler job with safeguards; API endpoint

**Independent Test**: Run full pipeline; assert signal created; GET /api/leader-follower/signals returns it; job_run_history has metrics

### Tests for User Story 3

- [X] T025 [P] [US3] Add test_signal_created_with_correct_fields in backend/tests/test_leader_follower_service.py: leader + candidates; run signal generation; assert LeaderFollowerSignal has leader_symbol, follower_symbol, group_id, strength_score (weighted combo), leader_return_pct
- [X] T026 [P] [US3] Add test_deduplication_skips_duplicate_within_cooldown in backend/tests/test_leader_follower_service.py: insert signal for (A,B); run again within 1-day cooldown; assert no duplicate
- [X] T027 [P] [US3] Add test_leader_follower_api_list_signals in backend/tests/test_leader_follower_api.py: GET /api/leader-follower/signals returns list; query params limit, since_date, leader, group work
- [X] T028 [P] [US3] Add test_scheduler_job_has_overlap_safeguards in backend/tests/test_scheduler_service.py or test_leader_follower_service.py: verify leader_follower_detection job registered with max_instances=1, coalesce=True, misfire_grace_time=1800

### Implementation for User Story 3

- [X] T029 [US3] Add compute_strength_score(return_pct, volume_ratio, config) -> float in backend/app/services/leader_follower_service.py: norm each to [0,1] using caps; w_r*norm_return + w_v*norm_volume; clamp to [0,1]
- [X] T030 [US3] Add create_signals(leader_events, candidates_map, signal_repo, cooldown_days, event_date) in backend/app/services/leader_follower_service.py: for each (leader, candidate, group_id) check exists_within_cooldown; if not, create LeaderFollowerSignal with strength_score from compute_strength_score; persist
- [X] T031 [US3] Add run_detection(db) -> dict in backend/app/services/leader_follower_service.py: compute_event_date; detect_leaders; load symbol->primary_group; select_follower_candidates per leader; create_signals; return metrics (input_universe_size, leader_events_detected, follower_candidates_found, signals_emitted, symbols_skipped, errors_count)
- [X] T032 [US3] Add _leader_follower_detection_job in backend/app/services/scheduler_service.py: SessionLocal; started_at; try run_detection; JobExecutionRepository.record_run with metrics, summary; on exception _record_job_failure
- [X] T033 [US3] Add leader_follower_detection job to _schedule_jobs in backend/app/services/scheduler_service.py: gated by leader_follower_enabled; CronTrigger(hour=leader_follower_job_hour, minute=0); id=leader_follower_detection; max_instances=1; coalesce=True; misfire_grace_time=1800
- [X] T034 [US3] Create backend/app/api/leader_follower.py: APIRouter prefix /api/leader-follower; GET /signals with limit, since_date, leader, group query params; use LeaderFollowerSignalRepository; return Pydantic response per contracts/leader-follower-api.md
- [X] T035 [US3] Register leader_follower router in backend/app/main.py: include_router(leader_follower_api.router)

**Checkpoint**: US3 complete; full pipeline runs; signals persisted; API returns them; scheduler has overlap protection. Job gated by leader_follower_enabled in T033.

---

## Phase 6: Polish & Cross-Cutting

- [X] T036 Run ./scripts/verify.sh; fix any failures
- [ ] T037 Update docs/ROADMAP.md: add leader-follower-signal-detection to tracking table when implemented
- [X] T038 Run pytest backend/tests/ --cov=backend/app; ensure no coverage regression on new code paths

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1: No dependencies
- Phase 2: Depends on Phase 1 (models exist)
- Phase 3 (US1): Depends on Phase 1, 2 (repos; StockGroupRepository needed for Phase 4, not US1)
- Phase 4 (US2): Depends on Phase 3 (LeaderEvent exists), Phase 2 (StockGroupRepository, load_symbol_to_primary_group_map)
- Phase 5 (US3): Depends on Phases 1–4
- Phase 6: Depends on Phases 1–5

### Within Phase 1

- T001 first; T002, T003, T004 parallel; T005 after models; T006 last

### Within Phase 2

- T007, T008, T009 parallel; T010 after T008 (needs StockGroupRepository); T011 after T010

### Within Phase 3

- T016–T019 sequential; T012–T015 (tests) can run in parallel

### Within Phase 4

- T023–T024 sequential; T020–T022 (tests) parallel

### Within Phase 5

- T029–T035 sequential; T025–T028 (tests) parallel

### Parallel Opportunities

- T002, T003, T004; T007, T008, T009; T012–T015; T020–T022; T025–T028

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (US1) — leader detection
4. **STOP and VALIDATE**: Run detection with seeded data; verify LeaderEvent created
5. Add Phase 4 (US2) for follower selection
6. Add Phase 5 (US3) for signals, scheduler, API
7. Phase 6 verification

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Leader events detected and persisted
3. Phase 4 → Follower candidates selected
4. Phase 5 → Signals, job, API; full pipeline
5. Phase 6 → Verification and docs

---

## Summary

- **Total tasks**: 38 (T001–T038)
- **Phase 1**: 6 tasks (config, models: StockGroup, LeaderEvent, LeaderFollowerSignal)
- **Phase 2**: 5 tasks (StockGroupRepository, LeaderEventRepository, LeaderFollowerSignalRepository, load_symbol_to_primary_group_map)
- **Phase 3 (US1)**: 8 tasks (4 test, 4 implementation including compute_event_date)
- **Phase 4 (US2)**: 5 tasks (3 test, 2 implementation)
- **Phase 5 (US3)**: 11 tasks (4 test, 7 implementation including compute_strength_score)
- **Phase 6**: 3 tasks (verify, docs, coverage)
- **MVP scope**: Phases 1–3 (leader detection only; then add 4–5 for full pipeline)
- **Parallel opportunities**: T002–T004; T007–T009; T012–T015; T020–T022; T025–T028
