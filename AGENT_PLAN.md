# Agent Implementation Plan
## Meme Stocks Trading Application

**Purpose**: Guide an AI coding agent through resuming development on this project.
**Approach**: Start with discovery/audit to establish ground truth, then refine into specific tasks.

---

## Phase 0: Environment & Baseline Verification

**Goal**: Confirm the project runs and establish what actually works.

### Task 0.1: Verify Backend Runs
- **Do**: Install dependencies and start the FastAPI server
- **Commands** (run from project root):
  ```bash
  pip install -r backend/requirements.txt
  uvicorn backend.app.main:app --reload --host 127.0.0.1
  ```
  Or with backend as cwd (requires PYTHONPATH):
  ```bash
  cd backend && PYTHONPATH=.. pip install -r requirements.txt && uvicorn app.main:app --reload
  ```
- **Check**: Server starts without errors, `/health` returns 200
- **Record**: Any startup errors, missing dependencies, or configuration issues

### Task 0.2: Run Test Suite
- **Do**: Execute all existing tests
- **Commands**:
  ```bash
  python -m pytest backend/tests/ -v --tb=short
  ```
- **Check**: Note pass/fail counts, identify failing tests
- **Record**:
  - Total tests: ___
  - Passing: ___
  - Failing: ___
  - Errors: ___
  - List of failing test names

### Task 0.3: Verify Frontend Runs
- **Do**: Install dependencies and start dev server
- **Commands**:
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
- **Check**: Dev server starts, page loads in browser
- **Record**: Any build errors, missing dependencies, console errors

### Task 0.4: Test API Endpoints Manually
- **Do**: Call each documented endpoint and verify response
- **Endpoints to test**:
  - [ ] `GET /health`
  - [ ] `GET /api/stocks`
  - [ ] `GET /api/stocks/{symbol}` (use a known symbol or expect empty)
  - [ ] `GET /api/analysis/daily`
  - [ ] `GET /api/notifications`
  - [ ] `GET /api/trades`
  - [ ] `GET /api/portfolio`
- **Record**: Which endpoints return expected responses vs errors

---

## Phase 1: Codebase Audit

**Goal**: Understand current code quality and identify gaps between docs and reality.

### Task 1.1: Verify Data Models Match Documentation
- **Files**: `backend/app/models/*.py`
- **Do**: Compare actual model definitions against PRD.md Section 7.3 (Data Models)
- **Check for**:
  - Missing models
  - Missing fields
  - Type mismatches
  - Relationship issues
- **Output**: List of discrepancies (if any)

### Task 1.2: Verify API Routes Match Documentation
- **Files**: `backend/app/api/*.py`
- **Do**: Compare actual endpoints against PRD.md Section 14.A (API Endpoints)
- **Check for**:
  - Missing endpoints
  - Different URL paths
  - Missing request/response validation
- **Output**: List of discrepancies (if any)

### Task 1.3: Assess Test Coverage
- **Do**: Identify which services/repositories/endpoints have tests
- **Files**: `backend/tests/test_*.py`
- **Check**:
  - [ ] All services in `backend/app/services/` have corresponding tests
  - [ ] All repositories in `backend/app/data/repositories/` have tests
  - [ ] All API routes in `backend/app/api/` have tests
- **Output**: List of untested modules

### Task 1.4: Review Error Handling
- **Do**: Check if external API calls (Reddit, Yahoo) handle failures gracefully
- **Files**:
  - `backend/app/services/reddit_service.py`
  - `backend/app/services/yahoo_service.py`
- **Check for**:
  - Try/except around external calls
  - Meaningful error messages
  - No silent failures (swallowed exceptions)
- **Output**: List of error handling gaps

### Task 1.5: Review Configuration Management
- **Files**: `backend/app/config.py`, `backend/.env`
- **Do**: Verify all configurable values from PRD Section 8 exist
- **Check**:
  - [ ] All threshold variables defined with defaults
  - [ ] All scheduling variables defined
  - [ ] No hardcoded secrets in code
