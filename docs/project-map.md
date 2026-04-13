# Project Map

Quick navigation guide for AI agents. Answers: "Where do I edit X?"

## Minimum docs by task type

Use this with the **trivial change shortcut** in `AGENTS.md`: if the task matches the first row, reading this file alone is often enough.

| Task type | Read at least |
|-----------|----------------|
| Typo / comment-only / single-file UI copy (no API, DB, ingestion) | This file (`project-map.md`) |
| Naming, file placement, layer boundaries | `conventions.md` |
| Ingestion flow, CoC endpoints, pipeline order | `data-flow.md` |
| New or changed HTTP routes | `apps/api/routers/*.py` + `docs/api.md` (docs are hints) |
| Schema / migrations | `docs/database.md` + `supabase/migrations/` (+ apply DDL via **Supabase MCP** `apply_migration` when connected; see `AGENTS.md` “Agent tooling”) |

---

## Feature → File Map

### Dashboard (overview stats)
- **UI**: `apps/web/src/pages/Dashboard.tsx`
- **API**: `apps/api/routers/dashboard.py` → `GET /api/dashboard`
- **Data**: Aggregates from `clans`, `players`, `wars`, `capital_raids` tables

### Players (list + detail)
- **UI list**: `apps/web/src/pages/Players.tsx`
- **UI detail**: `apps/web/src/pages/PlayerDetail.tsx`
- **API**: `apps/api/routers/players.py` → `GET /api/players`, `GET /api/players/{tag}`, `GET /api/players/{tag}/activity`, `DELETE /api/players/{tag}`
- **Ingestion**: `apps/ingestion/db.py` → `upsert_player()`
- **Activity chart data**: `apps/ingestion/player_activity.py`, `apps/web/src/components/AttackActivityHeatmap.tsx`

### Wars (list + detail)
- **UI list**: `apps/web/src/pages/Wars.tsx` (Logs / Players subtabs; player leaderboard `apps/web/src/components/WarPlayersLeaderboard.tsx`)
- **UI detail**: `apps/web/src/pages/WarDetail.tsx`
- **API**: `apps/api/routers/wars.py` → `GET /api/wars`, `GET /api/wars/player-stats`, `GET /api/wars/players/{tag}/history`, `GET /api/wars/{id}`, `DELETE /api/wars/{id}`
- **Ingestion**: `apps/ingestion/db.py` → `upsert_war()`, `upsert_war_attacks()`, `resolve_stale_wars()`

### Capital Raids (list + detail)
- **UI list**: `apps/web/src/pages/Raids.tsx`
- **UI detail**: `apps/web/src/pages/RaidDetail.tsx`
- **API**: `apps/api/routers/raids.py` → `GET /api/raids`, `GET /api/raids/{id}`, `DELETE /api/raids/{id}`
- **Ingestion**: `apps/ingestion/db.py` → `upsert_capital_raid()`, `upsert_raid_members()`

### Legends League (leaderboard + player detail)
- **UI**: `apps/web/src/pages/Legends.tsx` (biggest page, ~27KB)
- **API**: `apps/api/routers/legends.py` → `GET /api/legends`, `GET /api/legends/{tag}/days`, `GET /api/legends/{tag}`
- **Ingestion**: `apps/ingestion/legends.py` (battle-log cursor-based ingestion)
- **Domain logic**: `apps/shared/legends_roster.py` (roster queries, `current_legends_day()`)
- **Cursor logic**: `apps/shared/battlelog.py` (snapshot comparison, new attack detection)

### Tracked Clans (admin-managed tracking list)
- **UI**: `apps/web/src/pages/TrackedClans.tsx`
- **API**: `apps/api/routers/tracked_clans.py` → `GET /api/tracked-clans`, `POST`, `DELETE`
- **Ingestion**: `apps/ingestion/db.py` → `get_tracked_clans()`

### Tracked Players (admin-managed player pins)
- **UI**: `apps/web/src/pages/TrackedPlayers.tsx` (~19KB)
- **API**: `apps/api/routers/tracked_players.py` → `GET /api/tracked-players`, `POST`, `PATCH`, `DELETE`
- **Tag normalization**: `_normalize_player_tag()` in `apps/api/routers/tracked_players.py`
- **Ingestion**: `apps/ingestion/db.py` → `get_tracked_player_tags()`

### Admin
- **UI admin context**: `apps/web/src/lib/AdminContext.tsx` (session-scoped key)
- **API**: `apps/api/routers/admin.py` → `POST /api/admin/verify`
- **Auth guard**: `apps/api/auth.py` → `require_admin` dependency

---

## Cross-Cutting Modules

