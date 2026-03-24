# Development Roadmap

This roadmap organizes future development work into prioritized phases.

**Last Updated**: February 1, 2026

---

## Overview

| Phase | Focus | Effort | Status |
|-------|-------|--------|--------|
| Phase 1 | Assessment & Stabilization | 1-2 days | ✅ Complete |
| Phase 2 | Tech Debt Resolution | 3-5 days | In Progress |
| Phase 2.5 | Command-Line Interface | 2-3 days | ✅ Complete |
| Phase 3 | Analysis Enhancements | 5-7 days | Not Started |
| Phase 4 | User Experience | 3-5 days | Not Started |
| Phase 5 | Advanced Features | 7-14 days | Not Started |
| Phase 6 | Scale & Production | 5-10 days | Not Started |

---

## Phase 1: Assessment & Stabilization ✅ Complete

**Goal**: Establish baseline quality and fix any blocking issues.

**Priority**: Critical - Do this first

**Completed**: January 31, 2026

### Tasks

| ID | Task | Status | Result |
|----|------|--------|--------|
| 1.1 | Run quality check | ✅ | Baseline established |
| 1.2 | Run full test suite | ✅ | 53 tests, 100% pass rate |
| 1.3 | Verify backend starts | ✅ | Server runs, /health returns 200 |
| 1.4 | Verify frontend builds | ✅ | Vite dev server runs on :5173 |
| 1.5 | Test API endpoints manually | ✅ | All endpoints return expected responses |
| 1.6 | Document any issues found | ✅ | Issues triaged and fixed |

### Work Completed

**Environment Verification**:
- Backend starts with `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` from project root
- Frontend starts with `npm run dev` in frontend/ directory
- All 53 tests pass after fixes

**Issues Fixed**:
- Fixed 7 failing tests (6 due to RedditPost/RedditSymbolMention model update, 1 assertion fix)
- Fixed schema drift: added migration to drop legacy `stock_symbol` column from `reddit_posts`
- Fixed config loading: `env_file = (".env", "backend/.env")` for project root execution
- Fixed API 500 errors on all DB-backed endpoints
- Replaced deprecated FastAPI `on_event` with lifespan context manager
- Replaced deprecated Pydantic `class Config` with `model_config`/ConfigDict

**Added**:
- `test_reddit_symbol_mention_repo.py` with 4 tests for RedditSymbolMentionRepository

