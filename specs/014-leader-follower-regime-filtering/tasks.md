# Tasks: 014 Leader-follower regime filtering

## Dependencies

`Regime service → PaperTradingConfig → paper core wire → ORM migration → API/CLI → ALLOWED_GRID_KEYS → tests → verify`

---

## Phase 1: Setup

- [X] T001 Add `backend/app/services/regime_filter_service.py` with `RegimeFilterParams`, `evaluate_regime_filter(price_repo, decision_date, params) -> (allowed, snapshot_dict)`
- [X] T002 [P] Add unit tests `backend/tests/test_regime_filter_service.py` for MA uptrend, vol threshold, insufficient history → fail

## Phase 2: Foundational

- [X] T003 Extend `PaperTradingConfig` in `backend/app/services/leader_follower_paper_trading_service.py` with regime fields and validation in `from_json_dict` (incl. sector-strength requires 013)
- [X] T004 [P] Extend `PaperSimulationMetrics` + `to_json_dict` with `skipped_regime_filter_count` in `backend/app/services/leader_follower_paper_trading_service.py`

## Phase 3: User Story 1 — Gate trades

- [X] T005 [US1] After sector gate (013), apply regime gate using `_resolve_entry_date` / decision date in `run_paper_trading_core` in `backend/app/services/leader_follower_paper_trading_service.py`
- [X] T006 [US1] Attach regime snapshot keys to trade payloads for persistence in `backend/app/services/leader_follower_paper_trading_service.py`

## Phase 4: User Story 4 — Persistence & API

- [X] T007 [US4] Add ORM columns on `backend/app/models/leader_follower_paper_trade.py` and `backend/app/models/leader_follower_paper_run.py`
- [X] T008 [US4] Add `_migrate_leader_follower_paper_regime_fields` and register in `init_db` in `backend/app/data/database.py`
- [X] T009 [US4] Persist regime fields in `run_paper_trading_simulation` in `backend/app/services/leader_follower_paper_trading_service.py`
- [X] T010 [US4] Expose regime fields on API models in `backend/app/api/leader_follower_paper_trading.py` per `specs/014-leader-follower-regime-filtering/contracts/paper-trading-regime-fields.md`

## Phase 5: User Story 2 & 3 — Config & grids

- [X] T011 [US2] [US3] Extend `ALLOWED_GRID_KEYS` in `backend/app/services/leader_follower_walk_forward_service.py` with regime keys from `data-model.md`
- [X] T012 [US2] Add Typer options on `simulate leader-follower` in `backend/app/cli.py` for regime filter (mirror 013 pattern)

## Phase 6: Tests & polish

- [X] T013 [P] Add integration test path in `backend/tests/test_leader_follower_paper_trading_service.py` for regime skip when benchmark below MA
- [X] T014 Run `./scripts/verify.sh` from repo root (pre-commit + pytest: 358 passed; container step may run separately)
