# Notification API Contract

**Branch**: 002-combined-signal-alerts | **Date**: 2026-03-13

## Endpoint: GET /api/notifications

List unread notifications (volume spikes, price moves, sentiment shifts, combined signals).

### Response Model (Extended)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int | yes | Notification ID |
| stock_symbol | str | yes | Stock symbol |
| type | str | yes | Notification type: 'volume_spike', 'price_movement', 'sentiment_shift', 'combined_signal' |
| message | str | yes | Human-readable summary |
| severity | str | yes | 'low', 'medium', 'high' |
| created_at | str | yes | ISO 8601 datetime |
| read | bool | yes | Whether user has seen it |
| signal_metadata | object \| null | no | **NEW**: Present when type='combined_signal'. Absent or null for legacy/single-signal notifications |

### signal_metadata (when present)

| Field | Type | Description |
|-------|------|-------------|
| signals_fired | array | List of contributing signals |
| combined_score | number | Total weighted score that triggered the alert |

### signals_fired item

| Field | Type | Description |
|-------|------|-------------|
| kind | str | 'sentiment_shift', 'price_movement', 'volume_spike', 'rsi_signal' |
| value | str | Human-readable signal value (e.g., "Volume 2.5x average") |
| contribution | number | Weight contributed to combined score |

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
      "signals_fired": [
        {"kind": "sentiment_shift", "value": "Sentiment shifted positive by 0.45", "contribution": 2.0},
        {"kind": "volume_spike", "value": "Volume 2.5x average", "contribution": 1.0},
        {"kind": "price_movement", "value": "Price moved 6.20% (up)", "contribution": 2.0}
      ],
      "combined_score": 5.0
    }
  }
]
```

### Backward Compatibility

- Clients that do not expect `signal_metadata` may ignore it.
- For notifications with type other than 'combined_signal', `signal_metadata` is null or omitted.
