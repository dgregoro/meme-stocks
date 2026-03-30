# Spec 020 — Shared research execution platform

**Purpose:** Normative specs for **cross-strategy** building blocks that sit between raw research ideas (`S1`–`S7`, volume spike, extreme move, leader-follower) and any **tradability** or **paper** workflow.

**Status:** Mixed — some slices are implemented (`research_execution`); others are planned. Each slice file states its own status.

**Relationship to other specs**

| Spec | Role |
|------|------|
| [019-strategy-eval-data-preflight](../019-strategy-eval-data-preflight/plan.md) | Data prerequisites and optional `--ensure-data` for daily-strategy CLI |
| [011-leader-follower-execution-and-paper-trading](../011-leader-follower-execution-and-paper-trading/plan.md) | Event-driven paper sim from leader-follower signals (domain-specific) |
| [018-hypothesis-research-recipe](../018-hypothesis-research-recipe/) | YAML orchestration of CLI steps |

**Spec Kit artifacts**

| File | Topic |
|------|--------|
| [spec.md](./spec.md) | User stories, requirements (feature spec) |
| [research.md](./research.md) | Phase 0 decisions |
| [data-model.md](./data-model.md) | Envelope + related entities |
| [quickstart.md](./quickstart.md) | Developer quickstart |
| [contracts/README.md](./contracts/README.md) | JSON/CLI contracts |

**Slice index**

| File | Topic |
|------|--------|
| [plan.md](./plan.md) | Implementation plan, gates, project structure |
| [core-helpers.md](./core-helpers.md) | Costs, drawdown/equity metrics, calendar/trading window splits |
| [run-envelope.md](./run-envelope.md) | `ResearchRunEnvelope` — reproducibility metadata |
| [daily-simple-backtest.md](./daily-simple-backtest.md) | Generic daily bar path: signal → positions → PnL (planned) |
| [walk-forward-harness.md](./walk-forward-harness.md) | Multi-window evaluation orchestration (planned) |
| [net-metrics-reporting.md](./net-metrics-reporting.md) | Net-of-costs reporting conventions (planned) |
| [integration-conventions.md](./integration-conventions.md) | Merit runs, CLI, envelopes, leader-follower reuse |

**Code today (partial map)**

- `backend/app/services/research_execution/` — core helpers + envelope
- `backend/app/services/daily_frequency_strategy_research.py` — imports window splits from `research_execution`
- `backend/app/services/leader_follower_paper_trading_service.py` — imports costs + drawdown from `research_execution`
- `backend/app/services/strategy_eval_data_preflight.py` — data gate (019)
- `backend/app/models/daily_strategy_merit_run.py` — persisted merit JSON
