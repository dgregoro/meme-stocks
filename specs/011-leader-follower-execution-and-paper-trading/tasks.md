# Tasks: Leader-Follower Execution and Paper Trading (011)

**Input**: `/specs/011-leader-follower-execution-and-paper-trading/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Status**: All tasks below are **implemented** and verified (2026-03-24). This file matches the Speckit user-story layout for traceability.

## Phase 1: Setup (shared)

**Purpose**: Register models and wire imports so schema creation and tests see new tables.

- [x] T001 [P] Import `LeaderFollowerPaperRun` / `LeaderFollowerPaperTrade` in `backend/app/main.py` for metadata registration
- [x] T002 [P] Import paper-trading models in `backend/app/cli.py` model import block for `init_db()`

---

## Phase 2: Foundational (blocking)

**Purpose**: Persistence and data access required before simulation or APIs.

**Checkpoint**: Repositories and price/signal listing support simulation batch loads.

- [x] T003 Add SQLAlchemy models `backend/app/models/leader_follower_paper_run.py` and `backend/app/models/leader_follower_paper_trade.py`
- [x] T004 [P] Add `backend/app/data/repositories/leader_follower_paper_run_repo.py`
- [x] T005 [P] Add `backend/app/data/repositories/leader_follower_paper_trade_repo.py`
- [x] T006 Extend `LeaderFollowerSignalRepository.list_signals` with `limit: int | None` in `backend/app/data/repositories/leader_follower_signal_repo.py`
- [x] T007 Add `PriceDataRepository.list_dates_for_symbol` in `backend/app/data/repositories/price_data_repo.py`

---

## Phase 3: User Story 1 — Simulated trades after costs (Priority: P1)

**Goal**: Persist trades with entry/exit, gross/net returns, skips on missing bars.

**Independent test**: Run simulation on synthetic bars + one signal; assert one trade with expected returns and `skipped_count` when bars missing.

- [x] T008 [US1] Implement `run_paper_trading_simulation` and helpers in `backend/app/services/leader_follower_paper_trading_service.py`
- [x] T009 [US1] Unit tests in `backend/tests/test_leader_follower_paper_trading_service.py` (cost, drawdown, next_open path)

---

## Phase 4: User Story 2 — Configurable execution and event caps (Priority: P2)

**Goal**: Configurable entry/exit modes, `holding_days`, `max_positions_per_event`, optional `min_pair_score`; deterministic ranking per event.

**Independent test**: Two signals same event, `max_positions_per_event=1` keeps higher strength; different entry modes change prices.

- [x] T010 [US2] Event grouping and ranking in `backend/app/services/leader_follower_paper_trading_service.py`
- [x] T011 [US2] Unit test `test_max_positions_per_event_keeps_stronger_signal` in `backend/tests/test_leader_follower_paper_trading_service.py`

---

## Phase 5: User Story 3 — Portfolio metrics and retrieval (Priority: P3)

**Goal**: Cumulative return, drawdown, win rate; list/detail/equity HTTP API; structured 404.

**Independent test**: HTTP list/detail/equity + 404 in `backend/tests/test_leader_follower_paper_trading_api.py`

- [x] T012 [US3] FastAPI routes in `backend/app/api/leader_follower_paper_trading.py`
- [x] T013 [US3] Register router in `backend/app/main.py`
- [x] T014 [US3] Integration tests in `backend/tests/test_leader_follower_paper_trading_api.py`

---

## Phase 6: CLI and docs

- [x] T015 Add `simulate leader-follower` command in `backend/app/cli.py`
- [x] T016 Document flows in `specs/011-leader-follower-execution-and-paper-trading/quickstart.md`
- [x] T017 Update `docs/ROADMAP.md` (Phase 3.8) for this feature

---

## Phase 7: Polish & verification

- [x] T018 Run `./scripts/verify.sh` (pre-commit + pytest)
- [x] T019 Add `lf_*.json` to `.gitignore` for local evaluation dumps (repo root)

---

## Dependencies & execution order

| Phase | Depends on |
|-------|------------|
| 2 | 1 |
| 3–5 | 2 |
| 6 | 3–5 |
| 7 | 6 |

### User story order

- **US1** → core simulation and persistence
- **US2** → configuration and selection (same service module)
- **US3** → HTTP surface and equity curve

### Parallel opportunities

- T001/T002; T004/T005; tests T009/T011 can run after service is stable.

### MVP scope

Deliver **Phase 3 (US1)** first for a minimal “trades + net P&L” slice; add US2/US3 for full feature parity.