### Commands
```bash
# From project root
./scripts/quality-check.sh
pytest backend/tests/ -v
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

---

## Phase 2: Tech Debt Resolution

**Goal**: Address known technical debt before adding features.

**Priority**: High - Clean foundation enables faster feature development

### Tasks

| ID | Task | Source | Effort | Status |
|----|------|--------|--------|--------|
| 2.1 | Make sentiment keywords configurable | PLAN.md tech debt | Small | ✅ Done |
| 2.2 | Add post body to sentiment analysis | PLAN.md tech debt | Medium | Not Started |
| 2.3 | Add RSI indicator | PLAN.md tech debt, PRD FR-2.5 | Medium | Not Started |
| 2.4 | Add volume confirmation to patterns | PLAN.md tech debt | Small | Not Started |
| 2.5 | Implement combined-signal alerts | PLAN.md tech debt, PRD FR-3.7 | Medium | ✅ Complete |
| 2.6 | Fix any deprecation warnings | Test output | Small | ✅ Done in Phase 1 |
| 2.7 | Increase test coverage to 80%+ | Quality framework | Medium | Not Started |

### Technical Debt Checklist

Items consolidated from codebase analysis. Address when doing maintenance or before major features.

**Intraday ingestion (PR #17 / feature branch)**: When enabled, intraday ingestion uses a **global run lock** (job_locks table, TTL lease) to prevent overlapping runs between the scheduler and the API. See governance lock in codebase.

#### Completed ✅

| Item | Resolution |
|------|------------|
| Paper trading API: add db.rollback() on exception | Added in all except blocks |
| Paper trading API: handle DataAccessError | DataAccessError → 400/404; Exception → 500 |
| Standardize API error response format | Added `error_detail()` in `utils/api_errors.py` |
| Alembic unused | Removed; added Database Migrations section to ARCHITECTURE.md |
| Extract "stock not found" helper | Added `require_stock()` in `utils/stock_helpers.py` |
| Move magic numbers to config | Added analysis weights, windows, history days to config |
| Database migration: log swallowed exceptions | Added logger.warning() in migration except block |
| Pydantic validation on CreateTradeRequest | Added Literal, Field(gt=0) constraints |
| SEC user agent | Added sec_user_agent to config |
| Use status constants consistently | APIs now use status.HTTP_XXX consistently |

#### Remaining

| Priority | Item | Notes |
|----------|------|-------|
| Medium | RedditPostData.stock_symbol naming | Field is placeholder ""; consider renaming to `symbols: list[str]` |
| Low | Repository injection | Services instantiate repos inline; inject for testability |
| Low | Re-enable mypy in pre-commit | Disabled due to module path issues; fix config |
| Low | Additional test coverage | symbol-universe API tests, migration tests, SQLAlchemy error paths |

### 2.1 Make Sentiment Keywords Configurable

**Current**: Keywords hardcoded in `sentiment_analyzer.py`
```python
POSITIVE_KEYWORDS = {"buy", "moon", "hold", ...}
```

**Target**: Keywords loaded from config or file
```python
# In config.py
sentiment_positive_keywords: str = "buy,moon,hold,bullish,gains,profit,long"
```

**Files**: `backend/app/config.py`, `backend/app/services/sentiment_analyzer.py`

### 2.2 Add Post Body to Sentiment Analysis

**Current**: Only analyzes post title
**Target**: Analyze title + body (when available)

**Files**: `backend/app/services/sentiment_analyzer.py`, `backend/app/models/reddit_post.py`

### 2.3 Add RSI Indicator

**Current**: Only SMA-based trend detection
**Target**: RSI calculation with overbought/oversold signals

**Formula**:
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (14 periods)
```

**Files**: `backend/app/services/pattern_analyzer.py`

### 2.4 Add Volume Confirmation

**Current**: Volume spike detected but not used in pattern confirmation
**Target**: Require volume confirmation for breakout signals

**Files**: `backend/app/services/pattern_analyzer.py`

### 2.5 Combined-Signal Alerts

**Current**: Separate alerts for volume, price, sentiment
**Target**: Combined alert when multiple signals align

**Logic** (from PLAN.md):
```python
if alignment_score > COMBINED_SIGNAL_THRESHOLD and confidence > 0.7:
    create_notification(type="strong_signal", ...)
```

**Files**: `backend/app/services/activity_detector.py`, `backend/app/services/notification_service.py`

### Success Criteria
- [ ] All tech debt items from PLAN.md resolved
- [ ] Test coverage ≥ 80%
- [ ] No deprecation warnings in test output
- [ ] Quality score improved from baseline

---

## Phase 3: Analysis Enhancements

**Goal**: Improve the quality and usefulness of analysis outputs.

**Priority**: Medium - Core value proposition improvements

### Tasks

| ID | Task | PRD Ref | Effort |
|----|------|---------|--------|
| 3.0 | Lead-lag evidence endpoint (sentiment/mentions vs returns) | PRD §1.2 | Medium |
| 3.1 | Stock categorization in daily analysis | FR-4.3 | Medium |
| 3.2 | 7-day trend comparison | FR-4.4 | Medium |
| 3.3 | Price breakout/breakdown detection | FR-2.6 | Medium |
| 3.4 | Support/resistance level identification | FR-2.7 | Large |
| 3.5 | Win rate calculation for paper trading | FR-5.6 | Small |
| 3.6 | Sentiment momentum tracking | PRD §5 | Medium |
| 3.7 | Leader-follower signal detection | specs/003 | ✅ Implemented |
| 3.8 | Leader-follower paper trading simulation | specs/011 | ✅ Implemented |

### 3.7 Leader-Follower Signal Detection ✅

