# Tasks: Leader-Follower Execution and Paper Trading (011)

**Input**: `/specs/011-leader-follower-execution-and-paper-trading/`

## Phase 1 — Models and repositories

- [x] T001 Add `LeaderFollowerPaperRun` and `LeaderFollowerPaperTrade` SQLAlchemy models
- [x] T002 Add `LeaderFollowerPaperRunRepository` and `LeaderFollowerPaperTradeRepository`
- [x] T003 Extend `LeaderFollowerSignalRepository.list_signals` with optional unlimited date-range listing for simulation
- [x] T004 Add `PriceDataRepository` helpers: first bar on/after date; nth trading day from anchor (if not present)

## Phase 2 — Simulation service

- [x] T005 Implement `leader_follower_paper_trading_service.py`: config dataclass, grouping, ranking, entry/exit resolution, cost, equity curve, drawdown
- [x] T006 Unit tests: cost, gross/net, grouping, ranking tie-breaks, early_exit path

## Phase 3 — API

- [x] T007 Implement routes: `GET .../paper-trading/runs`, `GET .../{run_id}`, `GET .../{run_id}/equity-curve`
- [x] T008 Register router in `main.py`
- [x] T009 Integration tests for list/detail/equity + 404

## Phase 4 — CLI

- [x] T010 Add `simulate leader-follower` to `backend/app/cli.py`
- [x] T011 Document in [quickstart.md](./quickstart.md)

## Phase 5 — Verification

- [x] T012 `./scripts/verify.sh`
- [x] T013 Update `docs/ROADMAP.md` if this feature is tracked there

## Dependencies

| Phase | Depends on |
|-------|------------|
| 2 | 1 |
| 3 | 2 |
| 4 | 2 |
| 5 | 3, 4 |
