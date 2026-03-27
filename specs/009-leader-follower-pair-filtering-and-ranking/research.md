# Research: Leader-Follower Pair Filtering and Ranking

**Feature**: 009-leader-follower-pair-filtering-and-ranking

## 1. Threshold Default Values

**Decision**: Use conservative defaults to avoid over-filtering with current sample sizes.

| Config Key | Default | Rationale |
|------------|---------|-----------|
| `leader_follower_pair_min_signal_count` | 2 | Matches existing `min_sample` in `/evaluation/top-pairs`; with ~54 evaluable signals and 43 pairs, many have count=1; 2 allows pairs with 2+ observations |
| `leader_follower_pair_min_avg_return_1d` | 0.0 | Do not exclude positive pairs by default; let users tighten |
| `leader_follower_pair_min_win_rate_1d` | 0.5 | Exclude pairs with <50% win rate; reasonable floor |

**Alternatives considered**: More aggressive defaults (e.g., min_signal_count=3, min_avg_return_1d=0.5) would exclude most pairs with current backfill. Defer to user config.

---

## 2. API Layer vs Service Layer

**Decision**: Keep filter/rank logic inline in API routes or in a thin helper within `leader_follower_evaluation_service`.

**Rationale**:
- `aggregate_by_pair` already produces the data. Adding `filter_pairs_by_thresholds()` and `rank_pairs()` as helpers keeps logic reusable and testable.
- API layer calls `run_evaluation` + `aggregate_by_pair` (existing), then applies filter/rank. No new repository or heavy abstraction.

**Alternatives considered**: Dedicated `pair_filtering_service.py` — rejected as overkill for O(n) in-memory ops. Keep in evaluation service or API.

---

## 3. Caching

**Decision**: No caching for MVP. Ranking/filtering computed on demand.

**Rationale**:
- Pair count is small (~50–200). Evaluation is already on-demand. Adding cache adds complexity (invalidation, TTL) with little benefit.
- Revisit if pair count or evaluation cost grows.

---

## 4. Query Override vs Config Only

**Decision**: Config defaults with optional query-param override for exploration.

**Rationale**: Spec recommends config defaults; query override supports ad-hoc experimentation without redeploy. Same pattern as existing `min_sample` in `/evaluation/top-pairs`.
