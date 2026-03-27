# Implementation Plan: Leader-Follower Execution and Paper Trading

**Branch**: `011-leader-follower-execution-and-paper-trading` | **Date**: 2026-03-24
**Spec**: [spec.md](./spec.md)

## Summary

Add SQLAlchemy models `LeaderFollowerPaperRun` and `LeaderFollowerPaperTrade`, repositories, a deterministic simulation service that reads signals + price bars, persists runs/trades, and exposes REST endpoints plus a Typer CLI `simulate leader-follower`.

## Technical Context

- **Language**: Python 3.11+
- **Stack**: FastAPI, SQLAlchemy, SQLite
- **Inputs**: `LeaderFollowerSignalRepository` (date range), `PriceDataRepository` (OHLCV by date)
- **Testing**: pytest — unit tests for math/grouping; integration tests with in-memory DB + synthetic bars

## Constitution Check

- [x] Explicit failures — missing data → skip + count; API returns structured errors
- [x] Tests for new service, repos, API routes
- [x] Follow ARCHITECTURE: routes delegate to services; repos for persistence
- [x] CLI in `backend/app/cli.py` matches existing DB-backed CLI pattern (`backfill`)

## Project Structure

```text
specs/011-leader-follower-execution-and-paper-trading/
├── spec.md
├── plan.md
├── data-model.md
├── tasks.md
├── quickstart.md
└── contracts/
    └── paper-trading-api.md

backend/app/
├── models/
│   ├── leader_follower_paper_run.py
│   └── leader_follower_paper_trade.py
├── data/repositories/
│   ├── leader_follower_paper_run_repo.py
│   └── leader_follower_paper_trade_repo.py
├── services/
│   └── leader_follower_paper_trading_service.py
├── api/
│   └── leader_follower_paper_trading.py   # or extend leader_follower.py
└── cli.py                                  # simulate leader-follower

backend/tests/
├── test_leader_follower_paper_trading_service.py
└── test_leader_follower_paper_trading_api.py
```

## Key Algorithms

1. Load signals in `[start_date, end_date]` ordered deterministically.
2. Filter by `min_pair_score` on `strength_score`.
3. Group by `(leader_symbol, signal_date)`; rank; take top `max_positions_per_event`.
4. For each selected signal, resolve entry/exit prices from follower bars; skip if missing.
5. Compute returns and costs; append trade; update equity curve.
6. Persist run summary + trades in one transaction.

## Complexity / Risks

- **Trading calendar**: Derived from available `price_data` dates per symbol (no external calendar).
- **Performance**: Batch load price rows per symbol if needed; MVP may N+1 for clarity with tests covering correctness first.

---

## Phase 0 — Research

**Output**: [research.md](./research.md)

Resolved decisions: trading calendar source, determinism/tie-breaks, single round-trip cost, early-exit semantics. No blocking unknowns.

---

## Phase 1 — Design artifacts

**Output**: [data-model.md](./data-model.md), [contracts/paper-trading-api.md](./contracts/paper-trading-api.md), [quickstart.md](./quickstart.md)

---

## Constitution Check (post-design)

- [x] Explicit failures — skipped trades counted; API uses structured errors (`error_detail` / 404)
- [x] Tests — service + API tests added; `./scripts/verify.sh` passes
- [x] Layering — routes delegate to service; repos for persistence
- [x] Scope — no live trading; no duplicate paper-trade system beyond leader-follower simulation tables

**Complexity tracking**: None required.
