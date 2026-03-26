# Data Flow

How data moves through the system, step by step.

---

## 1. External Source: Supercell CoC API

- **Base URL**: `https://api.clashofclans.com/v1`
- **Auth**: Bearer JWT (IP-whitelisted to Oracle VM)
- **Rate limits**: Per-second; current sequential approach stays under for <20 clans
- **Client**: `apps/ingestion/supercell_client.py` (synchronous httpx)

### Endpoints Used
| Endpoint | Returns |
|----------|---------|
| `GET /clans/{tag}` | Clan metadata + `memberList` |
| `GET /players/{tag}` | Full player profile |
| `GET /clans/{tag}/currentwar` | Active war state (or 403 if private) |
| `GET /clans/{tag}/capitalraidseasons` | Last N raid weekends |
| `GET /players/{tag}/battlelog` | Recent battle entries (Legends + multiplayer) |

---

## 2. Ingestion Pipeline

**Trigger**: systemd timer (hourly with jitter) → `python -m apps.ingestion.main`

### Orchestration Flow (`ingest.py` → `run_once()`)

1. **Query tracking lists** from Supabase:
   - `db.get_tracked_clans()` → list of `{clan_tag, note}`
   - `db.get_tracked_player_tags()` → list of player tags to always ingest

2. **For each tracked clan:**
   - `coc.get_clan(tag)` → `db.upsert_clan(data)`
   - For each member: `coc.get_player(member_tag)` → `db.upsert_player(data)`
   - `coc.get_current_war(tag)` → `db.upsert_war()` + `db.upsert_war_attacks()`
   - `db.resolve_stale_wars(tag)` — mark wars stuck in `inWar`/`preparation` past `end_time`
   - `coc.get_capital_raids(tag)` → `db.upsert_capital_raid()` + `db.upsert_raid_members()`

3. **For each always-tracked player** (not in any tracked clan):
   - `coc.get_player(tag)` → `db.upsert_player(data)`

4. **Roster reconciliation** (`db.reconcile_tracked_roster(active_tags)`):
   - Clear `left_tracked_roster_at` for active players
   - Stamp departure timestamp for players no longer in any tracked clan/player list

5. **Legends ingestion** (`legends.ingest_legends(client)`):
   - Get Legends roster tags from `shared/legends_roster.py`
   - Fetch battle logs → compare with cursor → extract new battles
   - Upsert into `legends_battles` table
   - Update `legends_battlelog_cursor`

6. **Player activity** (`player_activity.ingest_player_activity(client, active_tags)`):
   - Fetch battle logs for active players
   - Extract multiplayer attack timestamps
   - Upsert into `player_attack_events`
   - Prune events older than 14 days

### Error Handling
- **403 (private war log)**: logged, skipped
- **404 (missing clan/player)**: logged, skipped
- **Unhandled exceptions**: `sys.exit(1)` for systemd failure recording
- One clan's failure does not block others

---

## 3. Database (Supabase PostgreSQL)

### Write Pattern (Ingestion)
- All writes use `upsert` with `on_conflict` → **fully idempotent**
- Singleton Supabase client (`apps/ingestion/db.py`)
- Service-role key (bypasses RLS)

### Read Pattern (API)
- Fresh Supabase client per request (`apps/api/database.py`)
- Read-only for data tables
- Write access only for `tracked_clans` and `tracked_players` (admin-gated)

### Key Tables
```
clans → players (FK: clan_tag)
         ├→ wars → war_attacks (FK: war_id, CASCADE)
         ├→ capital_raids → raid_members (FK: raid_id, CASCADE)
         ├→ legends_battles (FK: player_tag, CASCADE)
         ├→ legends_battlelog_cursor (FK: player_tag, CASCADE)
         ├→ player_battlelog_cursor (FK: player_tag, CASCADE)
         └→ player_attack_events (FK: player_tag, CASCADE)
tracked_clans (no FK to clans — can pre-exist)
tracked_players (no FK to players — can pre-exist)
```

---

## 4. API Layer (FastAPI)

### Query Flow
1. Router handler receives HTTP request
2. `get_db()` creates fresh Supabase client
3. Query Supabase via REST API
4. Shape response (pagination, aggregation, nesting)
5. Return JSON

### Pagination Pattern
- Offset-based: `page` + `page_size` query params
- Response: `{ data: [...], total, page, page_size }`
- Used on: players, wars, raids

### Aggregation Pattern (Legends)
- Fetch raw `legends_battles` for the current legends day
- Aggregate per-player totals (attack/defense trophy sums, battle counts)
- Merge with roster (from `shared/legends_roster.py`)
- Enrich with player names and tracked status
- Sort by final trophies, assign ranks

---

## 5. Frontend (React SPA)

### Data Fetching Pattern
1. Page component mounts
2. `useEffect` calls `api.methodName()` from `src/lib/api.ts`
3. `api.ts` does `fetch(BASE + path)`, parses JSON
4. Component updates state → renders

### No Global State
- Each page owns its own data via `useState` + `useEffect`
- Only global contexts: `AdminContext` (session key), `ThemePreferenceContext`

### Auth Flow (Admin Mode)
1. User enters admin key in UI
2. Stored in `sessionStorage` via `AdminContext`
3. Mutations (POST/PATCH/DELETE) send `Authorization: Bearer {key}`
4. Backend validates via `require_admin` dependency

---

## Visual Summary

```
[Supercell API] ──httpx──→ [Ingestion Pipeline] ──upsert──→ [Supabase PostgreSQL]
                                                                      │
                                                              query (REST)
                                                                      │
                           [React SPA] ←──fetch──→ [FastAPI API] ─────┘
```
