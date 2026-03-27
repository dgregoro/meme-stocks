# Research: Leader-Follower Execution and Paper Trading (011)

**Status**: Complete (no open NEEDS CLARIFICATION items)

## R1 — Trading calendar without an exchange calendar API

- **Decision**: Derive tradable dates from existing daily `price_data` rows per symbol (sorted dates).
- **Rationale**: Matches available bars; avoids external dependencies and lookahead; aligns with backfilled data.
- **Alternatives considered**: Third-party market calendar (extra dependency); fixed weekday-only rule (incorrect around holidays).

## R2 — Determinism and idempotency

- **Decision**: Sort signals and ties with explicit ordering `(signal_date, leader, follower)` and ranking `(−strength, −leader_return, follower_symbol)`; persist each CLI/API run as a new row (same inputs → same metrics when DB state identical).
- **Rationale**: Reproducible research; audit trail of runs.
- **Alternatives considered**: Content-hash dedup of runs (deferred; adds complexity).

## R3 — Cost model

- **Decision**: Single round-trip cost in percentage points subtracted once from gross return per trade.
- **Rationale**: Matches spec assumption; simple sensitivity to cost parameter.
- **Alternatives considered**: Half-spread per side (more parameters); slippage model (out of MVP scope).

## R4 — Early exit rule

- **Decision**: First trading day after entry where close &lt; entry price exits at that close; else exit at fixed horizon.
- **Rationale**: Simple stop proxy using daily bars only.
- **Alternatives considered**: Intraday stop (no intraday data in scope).
