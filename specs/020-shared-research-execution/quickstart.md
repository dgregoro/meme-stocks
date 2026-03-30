# Quickstart: 020 Shared research execution

## Prerequisite

For Spec Kit scripts on branch `main`:

```bash
export SPECIFY_FEATURE=020-shared-research-execution
```

Or use a git branch named `020-<name>`.

## Use from Python

```python
from backend.app.services.research_execution import (
    ResearchRunEnvelope,
    apply_round_trip_cost,
    max_drawdown_from_equity,
    split_calendar_range,
)

from datetime import date

windows = split_calendar_range(date(2024, 1, 1), date(2024, 12, 31), 4)
net = apply_round_trip_cost(1.5, 0.1)  # gross +1.5%, 0.1% round-trip
dd = max_drawdown_from_equity([1.0, 1.1, 0.95, 1.02])

env = ResearchRunEnvelope.from_context(
    run_kind="manual_probe",
    strategy_family="s1",
    eval_start=date(2024, 6, 1),
    eval_end=date(2024, 8, 1),
    universe_label="demo10",
    symbols=["SPY", "QQQ"],
    cost_round_trip_bps=10.0,
)
print(env.to_json_dict())
```

## Tests

```bash
pytest backend/tests/test_research_execution.py -v
./scripts/verify.sh
```

## Docs

- [README](./README.md) — slice index
- [integration-conventions.md](./integration-conventions.md) — import graph