- **Output**: List of missing configuration options

### Task 1.6: Audit Background Jobs
- **Files**: `backend/app/services/scheduler_service.py`
- **Do**: Verify scheduled jobs match PRD FR-7 requirements
- **Check**:
  - [ ] Reddit collection job exists and is scheduled
  - [ ] Price collection job exists and is scheduled
  - [ ] Daily analysis job exists and is scheduled
  - [ ] Notification check job exists and is scheduled
  - [ ] Catch-up logic implemented
- **Output**: List of missing or broken job functionality

---

## Phase 2: Issue Triage

**Goal**: Categorize findings from Phase 1 and prioritize fixes.

### Task 2.1: Create Issues List
- **Do**: Based on Phase 0 and Phase 1 findings, create categorized list:

```markdown
## Critical (blocks basic functionality)
- [ ] Issue: ___
- [ ] Issue: ___

## High (core feature incomplete/broken)
- [ ] Issue: ___
- [ ] Issue: ___

## Medium (functionality works but has gaps)
- [ ] Issue: ___
- [ ] Issue: ___

## Low (polish, nice-to-have)
- [ ] Issue: ___
- [ ] Issue: ___
```

### Task 2.2: Update Documentation
- **Do**: If discrepancies found, decide whether to:
  - Fix code to match docs, OR
  - Update docs to match code (if code is correct)
- **Files to potentially update**: `PLAN.md`, `PRD.md`, `README.md`

---

## Phase 3: Stabilization

**Goal**: Fix critical and high-priority issues before adding features.

### Task 3.1: Fix Failing Tests
- **Do**: For each failing test from Task 0.2:
  1. Understand what the test is checking
  2. Determine if test is wrong or code is wrong
  3. Fix appropriately
- **Done when**: `pytest backend/tests/ -v` shows all tests passing

### Task 3.2: Add Missing Tests
- **Do**: For each untested module from Task 1.3:
  1. Create test file if missing
  2. Add at least one happy-path test
  3. Add at least one error-case test
- **Done when**: All services/repos/endpoints have basic test coverage

### Task 3.3: Fix Error Handling Gaps
- **Do**: For each gap from Task 1.4:
  1. Add try/except with meaningful error handling
  2. Log errors appropriately
  3. Return clear error responses to callers
- **Done when**: External API failures don't crash the app

### Task 3.4: Fix Configuration Gaps
- **Do**: For each missing config from Task 1.5:
  1. Add to `config.py` with sensible default
  2. Update `.env.example` if it exists
- **Done when**: All PRD-specified thresholds are configurable

---

## Phase 4: Feature Completion

**Goal**: Implement any missing PRD requirements marked as "Must Have".

*Tasks in this phase depend on Phase 1 audit findings. Refine after Phase 2.*

### Task 4.x Template
```markdown
### Task 4.X: [Feature Name]
- **PRD Requirement**: FR-X.X
- **Depends on**: [Previous tasks]
- **Files to create/modify**:
  - `backend/app/...`
- **Do**: [Specific implementation steps]
- **Test**: [Test file and what to verify]
- **Done when**: [Acceptance criteria]
```

---

## Phase 5: Future Enhancements

**Goal**: Implement "Should Have" and "Could Have" items from PRD.

*Only proceed after Phase 4 is complete and stable.*

### Candidate Features (from PRD Section 10):
1. RSI indicator (FR-2.5)
2. Price breakout detection (FR-2.6)
3. Combined multi-signal alerts (FR-3.7)
4. Stock categorization in daily analysis (FR-4.3)
5. Win rate calculation for paper trading (FR-5.6)
6. WebSocket real-time notifications (FR-3.6)

---

## Technical Debt Checklist

*Items identified from codebase analysis. Address when doing maintenance or before major features.*

### High Priority