**Purpose**: Detect significant leader moves, identify follower candidates in same group, emit opportunity signals.

**Implemented**: March 2026. See `specs/003-leader-follower-signal-detection/`.

**API**: `GET /api/leader-follower/signals` (limit, since_date, leader, group)

**Scheduler**: `leader_follower_detection` job (gated by `leader_follower_enabled`; CronTrigger hour=17; max_instances=1, coalesce=True)

### 3.8 Leader-Follower Paper Trading Simulation ✅

**Purpose**: Simulate trades from historical leader-follower signals with configurable entry/exit, costs, and per-event position caps; report cumulative return and drawdown.

**Spec**: `specs/011-leader-follower-execution-and-paper-trading/`

**API**: `GET /api/leader-follower/paper-trading/runs`, `GET /.../{run_id}`, `GET /.../{run_id}/equity-curve`

**CLI**: `python -m backend.app.cli simulate leader-follower --start ... --end ...`

### 3.0 Lead-Lag Evidence Endpoint ✅

**Purpose**: Answer "Does Reddit activity/sentiment lead price moves for SYMBOL at some lag?"

**Endpoint**: `GET /api/analysis/causal/{symbol}`

**Output** (labeled as "lead-lag evidence", not proven causality):
- Cross-correlation by lag (mentions→returns, sentiment→returns)
- Out-of-sample predictive regression metrics (R², directional accuracy)
- Placebo test (shuffled predictor; result should drop)

**UI (Phase 4 UX)**: Causal tab on symbol detail page; controls (days, freq, max_lag, include placebo); results tables; correlation vs lag chart.

### 3.1 Stock Categorization

**Current**: Daily analysis returns ranked list
**Target**: Categorize into buckets

```python
{
    "top_opportunities": [...],  # score > 0.7
    "watchlist": [...],          # score 0.5-0.7
    "avoid": [...],              # score < 0.3
    "high_risk": [...]           # high volatility + low confidence
}
```

### 3.5 Win Rate Calculation

**Current**: Basic P/L tracking
**Target**: Performance metrics

```python
@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # wins / total
    avg_win: float
    avg_loss: float
    profit_factor: float  # gross_profit / gross_loss
```

### Success Criteria
- [ ] Daily analysis shows categorized stocks
- [ ] Paper trading shows win rate and performance metrics
- [ ] At least 2 additional technical indicators implemented
- [ ] All new features have tests

---

## Phase 4: User Experience

**Goal**: Improve frontend usability and real-time capabilities.

**Priority**: Medium - Better UX increases engagement

### Tasks

| ID | Task | PRD Ref | Effort |
|----|------|---------|--------|
| 4.1 | Auto-refresh for dashboard data | NFR-6.3 | Small |
| 4.2 | WebSocket real-time notifications | FR-3.6 | Large |
| 4.3 | Price charts with indicators | PRD §5 | Medium |
| 4.4 | Notification preferences/filtering | PRD §5 | Small |
| 4.5 | Loading states and error handling | NFR-6.2 | Small |

### 4.3 WebSocket Notifications

**Current**: Polling-based notification check
**Target**: Real-time push via WebSocket

**Backend**:
```python
@app.websocket("/ws/notifications")
async def notification_websocket(websocket: WebSocket):
    await websocket.accept()
    # Push notifications as they're created
```

**Frontend**: Connect to WebSocket, update notification badge in real-time

### Success Criteria
- [ ] Dashboard auto-refreshes every 60 seconds
- [ ] Notifications appear in real-time (WebSocket)
- [ ] Charts display price data with overlays

---

## Phase 5: Advanced Features

**Goal**: Add sophisticated analysis and integration capabilities.

**Priority**: Low - Nice-to-have enhancements

### Tasks

| ID | Task | PRD Ref | Effort |
|----|------|---------|--------|
| 5.1 | ML-based sentiment analysis | FR-1.8 | Large |
| 5.2 | Additional subreddit support | - | Small |
| 5.3 | News headline integration | PRD §10 | Large |
| 5.4 | Backtesting engine | PRD §10 | Large |
| 5.5 | Export data (CSV/JSON) | - | Small |
| 5.6 | Discord/Telegram alerts | PRD §10 | Medium |
| 5.7 | Options flow data | PRD §10 | Large |

