# Research: S7 rule discovery (025)

## Decision: Single time split + fixed quantile grid

**Rationale**: Limits look-ahead: quantile thresholds are computed only from **train**-window feature values; **test** rows are evaluated only after `train_end`. This matches “frozen hold-out protocol” at MVP scope (one split).

**Alternatives considered**: Walk-forward (defer — more code); ML classifiers (out of scope for “pre-registered rule” spec).

## Decision: Single-condition rules only (`depth=1`)

**Rationale**: Caps complexity and keeps `n_rules` interpretable (`features × quantiles × 2` directions).

**Alternatives considered**: Conjunctions of two features (combinatorial explosion; deferred).

## Decision: CLI under `research rule-discovery`, not `evaluate daily-strategy`

**Rationale**: Spec requires separation from casual S1–S6 exploration; avoids implying merit/gate parity.

**Alternatives considered**: Top-level `s7-discover` on root CLI (rejected — keep research tooling grouped).

## Decision: Acknowledgement flag `--ack-overfitting-risk`

**Rationale**: Meets “no turn-key profit CLI” — explicit operator opt-in.

**Alternatives considered**: Environment-only acknowledgement (less visible); Typer prompts (bad for automation).

## Decision: Reuse S1-style vol / volume-z windows from settings

**Rationale**: Same `price_data` semantics as existing daily research; fewer magic numbers.

**Alternatives considered**: Separate S7-only windows (optional future env vars).

## Decision: Output JSON includes `ResearchRunEnvelope`

**Rationale**: Aligns with spec acceptance and `research_execution` package for future storage.

**Alternatives considered**: CSV-only output (insufficient for audit metadata).
