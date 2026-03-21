# Data Model: Leader-Follower Signal Detection

**Entities** — New tables and models for this feature.

---

## 1. StockGroup

**Table**: `stock_groups`

**Purpose**: Stores stock-to-group membership. One symbol may appear in multiple groups. Primary group for follower selection = lexicographically smallest `group_id` when symbol has multiple rows.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INTEGER | No | PK, autoincrement |
| group_id | VARCHAR(64) | No | e.g. 'meme', 'tech_mega' |
| stock_symbol | VARCHAR(16) | No | FK → stocks.symbol |
| created_at | DATETIME | No | Default now(UTC) |

**Unique constraint**: (group_id, stock_symbol) — no duplicate memberships.

**Index**: (stock_symbol) for lookup by symbol; (group_id) for lookup by group.

---

## 2. LeaderEvent

**Table**: `leader_events`

**Purpose**: Records a detected significant move (leader) at a given date.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INTEGER | No | PK, autoincrement |
| leader_symbol | VARCHAR(16) | No | FK → stocks.symbol |
| event_date | DATE | No | Date of the move |
| return_pct | FLOAT | No | 1-day return % |
| volume_ratio | FLOAT | No | vs rolling avg |
| direction | VARCHAR(8) | No | 'up' or 'down' |
| created_at | DATETIME | No | Default now(UTC) |

**Index**: (event_date), (leader_symbol, event_date) for lookups.

---

## 3. LeaderFollowerSignal

**Table**: `leader_follower_signals`

**Purpose**: A follower opportunity signal linking leader and follower with strength and metrics.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INTEGER | No | PK, autoincrement |
| leader_symbol | VARCHAR(16) | No | FK → stocks.symbol |
| follower_symbol | VARCHAR(16) | No | FK → stocks.symbol |
| group_id | VARCHAR(64) | No | From stock_groups |
| signal_date | DATE | No | Same as leader event_date |
| strength_score | FLOAT | No | 0–1; weighted combo |
| leader_return_pct | FLOAT | No | Denormalized for audit |
| leader_volume_ratio | FLOAT | No | Denormalized |
| metrics_json | TEXT | Yes | Optional extra |
| created_at | DATETIME | No | Default now(UTC) |

**Index**: (signal_date), (leader_symbol, follower_symbol, signal_date) for deduplication check.

---

## Config Keys (config.py)

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| leader_follower_enabled | bool | False | Feature flag; job not scheduled when False |
| leader_return_threshold_pct | float | 5.0 | Min abs return % for leader |
| leader_volume_spike_threshold | float | 1.5 | Min volume ratio for leader |
| leader_follower_cooldown_days | int | 1 | Dedup window |
| follower_move_threshold_pct | float | 3.0 | Exclude follower if already moved this much |
| leader_follower_job_hour | int | 17 | Cron hour (UTC or local per config) |
| leader_follower_strength_weight_return | float | 0.6 | w_r for strength_score |
| leader_follower_strength_weight_volume | float | 0.4 | w_v for strength_score |
| leader_follower_norm_return_cap_pct | float | 15.0 | Cap for norm(return) |
| leader_follower_norm_volume_cap | float | 4.0 | Cap for norm(volume_ratio) |

---

## Migration

- Add tables via `Base.metadata.create_all()` — new models registered in `main.py` imports.
- If explicit migration needed (e.g. SQLite DDL), add `_migrate_*` in `database.py` following existing pattern.
