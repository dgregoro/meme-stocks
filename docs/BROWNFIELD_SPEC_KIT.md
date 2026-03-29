# Brownfield Spec Kit Context for Meme-Stocks

This document provides context for AI agents creating or implementing specs in this repo. Read it before writing or executing specs.

## Project Overview

Meme-stocks is a **decision-support tool** for retail investors analyzing meme stocks using Reddit sentiment and price data. It does not execute trades. Backend (FastAPI/Python) + frontend (React/Vite).

## Architecture

| Layer      | Location                         | Responsibility                          |
|-----------|-----------------------------------|-----------------------------------------|
| API       | `backend/app/api/`               | HTTP handling, delegates to services    |
| Services  | `backend/app/services/`          | Business logic, orchestration            |
| Repos     | `backend/app/data/repositories/`| Data access only                         |
| Models    | `backend/app/models/`            | SQLAlchemy ORM                           |
| Clients   | `backend/app/clients/`           | External APIs (Reddit, Yahoo, Alpaca)   |
| Frontend  | `frontend/src/`                  | React, Vite, API client in `services/api.ts` |
| CLI       | `backend/cli/`                   | API client; no direct DB access          |

**Data flow**: Reddit/Yahoo → clients → services → repos → DB. Scheduler jobs run ingestion and analysis. Frontend and CLI call REST API.

## Key Docs

| Doc                  | Purpose                                  |
|----------------------|------------------------------------------|
| `docs/PURPOSE.md`    | North star: research → edge or kill → execution |
| `docs/ROADMAP.md`    | Phases, tasks, agent instructions        |
| `docs/PRD.md`        | Requirements, reliability (§5.0), errors (App. C) |
| `docs/ARCHITECTURE.md`| Patterns, how to add features           |
| `docs/PLAN.md`       | Business logic, algorithms               |
| `docs/CAUSAL_RESEARCH.md` | Lead-lag research methodology     |

## Testing

- **Entry point**: `pytest backend/tests/ -v`
- **Coverage**: `pytest backend/tests/ --cov=backend/app`
- **Verify**: `./scripts/verify.sh` (pre-commit + pytest)
- **Unit vs integration**: `@pytest.mark.unit`, `@pytest.mark.integration`

## Local Dev

- **Backend**: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` (from project root)
- **Frontend**: `cd frontend && npm run dev` (port 5173)
- **Containers**: `podman-compose up --build` or `docker compose up --build`
- **Config**: `.env` at root; `backend/app/config.py` for all settings

## Spec-Friendly Conventions

- New feature: Model → Repository → Service → API Route → Tests
- Register routers in `backend/app/main.py`
- Add thresholds to `config.py`, not as literals
- Use `backend/app/utils/errors.py` for typed exceptions
- API errors: structured format per PRD Appendix C

## Research / Causal Work

Any predictive or causal analysis must avoid look-ahead bias. Document assumptions. Label outputs as "lead-lag evidence," not causality. See `docs/CAUSAL_RESEARCH.md`.
