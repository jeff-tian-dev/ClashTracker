# Database Schema

Supabase (hosted PostgreSQL). 15 ordered migrations in `supabase/migrations/`.

---

## Entity Relationship Diagram

```
tracked_clans (no FK)          tracked_players (no FK)
                                      │
clans ◄──────────────── players ──────┘ (via tag, but no FK)
  │                       │
  ├── wars                ├── legends_battles
  │     └── war_attacks   ├── legends_battlelog_cursor
  │                       ├── player_battlelog_cursor
  └── capital_raids       └── player_attack_events
        └── raid_members
```

---

## Tables

### `clans`
Primary tracking unit. Natural PK = Supercell tag.

| Column | Type | Notes |
|--------|------|-------|
| `tag` | TEXT PK | Supercell clan tag (e.g. `#2GRPGV0VL`) |
| `name` | TEXT NOT NULL | |
| `description` | TEXT | |
| `badge_url` | TEXT | Large badge URL |
| `clan_level` | INT | |
| `members_count` | INT | |
| `clan_points` | INT | |
| `clan_capital_points` | INT | |
| `war_frequency` | TEXT | |
| `war_win_streak` | INT | |
| `war_wins` / `war_ties` / `war_losses` | INT | |
| `war_league_id` | INT | |
| `capital_league_id` | INT | |
| `is_war_log_public` | BOOLEAN | |
| `updated_at` | TIMESTAMPTZ | Last ingestion update |

---

### `tracked_clans`
Admin-managed list of clans to ingest. **No FK to `clans`** — can be added before first ingestion.

| Column | Type | Notes |
|--------|------|-------|
| `clan_tag` | TEXT PK | |
| `note` | TEXT | Optional admin note |
| `added_at` | TIMESTAMPTZ | |

---

### `players`
Player profiles, overwritten on each ingestion run.

| Column | Type | Notes |
|--------|------|-------|
| `tag` | TEXT PK | Supercell player tag |
| `name` | TEXT NOT NULL | |
| `clan_tag` | TEXT FK → `clans.tag` | `ON DELETE SET NULL` |
| `town_hall_level` | INT | |
| `exp_level` | INT | |
| `trophies` / `best_trophies` | INT | |
| `war_stars` | INT | |
| `attack_wins` / `defense_wins` | INT | |
| `role` | TEXT | Display label (Leader/Co-leader/Elder/Member) |
| `war_preference` | TEXT | |
| `clan_capital_contributions` | INT | |
| `league_name` | TEXT | Prefers `leagueTier.name` over `league.name` |
| `updated_at` | TIMESTAMPTZ | |
| `left_tracked_roster_at` | TIMESTAMPTZ | Set when player leaves all tracked clans (migration 004) |
| `roster_sort_bucket` | SMALLINT GENERATED | 0 = active, 1 = left (migration 004) |

**Indexes**: `clan_tag`, `updated_at`, roster sort composite

---

### `tracked_players`
Admin-managed pins for always-tracked players. **No FK to `players`**.

| Column | Type | Notes |
|--------|------|-------|
| `player_tag` | TEXT PK | |
| `display_name` | TEXT | Resolved from `players.name` if blank (migration 007) |
| `note` | TEXT | Optional admin note |
| `added_at` | TIMESTAMPTZ | |
| `tracking_group` | TEXT NOT NULL DEFAULT `'clan_july'` | CHECK: `clan_july` or `external` (migration 010) |
| `legends_bracket` | INT DEFAULT 1 | 1 = upper, 2 = lower (migration 012) |

---

### `wars`
One row per clan war (deduplicated by composite key).

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `clan_tag` | TEXT FK → `clans.tag` | |
| `opponent_tag` / `opponent_name` | TEXT | |
| `state` | TEXT NOT NULL | `preparation`, `inWar`, `warEnded` |
| `team_size` / `attacks_per_member` | INT | |
| `preparation_start_time` / `start_time` / `end_time` | TIMESTAMPTZ | |
| `clan_stars` / `opponent_stars` | INT | |
| `clan_destruction_pct` / `opponent_destruction_pct` | NUMERIC(5,2) | |
| `result` | TEXT | `win`, `lose`, `tie`, or NULL (in progress) |
| `updated_at` | TIMESTAMPTZ | |

**Unique**: `(clan_tag, preparation_start_time)`
**Indexes**: `clan_tag`, `state`, `updated_at`

