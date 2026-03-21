# Data Model: Combined Signal Alerts

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## Storage: Text Column + JSON Serialization

**Decision**: `signal_metadata` is a **Text** column. JSON is serialized with `json.dumps()` and deserialized with `json.loads()`. Provide explicit helpers: `serialize_signal_metadata(ev: CombinedEvaluation) -> str` and `parse_signal_metadata(s: str | None) -> dict | None`. Add unit tests for round-trip and invalid/empty input handling.

**Rationale**: Aligns with repo pattern (`job_run_history.metrics_json`). No SQLAlchemy JSON type used elsewhere.

## In-Memory Entities (Dataclasses)

### SignalEvaluated

A single signal evaluated for a ticker. All evaluated signals appear in metadata for debugging.

| Field | Type | Description |
|-------|------|-------------|
| signal_type | str | 'sentiment_shift', 'price_movement', 'volume_spike', 'rsi_signal' |
| raw_value | str \| float | Raw value (e.g., message text, RSI number) |
| fired | bool | Whether signal contributed (met detector threshold) |
| contribution | float | Weight contributed (0 if not fired) |
| reason | str \| None | Optional explanation (e.g., why not fired) |

### CombinedEvaluation

Result of aggregating signals for a ticker.

| Field | Type | Description |
|-------|------|-------------|
| symbol | str | Stock symbol |
| signals_evaluated | list[SignalEvaluated] | All evaluated signals |
| combined_score | float | Sum of contributions |
| threshold | float | Threshold used |
| threshold_met | bool | combined_score >= threshold |
| evaluation_timestamp | datetime | When evaluation occurred |

## Persisted Schema Changes

### Notification (Existing Model — Extended)

**New column**:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| signal_metadata | Text | Yes | JSON string: evaluation_timestamp, combined_score, threshold, signals_evaluated |

**signal_metadata JSON structure** (when present):

```json
{
  "evaluation_timestamp": "2026-03-13T16:30:00Z",
  "combined_score": 5.0,
  "threshold": 4.0,
  "signals_evaluated": [
    {
      "signal_type": "sentiment_shift",
      "raw_value": "Sentiment shifted positive by 0.45",
      "fired": true,
      "contribution": 2.0,
      "reason": null
    },
    {
      "signal_type": "volume_spike",
      "raw_value": "Volume 2.5x average",
      "fired": true,
      "contribution": 1.0,
      "reason": null
    },
    {
      "signal_type": "rsi_signal",
      "raw_value": null,
      "fired": false,
      "contribution": 0.0,
      "reason": "RSI not available"
    }
  ]
}
```

**Validation**:
- When `type="combined_signal"`, `signal_metadata` MUST be non-null and valid JSON
- `signals_evaluated`: array of objects with signal_type, raw_value, fired, contribution, reason (optional)
- `combined_score`, `threshold`: numbers >= 0
- `evaluation_timestamp`: ISO 8601 string

## Migration

Add column via database migration in `backend/app/data/database.py`. Use Text type. Migration must:
- Check if column exists before adding
- Default to NULL for existing rows
- Be idempotent
