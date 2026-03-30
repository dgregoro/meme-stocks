# Spec 021 — Daily strategy S3 (volatility term structure)

**Purpose:** Implement **S3 — volatility term structure regime** in-repo: ingest **VIX** and a **medium-term implied vol index** (e.g. **VIX3M**), label **regimes**, and evaluate **regime-conditional equity** behavior using the same rigor as **S1/S2** (checklist, optional merit persistence, preflight).

**Status:** 📋 Spec drafted — not implemented.

**Companion docs**

| Doc | Role |
|-----|------|
| [spec.md](./spec.md) | Feature specification (Speckit / requirements) |
| [plan.md](./plan.md) | Implementation plan sketch |
| [quickstart.md](./quickstart.md) | Example commands (TBD until implemented) |
| [docs/STRATEGY_EXPLORATION.md](../../docs/STRATEGY_EXPLORATION.md) | S3 hypothesis and results table |
| [docs/STRATEGY_TESTING_PLAN.md](../../docs/STRATEGY_TESTING_PLAN.md) | Operational test sequence for S3 |
| [specs/020-shared-research-execution](../020-shared-research-execution/README.md) | Shared costs, splits, envelope (reuse for merit) |
| [specs/019-strategy-eval-data-preflight](../019-strategy-eval-data-preflight/plan.md) | Equity `price_data` preflight pattern |

**Suggested git branch:** `021-strategy-s3-vol-term-structure`
