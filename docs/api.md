# API Reference

FastAPI backend at `apps/api/`. Base path: `/api`.

**Start**: `uvicorn apps.api.main:app --reload`

---

## Authentication

- **Admin routes** require `Authorization: Bearer <ADMIN_API_KEY>` header
- If `ADMIN_API_KEY` env var is unset → admin routes return **503 Service Unavailable**
- Auth guard: `apps/api/auth.py` → `require_admin` FastAPI dependency
- Read-only endpoints require no authentication

---

## Common Response Patterns

### Paginated List
```json
{
  "data": [...],
  "total": 42,
  "page": 1,
  "page_size": 25
}
```

### Error Response
```json
{
  "detail": {
    "error": "machine_readable_code",
    "hint": "Human-readable suggestion",
    "request_id": "abc-123"
  }
}
```

---

## Endpoints

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | Returns `{"status": "ok"}` |

---

### Dashboard

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/dashboard` | No | Aggregate stats: total clans/players/wars/raids, active wars, 5 most recent wars and raids |

---

### Players

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/players` | No | Paginated player list. Query: `sort`=`roster` (default), `name`, `trophies`, `attacks_7d`; `order`=`asc`|`desc` (default `asc`; ignored when `sort=roster`). Each row includes `attacks_7d` (attacks in the last 7 days). |
| `GET` | `/api/players/{tag}` | No | Single player detail |
| `GET` | `/api/players/{tag}/activity` | No | Attack timestamps (last ~90 days) |
| `DELETE` | `/api/players/{tag}` | Admin | Delete player record |

**Query params** (list): `page`, `page_size`, `clan_tag`, `search` (ILIKE on name)

---

### Wars

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/wars` | No | Paginated war list |
| `GET` | `/api/wars/player-stats` | No | Per-player war leaderboard for one **tracked** `clan_tag` (ended wars; RPC `war_player_leaderboard_stats`). **Farming hits omitted** (1 star and destruction &lt; 40%). |
| `GET` | `/api/wars/players/{tag}/history` | No | That player’s offensive/defensive war rows for one **tracked** `clan_tag` (ended wars); offense list includes synthetic missed slots (`missed_attack: true`) |
| `GET` | `/api/wars/{id}` | No | War detail with nested `attacks[]` |
| `DELETE` | `/api/wars/{id}` | Admin | Delete war record |

**Query params** (list): `page`, `page_size`, `clan_tag`, `state`

**Query params** (`player-stats`): `clan_tag` (required), `sort` (allowlisted field name, default `avg_offense_stars`), `order` (`asc` \| `desc`, default `desc`), `last_attacks` (optional: `5`, `10`, or `15` — per player, last N home offensive swings and last N defensive rows by recency; omit for all ended wars)

**Query params** (`players/{tag}/history`): `clan_tag` (required), `last_attacks` (optional, same as `player-stats`). `{tag}` is URL-encoded player tag (e.g. `%23...`).

---

### Raids (Capital Raids)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/raids` | No | Paginated raid list |
| `GET` | `/api/raids/{id}` | No | Raid detail with nested `members[]` |
| `DELETE` | `/api/raids/{id}` | Admin | Delete raid record |

**Query params** (list): `page`, `page_size`, `clan_tag`

---

### Legends League

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/legends` | No | Today's leaderboard: per-player attack/defense totals, ranks, tracked status |
| `GET` | `/api/legends/{tag}/days` | No | Available legends days for a player |
| `GET` | `/api/legends/{tag}` | No | Player's attacks and defenses for a legends day |

**Query params** (`/api/legends/{tag}`): `legends_day` (YYYY-MM-DD, defaults to current)

**`GET /api/legends` row fields**: Each item includes `left_tracked_roster_at` (ISO timestamp or `null`) when the player is no longer on a tracked clan roster; the Legends UI demotes and greys those rows unless `is_always_tracked` is true (July or external tracked list).

---

### Tracked Clans

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/tracked-clans` | No | All tracked clans (with joined clan metadata) |
| `POST` | `/api/tracked-clans` | Admin | Add clan tag to tracking list |
| `DELETE` | `/api/tracked-clans/{tag}` | Admin | Remove clan from tracking list |

**POST body**: `{ "clan_tag": "#TAG", "note": "optional" }`

---

### Tracked Players

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/tracked-players` | No | All tracked players (optionally filtered) |
| `POST` | `/api/tracked-players` | Admin | Add player to tracking list |
| `PATCH` | `/api/tracked-players/{tag}` | Admin | Update display_name, tracking_group, or legends_bracket |
| `DELETE` | `/api/tracked-players/{tag}` | Admin | Remove player from tracking list |

**Query params** (list): `tracking_group` (`clan_july` or `external`)

**POST body**:
```json
{
  "player_tag": "#TAG",
  "display_name": "optional",
  "note": "optional",
  "tracking_group": "clan_july",
  "legends_bracket": 1
}
```

**PATCH body** (at least one field required):
```json
{
  "display_name": "New Name",
  "tracking_group": "external",
  "legends_bracket": 2
}
```

**Tag normalization**: tags are auto-uppercased and `#` is prepended if missing.

---

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/admin/verify` | Admin | Verify admin key validity; returns `{ "ok": true }` |

---

## CORS

Configured in `main.py`. Default origins:
- `http://localhost:5173`, `http://127.0.0.1:5173`
- `https://jeff-tian-dev.github.io`
- `https://clashtracker.duckdns.org`
- Additional via `CORS_ORIGINS` env var (comma-separated)

---

## Request Middleware

Every request gets:
- **`X-Request-Id`** response header (from incoming header or auto-generated UUID)
- Structured log lines with `request_id`, method, path, status, duration
- Validation errors return 422 with `request_id` and actionable `hint`

---

## Error Codes

| Status | When |
|--------|------|
| 400 | Invalid parameters (e.g. bad `legends_day` format) |
| 404 | Resource not found |
| 409 | Duplicate tracked player/clan (conflict) |
| 422 | Request validation failed |
| 500 | Invariant violation (unexpected DB response) |
| 502 | Database write failed |
| 503 | `ADMIN_API_KEY` not configured |