### 5.1 ML-Based Sentiment

**Current**: Keyword-based sentiment scoring
**Target**: Transformer-based sentiment model

**Options**:
- FinBERT (finance-specific)
- VADER with financial lexicon
- Fine-tuned DistilBERT

**Considerations**:
- Model size vs. accuracy tradeoff
- Inference latency
- GPU requirements

### 5.4 Backtesting Engine

**Purpose**: Test trading strategies against historical data

**Components**:
- Historical data loader
- Strategy definition interface
- Simulation engine
- Performance reporting

### Success Criteria
- [ ] At least one advanced feature implemented end-to-end
- [ ] Performance acceptable (no significant latency increase)
- [ ] Comprehensive tests for new features

---

## Phase 6: Scale & Production

**Goal**: Prepare for production deployment and scale.

**Priority**: Low - Only if moving beyond personal use

### Tasks

| ID | Task | Effort |
|----|------|--------|
| 6.1 | PostgreSQL migration | Medium |
| 6.2 | Docker containerization | Medium |
| 6.3 | User authentication | Large |
| 6.4 | Rate limiting | Small |
| 6.5 | Monitoring and alerting | Medium |
| 6.6 | CI/CD pipeline | Medium | ✅ Deploy workflow added (see docs/DEPLOYMENT.md) |
| 6.7 | Production deployment guide | Small | ✅ docs/DEPLOYMENT.md |

### 6.1 PostgreSQL Migration

**Current**: SQLite (single-writer, file-based)
**Target**: PostgreSQL (concurrent access, better scaling)

**Migration path**:
1. Update `DATABASE_URL` to postgres connection string
2. SQLAlchemy models already compatible
3. Test with PostgreSQL
4. Migrate data if needed

### 6.3 User Authentication

**Options**:
- Simple JWT-based auth
- OAuth (Google, GitHub)
- Session-based with cookies

**Scope**:
- User registration/login
- Per-user watchlists
- Per-user paper trading portfolios

### Success Criteria
- [ ] Can run in Docker container
- [ ] Works with PostgreSQL
- [ ] Has basic authentication (if needed)
- [ ] Deployed to cloud provider

---

## Prioritization Matrix

| Task | Impact | Effort | Priority |
|------|--------|--------|----------|
| Phase 1 (Assessment) | High | Low | 🔴 Do First |
| CLI (Phase 2.5) | High | Medium | 🟠 Quick Win |
| Configurable keywords | Medium | Low | 🟠 Quick Win |
| RSI indicator | High | Medium | 🟠 High Value |
| Combined-signal alerts | High | Medium | 🟠 High Value |
| Test coverage 80%+ | High | Medium | 🟠 High Value |
| Stock categorization | Medium | Medium | 🟡 Planned |
| WebSocket notifications | Medium | High | 🟡 Planned |
| ML sentiment | High | High | 🔵 Future |
| Backtesting | High | High | 🔵 Future |
| Multi-user auth | Low | High | ⚪ Maybe |

---

## Recommended Execution Order

### Immediate (This Week)
1. **Phase 1.1-1.6**: Assessment & baseline
2. **Phase 2.1**: Configurable sentiment keywords
3. **Phase 2.6**: Fix deprecation warnings

### Short-term (Next 2 Weeks)
4. **Phase 2.3**: RSI indicator
5. **Phase 2.5**: Combined-signal alerts
6. **Phase 2.7**: Test coverage to 80%

### Medium-term (Next Month)
7. **Phase 3.1**: Stock categorization
8. **Phase 3.5**: Win rate calculation
9. **Phase 4.1**: Auto-refresh
10. **Phase 4.6**: Better loading/error states

### When Needed
- Phase 4.3 (WebSocket) - If polling is insufficient
- Phase 5.x - Based on user feedback
- Phase 6.x - If deploying to production

---

## Tracking Progress