---

### `war_attacks`
Individual attacks within a war.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `war_id` | BIGINT FK → `wars.id` | `ON DELETE CASCADE` |
| `attacker_tag` / `defender_tag` | TEXT | |
| `stars` | INT | |
| `destruction_percentage` | NUMERIC(5,2) | |
| `attack_order` | INT | |
| `duration` | INT | Seconds, nullable |
| `is_home_attacker` | BOOLEAN | Nullable on legacy rows; `true` = attacker on tracked clan side (CoC `clan`), `false` = opponent side; set by ingestion (migration `014`) |

**Unique**: `(war_id, attacker_tag, attack_order)`

---

### `capital_raids`
Clan Capital raid weekend events.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `clan_tag` | TEXT FK → `clans.tag` | |
| `state` | TEXT NOT NULL | |
| `start_time` / `end_time` | TIMESTAMPTZ | |
| `capital_total_loot` | INT | |
| `raids_completed` / `total_attacks` / `enemy_districts_destroyed` | INT | |
| `offensive_reward` / `defensive_reward` | INT | |
| `updated_at` | TIMESTAMPTZ | |

**Unique**: `(clan_tag, start_time)`

---

### `raid_members`
Player contributions within a raid weekend.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `raid_id` | BIGINT FK → `capital_raids.id` | `ON DELETE CASCADE` |
| `player_tag` | TEXT | |
| `name` | TEXT | |
| `attacks` / `attack_limit` / `bonus_attack_limit` | INT | |
| `capital_resources_looted` | INT | |

**Unique**: `(raid_id, player_tag)`

---

### `legends_battles`
Legends League daily battle tracking.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `player_tag` | TEXT FK → `players.tag` | `ON DELETE CASCADE` |
| `opponent_tag` | TEXT | |
| `opponent_name` | TEXT | |
| `is_attack` | BOOLEAN | |
| `stars` | INT | |
| `destruction_pct` | INT | |
| `trophies` | INT | Trophy change (positive or negative) |
| `legends_day` | DATE | |
| `first_seen_at` | TIMESTAMPTZ DEFAULT NOW() | |

**Unique**: `(player_tag, opponent_tag, is_attack, stars, destruction_pct, legends_day)`
**Indexes**: `(player_tag, legends_day)`, `(legends_day)`

---

### `legends_battlelog_cursor`
Per-player cursor for legend-type battle log deduplication.

| Column | Type | Notes |
|--------|------|-------|
| `player_tag` | TEXT PK FK → `players.tag` | `ON DELETE CASCADE` |
| `cursor_snapshot` | JSONB | Newest battle fingerprint |
| `updated_at` | TIMESTAMPTZ | |

---

### `player_battlelog_cursor`
Per-player cursor for multiplayer battle log deduplication.

| Column | Type | Notes |
|--------|------|-------|
| `player_tag` | TEXT PK FK → `players.tag` | `ON DELETE CASCADE` |
| `cursor_snapshot` | JSONB | Newest battle fingerprint |
| `updated_at` | TIMESTAMPTZ | |

---

### `player_attack_events`
Multiplayer attack timestamps for activity heatmaps.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `player_tag` | TEXT FK → `players.tag` | `ON DELETE CASCADE` |
| `attacked_at` | TIMESTAMPTZ | |
| `opponent_tag` | TEXT DEFAULT '' | |

**Unique**: `(player_tag, attacked_at, opponent_tag)`
**Pruned**: events older than 14 days are deleted each ingestion run

---

## Functions

### `player_attack_counts_since(p_since timestamptz, p_tags text[])`

Returns `(player_tag, attack_count)` for each tag in `p_tags` that has at least one `player_attack_events` row with `attacked_at >= p_since`. Used by `GET /api/players` for `attacks_7d` so counts are not truncated by PostgREST max rows (migration `013`).

---

## Design Decisions

- **Natural PKs** for game entities (`clans.tag`, `players.tag`) — eliminates lookup joins during upsert
- **No FK from `tracked_*` to data tables** — tags can be tracked before first fetch
- **Composite unique constraints** for dedup — safe idempotent upserts
- **`ON DELETE CASCADE`** on child tables — automatic orphan cleanup
- **Indexes on all FKs and temporal columns** — supports API filtering without full scans
- **Generated column** (`roster_sort_bucket`) — efficient roster sorting
