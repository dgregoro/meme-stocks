# Data Model: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## In-Memory Entities (Dataclasses)

These are not persisted; they flow through the aggregation logic.

### SignalContribution

Represents a single signal that fired and its contribution to the combined score.

| Field | Type | Description |
|-------|------|-------------|
| kind | str | Signal type: 'sentiment_shift', 'price_movement', 'volume_spike', 'rsi_signal' |
| value | str \| float | Human-readable or numeric value (e.g., message text, RSI value) |
| weight | float | Weight applied (from config) |
| contribution | float | weight (if signal fired) or 0 |

### CombinedEvaluation

Result of aggregating signals for a ticker.

| Field | Type | Description |
|-------|------|-------------|
| symbol | str | Stock symbol |
| signals_fired | list[SignalContribution] | Which signals contributed (non-zero) |
| combined_score | float | Sum of contributions |
| threshold_met | bool | combined_score >= threshold |
| evaluated_at | datetime | When evaluation occurred |

## Persisted Schema Changes

### Notification (Existing Model — Extended)

**New column**:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| signal_metadata | JSON / Text | Yes | Structured explanation: `{"signals_fired": [...], "combined_score": float}` |

**signal_metadata structure** (when present):

```json
{
  "signals_fired": [
    {"kind": "sentiment_shift", "value": "Sentiment shifted positive by 0.45", "contribution": 2.0},
    {"kind": "volume_spike", "value": "Volume 2.5x average", "contribution": 1.0}
  ],
  "combined_score": 3.0
}
```

**Validation**:
- `signals_fired`: list of objects with `kind`, `value`, `contribution`
- `combined_score`: number >= 0
- When `type="combined_signal"`, `signal_metadata` MUST be non-null

## No New Tables

All entities are either in-memory (SignalContribution, CombinedEvaluation) or an extension of Notification. No new repositories.

## Migration

Add column via database migration in `backend/app/data/database.py` (project uses inline migrations, not Alembic). Migration must:
- Check if column exists before adding
- Default to NULL for existing rows
- Be idempotent
