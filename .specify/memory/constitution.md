# Meme-Stocks Project Constitution

<!--
Brownfield constitution v2.0.0 — reflects actual codebase state, not idealized design.
Ratification: 2026-03-19
-->

## 1. Purpose

### What the Application Does Today

Meme-stocks is a **decision-support tool** for retail investors analyzing meme stocks. It:

- **Ingests** Reddit posts (r/wallstreetbets, r/stocks, r/investing) and Yahoo Finance daily prices.
- **Derives** sentiment scores (keyword-based), price patterns (SMA, RSI), volume spikes, and daily aggregated Reddit features.
- **Signals** unusual activity (volume spike, price movement, sentiment shift) and combined multi-signal alerts via notifications.
- **Outputs** ranked daily analysis, paper trading (stocks and options), and a research API for causal/predictive experiments.

It does **not** execute trades. All trading is manual. Paper trading tracks hypothetical positions. The CLI is an API client and requires a running backend.

### Problems It Solves

1. **Information overload** — Automated Reddit and price collection reduces manual research time.
2. **Signal vs. noise** — Sentiment scoring, volume confirmation, and combined-signal thresholds help filter noise.
3. **Practice environment** — Paper trading enables strategy testing without risk.
4. **Research track** — Evaluation of whether Reddit activity predicts future price movement (lead-lag evidence), with leakage-safe datasets.

---

## 2. Current Architecture (AS-IS)

### High-Level Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| API | `backend/app/api/` | HTTP handling, delegates to services |
| Services | `backend/app/services/` | Business logic, orchestration, Reddit/Yahoo fetching |
| Clients | `backend/app/clients/` | **Only Alpaca** (minute bars); Reddit and Yahoo are in services |
| Repositories | `backend/app/data/repositories/` | Data access (CRUD) |
| Models | `backend/app/models/` | SQLAlchemy ORM |
| Utils | `backend/app/utils/` | Errors, ticker extraction, API error formatting |
| Feature store | `backend/app/feature_store/` | Parquet writer/reader for intraday bars |
| Frontend | `frontend/src/` | React, Vite, API client in `services/api.ts` |
| CLI | `backend/cli/` | HTTP client; no direct DB access |

### Data Flow

```
Reddit (PRAW) ──► RedditService ──► reddit_posts, reddit_symbol_mention
Yahoo (yfinance) ──► YahooFinanceService ──► price_data
Alpaca (optional) ──► AlpacaDataClient ──► parquet feature store (minute bars)

reddit_posts + price_data ──► sentiment_analyzer, pattern_analyzer ──► analysis (on-demand)
reddit_posts ──► reddit_daily_feature_service ──► reddit_daily_feature
price_data ──► label_service ──► price_labels
reddit_daily_feature + price_labels ──► dataset_builder_service ──► research datasets (CSV/parquet)

activity_detector + combined_signal_service ──► notifications
```

### Where State Is Stored

- **SQLite** — Default `sqlite:///./data/app.db`. All relational data: stocks, reddit_posts, reddit_symbol_mention, price_data, reddit_daily_feature, price_labels, notifications, paper_trades, symbol_universe, job_run_history, job_executions, job_locks, intraday_ingest_run, intraday_ingest_state.
- **Parquet** — `data/intraday/` (or `intraday_feature_store_root`). Partitioned by symbol/date. Append-only minute bars from Alpaca.
- **Research datasets** — `data/research/` (or `research_dataset_dir`). Output of build-dataset; input for experiments.

---

## 3. Engineering Principles

1. **Explicit failures over silence** — Never swallow exceptions. Log and surface meaningful errors. Return clear "no data" signals instead of fabricating defaults.

2. **Always add/update tests for backend logic** — Each new service, repository, or API endpoint must have at least one corresponding test. Target 80%+ line coverage on `backend/app`.

3. **Follow existing patterns unless a spec explicitly changes them** — Do not assume greenfield. New work integrates with the current architecture. Specs that require refactoring must say so.

4. **Minimize scope of changes** — Prefer minimal diffs. No broad rewrites without an explicit spec and approval. Touch the fewest files possible.

5. **Keep components loosely coupled** — Business logic in services, not in API routes. Return dataclasses from services, not ORM models. Repositories handle data access only.

---

## 4. Reliability Principles

Align with PRD §5.0:

- **No silent failures** — Handle network failures, invalid responses, and rate limiting for external APIs (Reddit, Yahoo, Alpaca) explicitly.
- **Explicit error surfaces** — Use `ExternalAPIError`, `DataAccessError`, `ValidationError`, `NotFoundError` as appropriate. API responses use structured format (PRD Appendix C); never expose raw stack traces.
- **Graceful degradation** — Background jobs must not crash the app on external API failure. Per-symbol failures (e.g., price fetch for invalid ticker) log and continue; one symbol must not stop the job.
- **Actionable error messages** — Include what failed, why (when known), and context (symbol, job name, subreddit).
- **Data integrity** — Missing/incomplete data → `None`, `[]`, or explicit "no data" response. Do not fabricate defaults.

