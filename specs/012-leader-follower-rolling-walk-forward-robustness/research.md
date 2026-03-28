# Research: 012 Rolling walk-forward robustness

## 1. Split calendar (MVP)

**Decision**: **Calendar-month** windows with **inclusive** date bounds. Train/validate/test are contiguous: `validate_start = train_end + 1 day`, etc. **Anchor** advances by `step_months` via `add_months(anchor, step_months)` until the next full split would extend past `overall_end`.

**Rationale**: Matches spec MVP guidance; stdlib-only (`calendar.monthrange`); deterministic when `overall_start` is typically the first of a month.

**Alternatives considered**: Day-based windows (deferred — spec lists as follow-on); 30-day approximations (ambiguous month lengths).

## 2. Grid vs candidates (MVP)

**Decision**: Support **both**: Mode A — same `base_config` + `grid` + `ranking` JSON shape as `010`, with `ranking.method` = `rolling_robustness_v1`. Mode B — JSON with `base_config` + `candidates` array of `PaperTradingConfig`-shaped objects + `ranking`.

**Rationale**: Grid reuses existing workflow; candidates support Top-K rescoring without re-specifying full grid.

**Alternatives considered**: Grid-only MVP — rejected to align with spec User Story 2.

## 3. Test window

**Decision**: **Optional**. Two-window (train/validate) and three-window splits supported; `test_window_spec` nullable on run row.

**Rationale**: Spec non-goals keep compute bounded; optional test matches `010`.

## 4. Minimum trades / eligibility

**Decision**: `min_trades_validate` per split (default **5**). Splits below floor contribute to `ineligible_splits` in aggregate JSON and incur a **per-ineligible** penalty in `rolling_robustness_v1` (configurable weight).

**Rationale**: Surfaces thin-split configs without hiding them.

## 5. Ranking: `rolling_robustness_v1`

**Decision**: Explainable score using **medians** over splits (not max single-split return):

- `median_validation_cumulative_return_pct`
- Penalties: `w_dd × median(validate max_drawdown_pct)`, `w_gap × median(max(0, train_ret − validate_ret))`
- Bonus for consistency: `w_frac × (frac_positive_validation − 0.5)` scaled in stored config
- Penalty: `penalty_ineligible × ineligible_splits`

Tie-break: descending `robustness_score`, then lexicographic canonical `params_json`.

**Rationale**: User Story 4 — consistency over one-period winners.

**Alternatives considered**: Mean-only (outlier-sensitive); walk_forward_v1 single-split formula (wrong object).

## 6. `config_hash`

**Decision**: **SHA-256** hex of UTF-8 `json.dumps(params, sort_keys=True)` for stable filtering.

**Alternatives considered**: params-only queries — hash enables compact API filter `config_key`.

## 7. Work caps

**Decision**: `leader_follower_robustness_max_evaluations` = max `splits × candidates` (hard ceiling). Candidate count and grid Cartesian size each bounded by existing `leader_follower_optimization_max_grid_points` philosophy (reuse same setting for max candidates / grid combinations).

**Rationale**: Prevents runaway CLI jobs per spec risks.

## 8. Split index

**Decision**: **0-based** `split_index` persisted and exposed in API.

**Rationale**: Common for loops; documented in contract.
