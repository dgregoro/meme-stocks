# Implementation Plan: Leader-follower sector ETF confirmation

**Branch**: `013-leader-follower-sector-etf-confirmation` | **Date**: 2026-03-27 | **Spec**: [spec.md](./spec.md)

## Summary

Add optional **sector ETF confirmation** to leader-follower **paper trading execution**: static `leader_symbol → ETF` map, daily **ma_above / rolling_return / combined** checks via `PriceDataRepository`, gate before opening follower trades, persist sector snapshot on `leader_follower_paper_trades`, extend `PaperTradingConfig` and **`010`/`012`** grid keys. Default **off**; unmapped leaders **pass with warning**; insufficient ETF history **fails gate** (skip).

## Technical Context

**Language/Version**: Python 3.11
**Dependencies**: SQLAlchemy, FastAPI, existing `PriceDataRepository`, `PaperTradingConfig`
**Storage**: SQLite; additive columns on `leader_follower_paper_trades` + `_migrate_*` in `database.py`
**Testing**: pytest unit tests for sector math + paper trading path
**Target**: Linux; backend API + CLI `simulate leader-follower` unchanged signature (config JSON carries sector fields)

## Constitution Check

| Gate | Status |
|------|--------|
| Explicit failures | Log warnings (unmapped); skip with conservative rules for missing ETF data |
| Tests | New tests for sector service + paper trading gating |
| Patterns | Logic in `sector_confirmation_service`; wire in `leader_follower_paper_trading_service` |
| Minimal scope | No ML; no new ingestion; map module + gate only |

**Post-design**: API adds nullable fields to `PaperTradeOut`; grid keys centralized in `ALLOWED_GRID_KEYS`.

## Project Structure

```text
specs/013-leader-follower-sector-etf-confirmation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── paper-trading-sector-fields.md
└── tasks.md

backend/app/
├── data/
│   └── stock_sector_etf_map.py          # STATIC map dict + resolver
├── services/
│   ├── sector_confirmation_service.py    # evaluate gate + snapshots
│   └── leader_follower_paper_trading_service.py  # wire gate, metrics
├── services/leader_follower_walk_forward_service.py  # ALLOWED_GRID_KEYS
├── models/leader_follower_paper_trade.py
├── data/database.py                      # migration
└── api/leader_follower_paper_trading.py # response fields

backend/tests/
├── test_sector_confirmation_service.py
└── test_leader_follower_paper_trading_sector_gate.py
```

**Structure Decision**: Brownfield `backend/app` only; no new tables.

## Complexity Tracking

None.
