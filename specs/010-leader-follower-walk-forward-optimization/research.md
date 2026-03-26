# Research: Leader-Follower Walk-Forward Optimization

## R1 — Signals: reuse stored vs regenerate per grid point

**Decision**: MVP uses **stored `leader_follower_signals` only**. Each grid point varies **`PaperTradingConfig`** fields (`holding_days`, `max_positions_per_event`, `min_pair_score`, `per_trade_cost_pct`, entry/exit modes).

**Rationale**: `run_paper_trading_simulation` reads signals from the DB; leader return/volume thresholds affect **detection**, which would require **replay/backfill** per configuration—high compute and schema complexity for v1.

**Alternatives considered**: Full replay per threshold combo (accurate, expensive); hybrid queue (deferred).

---

## R2 — Persist paper runs for each grid evaluation?

**Decision**: **No.** Optimization calls an in-memory **`compute_paper_trading_metrics`** (extracted from current simulation) that does **not** insert `LeaderFollowerPaperRun` / trades.

**Rationale**: Avoids hundreds of paper-run rows, keeps paper trading API for intentional single runs only.

**Alternatives considered**: Persist ephemeral runs with a flag (more schema/UI noise).

---

## R3 — Robustness ranking (transparent)

**Decision**: Method id **`walk_forward_v1`**. For each parameter set:

Let `V = validate cumulative_return_pct`, `T = train cumulative_return_pct`, `D = validate max_drawdown_pct`, `n = validate total_trades`, `n_min` = minimum trades floor (config default e.g. 5).

- If `n < n_min`: `raw_score = -10_000 + n` (severe penalty, deterministic tie-break by n).
- Else:  
  `raw_score = V - w_deg * max(0, T - V) - w_dd * D`  
  with defaults `w_deg = 0.5`, `w_dd = 0.25` (stored in run `config_json` under `ranking`).

**Rationale**: Validation-first; penalizes train→validate degradation (overfitting signal) and deep drawdowns; low sample invalidate.

**Alternatives considered**: Sort only by Sharpe (needs more stats); ML ranker (non-goal).

---

## R4 — Grid definition

**Decision**: JSON file passed to CLI:

- `base_config`: partial `PaperTradingConfig` fields (defaults merged).
- `grid`: object mapping parameter name → list of values (Cartesian product).
- **Cap**: `Settings.leader_follower_optimization_max_grid_points` (default 256) rejects larger cross-products at CLI with clear error.

**Rationale**: Explicit, reproducible; matches “small grid” requirement.

**Alternatives considered**: All CLI flags (combinatorial explosion); YAML (extra dep).

---

## R5 — Optional test window

**Decision**: **Optional** in MVP. If omitted, `test_metrics_json` is null on results. Ranking still uses train+validate only.

**Rationale**: Spec allows optional test; speeds initial adoption.

---

## R6 — `pair_filter_mode` categorical

**Decision**: **Defer** to Phase 2. MVP maps “filter strength” only via **`min_pair_score`** (including `null` = off).

**Rationale**: Aligns with existing `PaperTradingConfig`; categorical mode needs clearer mapping to signal pipeline.
