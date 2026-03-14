# Notification API Contract

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## Endpoint: GET /api/notifications

List unread notifications (volume spikes, price moves, sentiment shifts, combined signals).

### Response Model (Extended)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Notification ID |
| stock_symbol | str | yes | Stock symbol |
| type | str | yes | 'volume_spike', 'price_movement', 'sentiment_shift', 'combined_signal' |
| message | str | yes | Human-readable summary |
| severity | str | yes | 'low', 'medium', 'high' |
| created_at | str | yes | ISO 8601 datetime |
| read | bool | yes | Whether user has seen it |
| signal_metadata | object \| null | no | Present when type='combined_signal'. Absent or null for legacy/single-signal |

### signal_metadata (when present)

| Field | Type | Description |
|-------|------|-------------|
| evaluation_timestamp | string | ISO 8601 when evaluation occurred |
| combined_score | number | Total weighted score |
| threshold | number | Threshold used |
| signals_evaluated | array | All evaluated signals (fired and not fired) |

### signals_evaluated item

| Field | Type | Description |
|-------|------|-------------|
| signal_type | str | 'sentiment_shift', 'price_movement', 'volume_spike', 'rsi_signal' |
| raw_value | str \| number \| null | Raw signal value; null if not evaluated |
| fired | bool | Whether signal contributed |
| contribution | number | Weight contributed (0 if not fired) |
| reason | str \| null | Optional (e.g., why not fired) |

### Example Response

```json
[
  {
    "id": 42,
    "stock_symbol": "GME",
    "type": "combined_signal",
    "message": "Multiple signals aligned: sentiment +0.4, volume 2.5x avg, price +6%",
    "severity": "high",
    "created_at": "2026-03-13T16:30:00Z",
    "read": false,
    "signal_metadata": {
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
          "signal_type": "price_movement",
          "raw_value": "Price moved 6.20% (up)",
          "fired": true,
          "contribution": 2.0,
          "reason": null
        },
        {
          "signal_type": "rsi_signal",
          "raw_value": null,
          "fired": false,
          "contribution": 0.0,
          "reason": "RSI neutral"
        }
      ]
    }
  }
]
```

### Backward Compatibility

- Clients may ignore `signal_metadata`
- For non-combined notifications, `signal_metadata` is null or omitted
