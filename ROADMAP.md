# Development Roadmap

This roadmap organizes future development work into prioritized phases.

---

## Overview

| Phase | Focus | Effort | Status |
|-------|-------|--------|--------|
| Phase 1 | Assessment & Stabilization | 1-2 days | Not Started |
| Phase 2 | Tech Debt Resolution | 3-5 days | Not Started |
| Phase 3 | Analysis Enhancements | 5-7 days | Not Started |
| Phase 4 | User Experience | 3-5 days | Not Started |
| Phase 5 | Advanced Features | 7-14 days | Not Started |
| Phase 6 | Scale & Production | 5-10 days | Not Started |

---

## Phase 1: Assessment & Stabilization

**Goal**: Establish baseline quality and fix any blocking issues.

**Priority**: Critical - Do this first

### Tasks

| ID | Task | Deliverable |
|----|------|-------------|
| 1.1 | Run quality check | Baseline score recorded |
| 1.2 | Run full test suite | All tests passing |
| 1.3 | Verify backend starts | Server runs without errors |
| 1.4 | Verify frontend builds | Dev server runs |
| 1.5 | Test API endpoints manually | Confirm core functionality |
| 1.6 | Document any issues found | Issues list for Phase 2 |

### Success Criteria
- [ ] `./scripts/quality-check.sh` runs and produces score
- [ ] `pytest backend/tests/ -v` shows 100% pass rate
- [ ] Backend starts: `uvicorn backend.app.main:app`
- [ ] Frontend starts: `npm run dev` (in frontend/)
- [ ] Quality baseline documented

### Commands
```bash
./scripts/quality-check.sh
pytest backend/tests/ -v
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

---

## Phase 2: Tech Debt Resolution

**Goal**: Address known technical debt before adding features.

**Priority**: High - Clean foundation enables faster feature development

### Tasks

| ID | Task | Source | Effort |
|----|------|--------|--------|
| 2.1 | Make sentiment keywords configurable | PLAN.md tech debt | Small |
| 2.2 | Add post body to sentiment analysis | PLAN.md tech debt | Medium |
| 2.3 | Add RSI indicator | PLAN.md tech debt, PRD FR-2.5 | Medium |
| 2.4 | Add volume confirmation to patterns | PLAN.md tech debt | Small |
| 2.5 | Implement combined-signal alerts | PLAN.md tech debt, PRD FR-3.7 | Medium |
| 2.6 | Fix any deprecation warnings | Test output | Small |
| 2.7 | Increase test coverage to 80%+ | Quality framework | Medium |

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
| 3.1 | Stock categorization in daily analysis | FR-4.3 | Medium |
| 3.2 | 7-day trend comparison | FR-4.4 | Medium |
| 3.3 | Price breakout/breakdown detection | FR-2.6 | Medium |
| 3.4 | Support/resistance level identification | FR-2.7 | Large |
| 3.5 | Win rate calculation for paper trading | FR-5.6 | Small |
| 3.6 | Sentiment momentum tracking | PRD §5 | Medium |

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
| 4.2 | Mobile-responsive layout | NFR-6.4 | Medium |
| 4.3 | WebSocket real-time notifications | FR-3.6 | Large |
| 4.4 | Price charts with indicators | PRD §5 | Medium |
| 4.5 | Notification preferences/filtering | PRD §5 | Small |
| 4.6 | Loading states and error handling | NFR-6.2 | Small |

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
- [ ] Works on mobile devices
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
| 6.6 | CI/CD pipeline | Medium |
| 6.7 | Production deployment guide | Small |

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
| | | | | |

---

## References

- `PLAN.md` - Original project plan and tech debt
- `PRD.md` - Product requirements with FR/NFR details
- `AGENT_PLAN.md` - Task breakdown for agent execution
- `QUALITY.md` - Quality measurement framework
- `ARCHITECTURE.md` - Implementation patterns
