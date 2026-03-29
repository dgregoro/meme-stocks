# Research: 016 Mean reversion after extreme moves

## Forward-return anchor

- **Decision**: Use **event_date** close as reference for `compute_forward_return(symbol, event_date, h, ...)`, matching 015 and leader-follower evaluation.
- **Rationale**: One convention across research features; documented in contracts.
- **Alternatives considered**: Next-day open — deferred.

## Tie-break when both thresholds could fire

- **Decision**: If return_pct ≥ up threshold **and** return_pct ≤ −down threshold (only possible with **asymmetric** thresholds), classify by **larger absolute return**: if `abs(return_pct)` is driven by the positive side use `extreme_up`, else `extreme_down`; if exactly ambiguous, prefer **`extreme_up`** (documented arbitrary tie-break).
- **Rationale**: Rare edge case; symmetric defaults 5%/5% never double-fire.
- **Alternatives considered**: Drop event — rejected as surprising.

## Horizons configuration

- **Decision**: New setting **`extreme_move_research_horizons`** default **`"1,3,5"`**, parsed like `volume_spike_research_horizons`.
- **Rationale**: Decouples from volume-spike env; same numeric defaults as other evaluation.
- **Alternatives considered**: Reuse `leader_follower_evaluation_horizons` only — rejected to keep 016 self-contained in config keys.

## Min close filter

- **Decision**: **`extreme_move_research_min_close`** default **0** (disabled).
- **Rationale**: Spec open question; optional guard without changing default behavior.
- **Alternatives considered**: Hard exclude pennies in MVP — deferred.