| Module | File | Purpose |
|--------|------|---------|
| Config | `apps/shared/config.py` | Loads `.env.local`, exports all config vars |
| Config (API) | `apps/api/config.py` | Re-exports `shared.config` |
| Config (Ingestion) | `apps/ingestion/config.py` | Re-exports `shared.config` |
| Logging | `apps/shared/logutil.py` | JSON-line formatter, `request_id` / `ingestion_run_id` context |
| API DB | `apps/api/database.py` | Per-request Supabase client factory |
| Ingestion DB | `apps/ingestion/db.py` | Singleton Supabase client, all upsert functions |
| Error Mapping | `apps/api/supabase_errors.py` | PostgREST error → HTTP exception |
| API Client (FE) | `apps/web/src/lib/api.ts` | Typed fetch wrapper + all TS interfaces |

---

## Key Files at a Glance

| File | Lines | What it does |
|------|-------|-------------|
| `apps/api/main.py` | ~130 | FastAPI app, middleware, CORS, router registration |
| `apps/ingestion/ingest.py` | ~181 | Orchestrates one full ingestion run |
| `apps/ingestion/db.py` | ~489 | All Supabase upsert/query helpers for ingestion |
| `apps/web/src/lib/api.ts` | ~319 | Every API call + all TypeScript interfaces |
| `apps/web/src/pages/Legends.tsx` | ~780+ | Most complex page (leaderboard, player detail, heatmaps) |
| `apps/api/routers/tracked_players.py` | ~287 | CRUD + validation for tracked players |
| `apps/api/routers/legends.py` | ~231 | Legends leaderboard aggregation + detail |
| `apps/shared/config.py` | ~27 | All env var loading |
| `apps/shared/logutil.py` | ~120 | Structured logging setup |

---

## Database Migrations

Located in `supabase/migrations/`, ordered `001`–`020`:

| # | File | Creates |
|---|------|---------|
| 001 | `001_core_tables.sql` | `clans`, `tracked_clans`, `players` |
| 002 | `002_wars.sql` | `wars`, `war_attacks` |
| 003 | `003_capital_raids.sql` | `capital_raids`, `raid_members` |
| 004 | `004_player_roster_and_tracked_players.sql` | `tracked_players`, roster columns on `players` |
| 005 | `005_legends.sql` | `legends_battles` |
| 006–008 | Various | Column additions: `display_name`, `role` display |
| 009 | `009_player_attack_activity.sql` | `player_battlelog_cursor`, `player_attack_events` |
| 010 | `010_tracked_players_tracking_group.sql` | `tracking_group` column on `tracked_players` |
| 011 | `011_legends_battlelog_cursor.sql` | `legends_battlelog_cursor` |
| 012 | `012_tracked_players_legends_bracket.sql` | `legends_bracket` column |
| 013 | `013_player_attack_counts_since.sql` | RPC `player_attack_counts_since` for accurate list `attacks_7d` |
| 014 | `014_war_attacks_home_attacker.sql` | `war_attacks.is_home_attacker`; RPCs `war_player_leaderboard_stats`, `war_player_attack_history` |
| 015 | `015_war_stats_exclude_farming.sql` | `war_player_leaderboard_stats` excludes farming hits (1★, dest &lt; 40%) |
| 016 | `016_legends_confirmation_queue.sql` | `legends_confirmation_queue` (deferred legends diff) |
| 017 | `017_war_player_stats_war_window.sql` | War RPCs gain `p_max_wars` (last N ended wars by `start_time`) — superseded by 018 for deployed DBs that apply 018 |
| 018 | `018_war_player_stats_attack_window.sql` | RPCs use `p_max_attacks` (last N offense + last N defense rows per player); history adds `missed` rows; API query `last_attacks`. Hosted DB may list this DDL as two applied migrations (`war_player_stats_attack_window_leaderboard` + `_history`) if applied via Supabase MCP in two steps. |
| 019 | `019_war_player_attack_window_param_bind.sql` | Window `WHERE` uses `(SELECT p_max_attacks)` so the limit binds correctly inside `RETURNS TABLE` RPC bodies. |
| 020 | `020_war_missed_count_all_swings.sql` | Missed slots use all home offensive swings (farming included) so history does not duplicate farming rows as synthetic missed. |

---

## Tests

Located in `tests/`:

| File | Tests |
|------|-------|
| `test_smoke_api.py` | Basic route reachability |
| `test_admin.py` | Admin auth, verify, delete operations |
| `test_failure_paths.py` | Error handling, invariant violations |
| `test_tracked_clans_admin.py` | Tracked clans CRUD |
| `test_tracked_players_admin.py` | Tracked players CRUD + validation (~300 lines) |
| `test_legends_cursor.py` | Legends battle-log cursor logic |
| `test_legends_leaderboard_agg.py` | Legends aggregation unit tests |
| `test_integration_dashboard_flow.py` | Dashboard end-to-end flow |
| `test_ingestion_supercell_errors.py` | Supercell API error handling |
| `contract/` | Pydantic contract shape validation |
| `regression/` | Regression tests |
