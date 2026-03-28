# Tasks: 013 Sector ETF confirmation

## Dependencies

`Setup → Map + sector service → PaperTradingConfig → paper core wire → model migration → API → grid keys → tests → verify`

---

## Phase 1: Setup

- [X] T001 Add static map `backend/app/data/stock_sector_etf_map.py` with `resolve_sector_etf(leader_symbol, override)`
- [X] T021 [P] Add `backend/app/services/sector_confirmation_service.py` with `evaluate_sector_confirmation(...)`

## Phase 2: Foundational

- [X] T003 Extend `PaperTradingConfig` in `backend/app/services/leader_follower_paper_trading_service.py` with sector fields and validation in `from_json_dict`
- [X] T004 [P] Extend `PaperSimulationMetrics` + `to_json_dict` with `skipped_sector_confirmation_count` in `backend/app/services/leader_follower_paper_trading_service.py`

## Phase 3: User Story 1 — Gate trades

- [X] T005 [US1] Add `_resolve_entry_date` and sector gate loop in `run_paper_trading_core` in `backend/app/services/leader_follower_paper_trading_service.py`
- [X] T006 [US1] Attach sector snapshot dict to trade payloads for persistence in `backend/app/services/leader_follower_paper_trading_service.py`

## Phase 4: User Story 4 — Persistence & API

- [X] T007 [US4] Add ORM columns on `backend/app/models/leader_follower_paper_trade.py` and `leader_follower_paper_run.py`
- [X] T008 [US4] Add `_migrate_leader_follower_paper_sector_fields` and register in `init_db` in `backend/app/data/database.py`
- [X] T009 [US4] Persist sector fields in `run_paper_trading_simulation` in `backend/app/services/leader_follower_paper_trading_service.py`
- [X] T010 [US4] Expose fields on paper-trading API models in `backend/app/api/leader_follower_paper_trading.py`

## Phase 5: User Story 3 — Grid

- [X] T011 [US3] Extend whitelist `ALLOWED_GRID_KEYS` in `backend/app/services/leader_follower_walk_forward_service.py`

## Phase 6: Tests & polish

- [X] T012 [P] Add `backend/tests/test_sector_confirmation_service.py`
- [X] T013 [P] Add sector gate coverage in `backend/tests/test_leader_follower_paper_trading_service.py` (`test_sector_confirmation_skips_trade_when_ma_fails`)
- [X] T014 Run `./scripts/verify.sh` from repo root