Update this section as work completes:

| Date | Phase | Task | Status | Notes |
|------|-------|------|--------|-------|
| 2026-01-31 | 1 | Environment verification | ✅ | Backend/frontend run, /health returns 200 |
| 2026-01-31 | 1 | Test suite | ✅ | 53 tests, 100% pass rate |
| 2026-01-31 | 1 | Fix failing tests | ✅ | 7 tests fixed (model/assertion updates) |
| 2026-01-31 | 1 | Schema migration | ✅ | Dropped legacy reddit_posts.stock_symbol |
| 2026-01-31 | 1 | Config loading fix | ✅ | env_file supports project root |
| 2026-01-31 | 1 | Deprecation fixes | ✅ | FastAPI lifespan, Pydantic ConfigDict |
| 2026-01-31 | 1 | Add missing tests | ✅ | RedditSymbolMentionRepository tests |
| 2026-02-01 | 2 | 2.1 Configurable sentiment keywords | ✅ | config.py + sentiment_analyzer.py |
| 2026-02-01 | 2.5 | CLI implementation started | 🔄 | backend/cli/ scaffold |
| 2026-03-04 | 4 | Causal UI (lead-lag tab on symbol detail) | ✅ | CausalPanel, fetchCausalEvidence, tab routing |
| 2026-03-04 | 4 | 4A: Research API (build-dataset, experiments) | ✅ | backend/app/api/research.py, test_research_api.py |
| 2026-03-04 | 4 | 4B: Research frontend page | ✅ | Research.tsx, nav + route, api client |

---

## References

- `PLAN.md` - Original project plan and tech debt
- `PRD.md` - Product requirements with FR/NFR details
- `QUALITY.md` - Quality measurement framework
- `ARCHITECTURE.md` - Implementation patterns

### Generated Reports (for AI Agents)

Run `./scripts/quality-check.sh` to generate these reports:

| File | Contents | Use Case |
|------|----------|----------|
| `.coverage-report.md` | Per-file test coverage with missing lines | Improve test coverage |
| `.api-inventory.md` | All API endpoints from OpenAPI schema | Understand API surface |
| `.mypy-report.md` | Type errors by file and line | Fix type issues |
| `.lint-report.md` | Linting errors by file | Fix code style |
| `.todos-report.md` | TODO/FIXME items in codebase | Address technical debt |

These files are gitignored and regenerated on each quality check.

---

## Agent Instructions

When working on this roadmap:

1. **Execute phases in order** - complete Phase N before starting Phase N+1
2. **One task at a time** - complete and verify before moving on
3. **Update this document** - mark tasks complete, add notes, update tracking table
4. **Follow ARCHITECTURE.md patterns** - Model → Repository → Service → API → Tests
5. **Run verification** - `./scripts/verify.sh` or `pytest` + `pre-commit` before marking done

### Using Generated Reports

Run `./scripts/quality-check.sh` first to generate all reports, then:

| Task | Read This Report |
|------|------------------|
| Improve test coverage | `.coverage-report.md` - files sorted by coverage, missing lines |
| Fix type errors | `.mypy-report.md` - errors by file with line numbers |
| Fix linting issues | `.lint-report.md` - style errors by file |
| Address TODOs | `.todos-report.md` - all TODO/FIXME items |
| Understand API | `.api-inventory.md` - all endpoints with methods and tags |

### Improving Test Coverage

When working on Task 2.7 (test coverage) or any testing task:

1. **Read `.coverage-report.md`** for per-file coverage data:
   - Files sorted by coverage (lowest first)
   - Specific line numbers that need tests
   - Top 10 files needing most improvement

2. **Prioritize** files with:
   - Lowest coverage percentage
   - Most missed lines
   - Core business logic (services, repositories)

3. **After adding tests**, re-run quality check to update the report

### Decision Rules

- **If a test fails**: Investigate before fixing - understand root cause
- **If docs conflict with code**: Check git history, ask user if unclear
- **If external API unavailable**: Mock for testing, note for user
- **If unclear on priority**: Ask user before proceeding
