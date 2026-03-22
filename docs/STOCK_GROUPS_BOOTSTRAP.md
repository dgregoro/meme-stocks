# Stock Groups Bootstrap

## What stock_groups Is Used For

The `stock_groups` table is the **candidate universe** for leader-follower signal detection:

1. The system detects **leaders** (stocks with significant price/volume moves).
2. For each leader, it looks up which groups that symbol belongs to.
3. Other symbols in the same group become **follower candidates** (filtered by `follower_move_threshold_pct`).
4. Candidates that move in the same direction as the leader can produce signals.

**Important**: Without any rows in `stock_groups`, leader detection still runs, but follower candidate generation returns **zero**. No signals will be emitted.

This is **scaffolding**, not the final intelligence of the system. Future versions may learn leader-follower relationships automatically; for now, groups are curated and seeded manually.

---

## How to Seed stock_groups

Run the bootstrap command:

```bash
python -m backend.app.cli seed stock-groups
```

This command:

- Is **idempotent**: running twice does not create duplicates
- Creates missing stocks with minimal metadata when needed (FK integrity)
- Logs how many rows were inserted vs skipped
- Reports any symbols that could not be added (with warnings)
- Does **not** wipe existing user-defined groups

From project root:

```bash
# Local development
python -m backend.app.cli seed stock-groups

# In container
podman exec -it <container> python -m backend.app.cli seed stock-groups
```

---

## How to Inspect stock_groups

### API (read-only)

| Endpoint | Description |
|---------|-------------|
| `GET /api/stock-groups` | List all groups with symbol counts. `is_empty: true` when no groups exist |
| `GET /api/stock-groups/{group_id}` | List symbols in a specific group |

Example:

```bash
curl http://localhost:8000/api/stock-groups
```

Response:

```json
{
  "total_rows": 34,
  "groups": [
    {"group_id": "banks", "symbol_count": 6},
    {"group_id": "megacap_tech", "symbol_count": 5},
    {"group_id": "meme", "symbol_count": 3},
    {"group_id": "oil", "symbol_count": 6},
    {"group_id": "semis", "symbol_count": 10}
  ],
  "is_empty": false
}
```

### CLI

There is no dedicated CLI for inspection; use the API or query the database directly.

---

## Bootstrap Dataset

The seed data lives in `backend/app/data/stock_group_seed.py` as `BOOTSTRAP_GROUPS`:

| group_id | Symbols |
|----------|---------|
| semis | NVDA, AMD, MU, AVGO, QCOM, INTC, AMAT, LRCX, KLAC, ON |
| banks | JPM, BAC, WFC, C, GS, MS |
| oil | XOM, CVX, COP, EOG, OXY, SLB |
| megacap_tech | AAPL, MSFT, GOOGL, AMZN, META |
| meme | GME, AMC, BB |

Edit `BOOTSTRAP_GROUPS` to add or remove groups/symbols, then re-run `seed-stock-groups`.

---

## Empty-State Warning

When `stock_groups` is empty and leader-follower detection is enabled:

- **Startup**: A warning is logged
- **Leader-follower job run**: A warning is logged before detection

The warning explains that leader detection may work but follower candidate generation will return zero, and suggests running: `python -m backend.app.cli seed stock-groups`.

---

## Limitations

- Groups are static and curated; no automatic learning of leader-follower pairs
- Missing symbols: if a symbol in the seed is not in `stocks`, the seeder creates a minimal stock (name `{symbol} (bootstrap)`) to satisfy the FK
- This bootstrap does not replace or preclude future learned pairwise relationships
- No admin UI; inspect via API or DB