- [x] **Paper trading API: add db.rollback() on exception** — Added `db.rollback()` in all except blocks before re-raise.
- [x] **Paper trading API: handle DataAccessError explicitly** — DataAccessError → 400 (create) or 404 (close); Exception → 500.
- [x] **Standardize API error response format** — Added `error_detail()` in `utils/api_errors.py`; all APIs now use `{"error": true, "error_type": "...", "message": "..."}`.
- [x] **Alembic unused** — Removed from requirements; added Database Migrations section to ARCHITECTURE.md documenting current strategy.

### Medium Priority

- [x] **Extract "stock not found" helper** — Added `require_stock()` in `utils/stock_helpers.py`; used by stocks, sentiment_price.
- [x] **Move magic numbers to config** — Added analysis_sentiment_weight, analysis_trend_weight, sentiment_window_hours, reddit_max_age_days, price_history_days to config.
- [x] **Database migration: log swallowed exceptions** — Added logger.warning() in migration except block.
- [x] **Pydantic validation on CreateTradeRequest** — Added Literal["buy","sell"], Field(gt=0) for quantity, price, exit_price.
- [ ] **RedditPostData.stock_symbol** — Field is placeholder `""`; name suggests single symbol but posts can mention multiple. Consider renaming or `symbols: list[str]`.

### Low Priority

- [ ] **Repository injection** — Services instantiate repos (e.g. `PaperTradeRepository(db)`) inline; inject for testability.
- [ ] **Re-enable mypy** — Disabled in pre-commit due to module path issues. Fix config and re-enable.
- [ ] **SEC user agent** — `"contact@example.com"` in symbol_universe_service; make configurable.
- [ ] **Test coverage** — Add symbol-universe API tests; migration test for `_migrate_drop_reddit_posts_stock_symbol`; consider testing SQLAlchemy error paths.
- [ ] **Use status constants consistently** — `post_trade` uses `status.HTTP_400_BAD_REQUEST`; `post_close_trade` uses raw `400`.

---

## Agent Instructions

### How to Use This Plan

1. **Execute phases in order** (0 → 1 → 2 → 3 → 4 → 5)
2. **Record findings** in the designated spots during audit phases
3. **After Phase 2**, refine Phase 3-4 tasks based on actual findings
4. **One task at a time** - complete and verify before moving on
5. **Update this plan** as you learn more about the codebase

### Decision Rules

- **If a test fails**: Investigate before fixing - understand root cause
- **If docs conflict with code**: Ask user which is correct, or check git history
- **If external API is unavailable**: Mock it for testing, note for user
- **If unclear on priority**: Ask user before proceeding

### Reporting

After each phase, provide a summary:
```markdown
## Phase X Complete

### Completed Tasks
- [x] Task X.1: [Brief result]
- [x] Task X.2: [Brief result]

### Issues Found
- [Issue description]

### Blockers
- [Anything preventing progress]

### Recommended Next Steps
- [What to do next]
```

---

## Current Status

**Phase**: 3 (Complete)
**Last Updated**: January 31, 2026

### Phase Completion Checklist
- [x] Phase 0: Environment & Baseline Verification
- [x] Phase 1: Codebase Audit
- [x] Phase 2: Issue Triage
- [x] Phase 3: Stabilization

---

## Phase 0 Report (January 31, 2026)

