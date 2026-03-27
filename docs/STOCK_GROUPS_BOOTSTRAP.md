# Stock Groups Bootstrap

## What stock_groups Is Used For

The `stock_groups` table is the **candidate universe** for leader-follower signal detection:

1. **Leader detection** is restricted to symbols present in `stock_groups`. Only these symbols are scanned for significant price/volume moves.
2. For each detected leader, the system looks up which groups that symbol belongs to.
3. Other symbols in the same group become **follower candidates** (filtered by `follower_move_threshold_pct`).
4. Candidates that move in the same direction as the leader can produce signals.

**Important**: Without any rows in `stock_groups`, leader detection **short-circuits** (no leaders are detected). The pipeline returns early with `grouped_leader_universe_size: 0` and zero signals.

This is **scaffolding**, not the final intelligence of the system. Future versions may learn leader-follower relationships automatically; for now, groups are curated and seeded manually.

---

## Bootstrap-Phase Leader Scoping

During the bootstrap phase, leader detection uses **only** the distinct symbols in `stock_groups` — not the full stock universe. This is intentional:

- **Coherent pipeline**: Any detected leader has a plausible path to follower candidates, because follower candidates also come from groups. Previously, leaders could be detected from the full universe (e.g. 1600+ symbols) while followers came only from groups, causing many leaders with zero follower candidates.
- **Debuggability**: With a small, curated universe, runs are easier to reason about and evaluate.
- **Future direction**: The system may later add learned pairwise relationships or broader discovery. For now, restricting leaders to grouped symbols keeps the pipeline coherent and evaluable.

This design does **not** constitute true follower discovery. It is a structural alignment so that during bootstrap, any detected leader can logically produce follower candidates from the same curated groups.

---

## How to Populate stocks and Seed stock_groups

The stock_groups seed requires symbols to exist in the `stocks` table (FK constraint). Populate stocks first:

```bash
# 1. Create Stock rows for all BOOTSTRAP_GROUPS symbols
python -m backend.app.cli seed stocks

# 2. Add those symbols to stock_groups
python -m backend.app.cli seed stock-groups
```

**seed stocks** creates minimal `Stock` rows for every symbol in `BOOTSTRAP_GROUPS`. Idempotent.

**seed stock-groups**:

- Is **idempotent**: running twice does not create duplicates
- Skips symbols not in `stocks` table (logs warning, does not create)
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

The seed data lives in `backend/app/data/stock_group_seed.py` as `BOOTSTRAP_GROUPS`. These are curated peer groups: liquid, established sector names with clear relationships. Expansion is intentionally conservative.

| group_id | Symbol count | Symbols |
|----------|--------------|---------|
| semis | 20 | NVDA, AMD, MU, AVGO, QCOM, INTC, AMAT, LRCX, KLAC, ON, MCHP, MPWR, TXN, SWKS, QRVO, ADI, NXPI, TER, ASML, MRVL |
| banks | 13 | JPM, BAC, WFC, C, GS, MS, USB, PNC, TFC, BK, SCHW, COF, AXP |
| oil | 13 | XOM, CVX, COP, EOG, OXY, SLB, HAL, PSX, MPC, VLO, DVN, FANG, APA |
| megacap_tech | 11 | AAPL, MSFT, GOOGL, AMZN, META, ORCL, CRM, ADBE, NFLX, NOW, IBM |
| meme | 5 | GME, AMC, BB, KOSS, BYND |

**Note**: Symbols not present in the `stocks` table are skipped (with a warning). Run `python -m backend.app.cli seed stocks` first to populate stocks for all bootstrap symbols.

---

## Empty-State Warning

When `stock_groups` is empty and leader-follower detection is enabled:

- **Startup**: A warning is logged
- **Leader-follower job run**: The pipeline short-circuits; no leaders are detected. Metrics include `grouped_leader_universe_size: 0`. `GET /api/leader-follower/status` returns `empty_reason: "stock_groups_empty"`.

To enable leader-follower detection, run: `python -m backend.app.cli seed stock-groups`.

---

## Limitations

- Groups are static and curated; no automatic learning of leader-follower pairs
- Missing symbols: if a symbol in the seed is not in `stocks`, the seeder skips it (logs warning, reports in `symbols_skipped`). Run `seed stocks` first to populate stocks.
- This bootstrap does not replace or preclude future learned pairwise relationships
- No admin UI; inspect via API or DB