**Jobs must be observable** — Every scheduled job records runs in `job_run_history` (or via `JobExecutionRepository`): last run, success/failure, error_message, duration_seconds, summary, metrics_json. The status API (`/api/status`) exposes job health and collection staleness. Failures must be detectable and debuggable. Avoid hidden background behavior.

---

## 5. Data & Signal Integrity

- **Clearly separate** raw data, derived features, and signals:
  - **Raw**: `reddit_posts`, `reddit_symbol_mention`, `price_data` — immutable after write.
  - **Derived**: `reddit_daily_feature`, `price_labels` — computed from raw; deterministic and reproducible.
  - **Signals**: `notifications` — outputs of activity_detector and combined_signal_service.

- **Do not overwrite raw data** — Reddit posts and price rows are additive. Parquet feature store is append-only.

- **Make transformations traceable** — Dataset builder writes metadata sidecar (git sha, date range, horizon). Experiments consume versioned datasets. Label computation uses explicit horizon logic without look-ahead.

- **Prefer reproducibility over cleverness** — Same inputs and config should produce identical datasets. Document assumptions.

---

## 6. Experimentation & Strategy Development

- **New trading ideas must start as experiments** — Not in production signals until validated.

- **Requirements for experiments**:
  - Hypothesis (e.g., "Reddit mention count predicts 5-day forward return")
  - Measurable success criteria
  - Backtest or evaluation plan (directionality, event study, predictiveness)

- **Do not promote signals to production without validation** — Research API (`/api/research`) supports build-dataset, directionality, event_study, predictiveness. Results are labeled as "lead-lag evidence," not proven causality. See `docs/CAUSAL_RESEARCH.md`.

---

## 7. Testing & Validation

- **Unit tests** — Core logic (sentiment, pattern analyzer, activity detector, pure functions). Use `@pytest.mark.unit`. Mock external deps.
- **Integration tests** — Data flows, jobs, API endpoints. Use `@pytest.mark.integration`. TestClient for API; mock Reddit/Yahoo/Alpaca where practical.
- **Deterministic behavior** — Prefer deterministic tests. Avoid flaky time-based or random assertions.
- **Entry point**: `pytest backend/tests/ -v`
- **Coverage**: `pytest backend/tests/ --cov=backend/app`
- **Verify before done**: `./scripts/verify.sh` (pre-commit + pytest + bandit + container check)

---

## 8. Incremental Development Model

- **New work** — Go through spec → plan → tasks (Spec Kit or equivalent). Integrate with existing system; do not replace it.
- **Refactors** — Must be scoped and justified. Update ROADMAP.md if scope changes. No drive-by renames or reorganizations unrelated to the task.
- **Allowed without ROADMAP update** (as long as external behavior does not change): refactors for testability, reliability/observability improvements, small scaffolding for planned items.

---

## 9. Observability & Debuggability

- **All scheduled jobs must**:
  - Record last run (via `JobExecutionRepository.record_run`)
  - Record status (success/failure, error_message)
  - Record key metrics (e.g., posts_inserted, symbols_mentioned, rows_inserted, notifications_generated)

- **System state inspectable** — Status API (`/api/status`) exposes:
  - Job status (last run, last success, last error, duration, summary)
  - Collection health (reddit, prices, daily features)
  - Stale symbols

- **Logging** — Error/warning for external API and job failures. Include correlation context (provider, endpoint, status) when possible. Do not log secrets.

---

## 10. Constraints / Non-Goals

- **No premature optimization** — Keep it simple until there is evidence of a bottleneck.
- **No full rewrites without explicit spec** — Incremental change preferred.
- **Avoid unnecessary infrastructure complexity** — No new message queues, caches, or services unless justified by a spec.
- **Current gaps (accepted for now)**:
  - Reddit and Yahoo are in services, not dedicated clients — `.cursorrules` say clients/ but only Alpaca uses clients/. New external APIs should use clients/.
  - No shared `retry.py` — Reddit/Yahoo use `backoff` inline; Alpaca has its own retry. Prefer extracting a shared helper when adding new API integrations.
  - Mypy in pre-commit may be disabled — Re-enable when config is fixed; do not remove type hints.

---

## Development Workflow

Before planning or implementing:

1. Read `docs/ROADMAP.md` (current phase and task)
2. Read `docs/PRD.md` §5.0 and Appendix C
3. Read `docs/ARCHITECTURE.md` for patterns

For Spec Kit: Specs complement existing docs. Constitution and `.cursorrules` both apply. Use `docs/BROWNFIELD_SPEC_KIT.md` for Spec Kit usage.

---

## Governance

- This constitution supersedes ad-hoc guidance for conflicting cases.
- Amendments require a version bump and clear changelog.
- Versioning: PATCH (clarifications), MINOR (new principles), MAJOR (backward-incompatible changes).

**Version**: 2.0.0 | **Ratified**: 2026-03-19 | **Last Amended**: 2026-03-19