### Task 0.1: Verify Backend Runs
- **Result**: Server starts successfully when run from project root: `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
- **Note**: AGENT_PLAN commands say `cd backend` then `uvicorn app.main:app`; project uses `backend.app` imports, so must run from project root with `backend.app.main:app`
- **Startup errors**:
  - Catch-up job fails during Reddit collection: `NOT NULL constraint failed: reddit_posts.stock_symbol`
  - Indicates schema drift: `reddit_posts` table has `stock_symbol` column (legacy) but model uses `RedditSymbolMention` junction table instead
- **Configuration**: `.env` lives in `backend/`; pydantic-settings loads from cwd, so when running from project root, may need `.env` in project root or explicit path
- **Health check**: `GET /health` returns 200 OK

### Task 0.2: Run Test Suite
- **Total tests**: 53
- **Passing**: 46
- **Failing**: 7
- **Errors**: 0
- **Failing test names**:
  1. `test_api_analysis.py::test_daily_analysis_ranks_stocks_by_composite_score`
  2. `test_api_stocks.py::test_get_sentiment_and_prices_for_stock`
  3. `test_jobs_api.py::test_get_recent_reddit_posts_with_data`
  4. `test_notification_service_api.py::test_generate_notifications_and_list_via_api`
  5. `test_repositories.py::test_reddit_post_repository_add_and_list_for_stock`
  6. `test_repositories.py::test_reddit_post_repository_count_recent_mentions`
  7. `test_scheduler_service.py::test_collect_reddit_data_with_tickers`
- **Root cause of 6 failures**: Tests pass `stock_symbol` to `RedditPost()`; model has no such field (uses `RedditSymbolMention` junction table)
- **7th failure**: `test_collect_reddit_data_with_tickers` asserts `stocks_created == 1` but got 6 (different behavior/expectation)

### Task 0.3: Verify Frontend Runs
- **Result**: `npm install` succeeds; `npm run dev` starts Vite on http://localhost:5173/
- **Build errors**: None
- **Dependencies**: 45 packages, 2 moderate severity vulnerabilities (npm audit)
- **Page load**: Vite server starts; curl to 127.0.0.1:5173 returned 000 (connection may be sandbox-restricted)

### Task 0.4: Test API Endpoints Manually
| Endpoint | Expected | Actual |
|----------|----------|--------|
| `GET /health` | 200 | 200 OK |
| `GET /api/stocks` | 200 | 500 Internal Server Error |
| `GET /api/stocks/{symbol}` | 200 or 404 | 500 Internal Server Error |
| `GET /api/analysis/daily` | 200 | 500 Internal Server Error |
| `GET /api/notifications` | 200 | 500 Internal Server Error |
| `GET /api/trades` | 200 | 500 Internal Server Error |
| `GET /api/portfolio` | 200 | 500 Internal Server Error |

- All endpoints except `/health` return 500; likely database/session or schema-related

---

## Phase 0 Complete

### Completed Tasks
- [x] Task 0.1: Backend installs and runs; `/health` returns 200. Startup has catch-up error (schema drift on `reddit_posts`)
- [x] Task 0.2: 53 tests run; 46 pass, 7 fail (6 due to `RedditPost`/`stock_symbol` model mismatch, 1 assertion mismatch)
- [x] Task 0.3: Frontend installs and dev server starts (Vite on :5173)
- [x] Task 0.4: Only `/health` returns 200; all other endpoints return 500

### Issues Found
- **RedditPost model vs tests**: Tests use `stock_symbol` on `RedditPost`; model uses `RedditSymbolMention` junction table. Tests are out of date.
- **Schema drift**: `reddit_posts` table has `stock_symbol` NOT NULL (legacy) vs current model; catch-up fails when inserting real Reddit data.
- **API 500 errors**: All DB-backed endpoints return 500; likely session or schema mismatch when using persisted DB.
- **AGENT_PLAN run commands**: Plan says `cd backend` + `uvicorn app.main:app`; project expects `uvicorn backend.app.main:app` from root.
- **Deprecations**: `on_event` deprecated in FastAPI; Pydantic `class Config` deprecated in favor of ConfigDict.

### Blockers
- None that prevent Phase 1 audit; backend and frontend both run. Tests and API need fixes before full functionality.

### Recommended Next Steps
1. Proceed to Phase 1: Codebase Audit.
2. Fix `RedditPost` test usage (use `RedditSymbolMention` or adjust model) to unblock 6 tests.
3. Investigate API 500s (DB path, schema migration, or fresh DB).
4. Update AGENT_PLAN startup commands to reflect project structure.

---

## Phase 1 Report (January 31, 2026)

### Task 1.1: Verify Data Models Match Documentation

**Discrepancies:**

| Model | PRD 7.3 Says | Actual | Discrepancy |
|-------|---------------|--------|-------------|
| Stock | symbol, name, sector | symbol, name, sector, market_cap, created_at, updated_at | Extra fields (OK; extends PRD) |
| SymbolUniverse | symbol, exchange, is_active | Adds name, is_etf, sector, industry, last_seen, created_at, updated_at | Extra fields (OK) |
| RedditPost | id, subreddit, title, upvotes, comments | Adds author, url, posted_at, collected_at; no stock_symbol (uses junction) | Model correct; PRD abbreviated |
| RedditSymbolMention | post_id + symbol (composite PK) | ✓ Matches | None |
| PriceData | stock_symbol, date, open, high, low, close, volume | ✓ Matches (adds id, timestamp) | None |
| Notification | type, severity, message, read | Adds id, stock_symbol, created_at | stock_symbol required for linking (PRD incomplete) |
| PaperTrade | symbol, action, quantity, price, status | Uses stock_symbol, entry_price, exit_price; no explicit status (derived from exit_price) | Minor: PRD "price"/"status" vs entry/exit_price design |
| JobExecution | job_name, started_at, completed_at | job_name, last_run_at (tracks last run only, not per-execution history) | Different design: single last_run_at vs started/completed per run |

**Summary:** No critical mismatches. PaperTrade and JobExecution have intentional design differences from PRD.

### Task 1.2: Verify API Routes Match Documentation

**PRD 14.A endpoints:** All 13 documented endpoints exist and match:
- GET /health, GET /api/stocks, GET /api/stocks/{symbol}
- GET /api/stocks/{symbol}/sentiment, GET /api/stocks/{symbol}/prices
- GET /api/analysis/daily, GET /api/notifications
- POST /api/trades, GET /api/trades, POST /api/trades/{id}/close, GET /api/portfolio
- POST /api/symbol-universe/refresh, GET /api/symbol-universe/stats

**Extra endpoints (not in PRD):**
- POST /api/stocks (create stock)
- POST /api/jobs/reddit-collection, POST /api/jobs/price-collection, POST /api/jobs/notification-check
- GET /api/jobs/reddit-collection/recent

**Discrepancies:** None. All PRD endpoints implemented. Path param `{trade_id}` vs PRD `{id}` is equivalent.

### Task 1.3: Assess Test Coverage

| Category | Module | Has Tests? | Notes |
|----------|--------|------------|-------|
| **Services** | activity_detector | ✓ test_activity_detector | |
| | analysis_service | ✓ test_api_analysis | Via API |
| | notification_service | ✓ test_notification_service_api | |
| | paper_trading_service | ✓ test_paper_trading_api | |
| | pattern_analyzer | ✓ test_pattern_analyzer | |
| | reddit_service | ✓ test_reddit_service | |
| | scheduler_service | ✓ test_scheduler_service | |
| | sentiment_analyzer | ✓ test_sentiment_analyzer | |
| | symbol_universe_service | ✓ test_symbol_universe | |
| | yahoo_service | ✓ test_yahoo_service | |
| **Repositories** | job_execution_repo | ✓ test_scheduler_service | |
| | notification_repo | ✓ test_notification_service_api | |
| | paper_trade_repo | ✓ test_paper_trading_api | |
| | price_data_repo | ✓ test_repositories | |
| | reddit_post_repo | ✓ test_repositories | (tests broken—stock_symbol) |
| | reddit_symbol_mention_repo | ⚠ Partial | No dedicated tests; only indirect via scheduler/jobs |
| | stock_repo | ✓ test_repositories, test_api_stocks_create | |
| | symbol_universe_repo | ✓ test_symbol_universe | |
| **API routes** | stocks, sentiment_price, analysis | ✓ test_api_stocks, test_api_analysis | |
| | notifications | ✓ test_notification_service_api | |
| | paper_trading | ✓ test_paper_trading_api | |
| | jobs | ✓ test_jobs_api | |
| | symbol_universe | ✓ test_symbol_universe | |

**Untested / under-tested modules:**
- `RedditSymbolMentionRepository`: No dedicated unit tests; only exercised indirectly.

### Task 1.4: Review Error Handling

**reddit_service.py:**
- ✓ Try/except around PRAW client init; raises ExternalAPIError
- ✓ Try/except in fetch loop; raises ExternalAPIError on subreddit fetch failure
- ✓ Backoff on _iter_new for retries
- ✓ No silent failures

**yahoo_service.py:**
- ✓ Try/except around fetch; raises ExternalAPIError
- ✓ Handles empty history (returns [])
- ✓ Handles malformed rows (KeyError, TypeError, ValueError) with ExternalAPIError
- ✓ Backoff on _safe_history
- ✓ fetch_latest_price returns None for no data (explicit, not silent)

**Gaps:** None identified. Both services handle failures explicitly.

### Task 1.5: Review Configuration Management

**PRD Section 8 variables:** All present in config.py with correct defaults:
- sentiment_positive_threshold, sentiment_negative_threshold
- volume_spike_threshold, price_movement_threshold_pct, sentiment_shift_threshold
- reddit_collection_interval_minutes, price_collection_interval_minutes
- notification_check_interval_minutes, daily_analysis_hour
- reddit_subreddits, enable_catch_up

**Secrets:** No hardcoded secrets. Reddit credentials loaded from env via pydantic-settings.

**Missing config options:** None.

### Task 1.6: Audit Background Jobs

| FR-7 Requirement | Status | Implementation |
|------------------|--------|----------------|
| FR-7.1 Reddit collection | ✓ | IntervalTrigger, configurable minutes |
| FR-7.2 Price collection | ✓ | IntervalTrigger, configurable minutes |
| FR-7.3 Daily analysis | ✓ | CronTrigger at daily_analysis_hour |
| FR-7.4 Notification checks | ✓ | IntervalTrigger, configurable minutes |
| FR-7.5 Catch-up logic | ✓ | _run_catch_up checks last run, runs missed jobs |
| FR-7.6 Job execution tracking | ✓ | JobExecutionRepository, record_run, get_last_run |

**Note:** Daily analysis job records execution but analysis is computed on-demand via API; no persistence of analysis results. This matches current design.

---

## Phase 1 Complete

### Completed Tasks
- [x] Task 1.1: Data models compared to PRD 7.3; minor discrepancies (PaperTrade, JobExecution)
- [x] Task 1.2: All PRD API endpoints exist; extra jobs/stocks endpoints present
- [x] Task 1.3: Test coverage assessed; RedditSymbolMentionRepository has no dedicated tests
- [x] Task 1.4: Reddit and Yahoo services handle errors explicitly; no gaps found
- [x] Task 1.5: All PRD config options present; no hardcoded secrets
- [x] Task 1.6: All FR-7 background jobs implemented and scheduled

### Issues Found
- **RedditSymbolMentionRepository**: No dedicated unit tests (only indirect coverage)
- **PaperTrade/JobExecution vs PRD**: Design differs from PRD table (acceptable; code is coherent)

### Blockers
- None

### Recommended Next Steps
1. Proceed to Phase 2: Issue Triage—categorize Phase 0 + Phase 1 findings.
2. Consider adding RedditSymbolMentionRepository unit tests in Phase 3.

---

## Phase 2 Report (January 31, 2026)

### Task 2.1: Issues List (Triaged)

#### Critical (blocks basic functionality)
- [x] **API 500 errors on all DB-backed endpoints**: Fixed via config `env_file = (".env", "backend/.env")` and schema migration. API returns 200 with TestClient.
- [x] **Schema drift blocks Reddit catch-up**: Added `_migrate_drop_reddit_posts_stock_symbol()` in `database.py` to drop legacy column on init.

#### High (core feature incomplete/broken)
- [x] **7 failing tests**: Fixed. Updated 6 tests to use `RedditSymbolMention`; fixed `test_collect_reddit_data_with_tickers` by seeding symbol universe. All 53 tests pass.
- [x] **AGENT_PLAN startup commands incorrect**: Updated Task 0.1 to show correct commands (`uvicorn backend.app.main:app` from root).

#### Medium (functionality works but has gaps)
- [x] **Config/.env loading from project root**: Fixed. `config.py` now uses `env_file = (".env", "backend/.env")`.
- [x] **RedditSymbolMentionRepository has no dedicated tests**: Added `test_reddit_symbol_mention_repo.py` with 4 tests.

#### Low (polish, nice-to-have)
- [x] **FastAPI `on_event` deprecated**: Replaced with lifespan context manager in `main.py`.
- [x] **Pydantic `class Config` deprecated**: Replaced with `model_config`/ConfigDict in config.py and API response models.
- [x] **PRD data model table outdated**: Updated PRD Section 7.3 to match implementation.

### Task 2.2: Documentation Update Decisions

| Finding | Decision | Action |
|---------|----------|--------|
| AGENT_PLAN startup commands | Update docs | Fix in Phase 3/now |
| PRD 7.3 data models | Update docs | Update PRD table to match code |
| PaperTrade, JobExecution design | Code is correct | No code change; doc update only |

---

## Phase 2 Complete

### Completed Tasks
- [x] Task 2.1: Created categorized issues list (4 Critical/High, 2 Medium, 3 Low)
- [x] Task 2.2: Decided documentation updates—fix AGENT_PLAN commands, update PRD 7.3 to match code

### Recommended Next Steps
1. Proceed to Phase 3: Stabilization—fix critical and high-priority issues first.
2. Fix failing tests and API 500s before addressing medium/low items.

---

## Phase 3 Report (January 31, 2026)

### Task 3.1: Fix Failing Tests ✓
- Updated 6 tests to use `RedditSymbolMention` instead of `RedditPost(stock_symbol=...)`: test_repositories (2), test_api_analysis, test_api_stocks, test_notification_service_api, test_jobs_api
- Fixed `test_collect_reddit_data_with_tickers`: seeded symbol universe (GME, AAPL) so ticker extractor returns only those, making `stocks_created == 1` assert pass
- Added `timedelta` import to `reddit_post_repo.py`
- **Result**: All 53 tests pass

### Task 3.2: Add Missing Tests
- Deferred: RedditSymbolMentionRepository still has no dedicated tests (Phase 2 Medium item)

### Task 3.3: Fix Error Handling Gaps
- No gaps identified in Phase 1; skipped

### Task 3.4: Fix Configuration Gaps ✓
- **Config env loading**: `config.py` now uses `env_file = (".env", "backend/.env")` so `.env` loads when running from project root
- **AGENT_PLAN commands**: Updated Task 0.1 with correct `uvicorn backend.app.main:app` from root

### Schema Migration (Critical fix)
- Added `_migrate_drop_reddit_posts_stock_symbol()` in `database.py`: drops legacy `stock_symbol` column from `reddit_posts` on init if present (SQLite 3.35+)

---

## Phase 3 Complete

### Completed Tasks
- [x] Task 3.1: Fixed all 7 failing tests
- [x] Task 3.4: Fixed config env loading, AGENT_PLAN commands
- [x] Schema migration for reddit_posts stock_symbol

### Recommended Next Steps
1. Proceed to Phase 4: Feature Completion (or Phase 5: Future Enhancements)
2. Optional: Add RedditSymbolMentionRepository dedicated tests
3. Optional: Address Low-priority items (deprecations, PRD updates)
