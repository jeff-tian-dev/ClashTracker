# AI Agent Instructions

**This is the most important file in `/docs/`.** These rules govern how AI agents should behave when modifying this codebase.

---

## Before Making Any Change

1. **Read `/docs/project-map.md`** to locate the correct files
2. **Read `/docs/conventions.md`** for naming and structure rules
3. **Check for existing patterns** in similar files before writing new code
4. **Understand the data flow** (`/docs/data-flow.md`) before modifying ingestion or API

---

## Core Rules

### Do Not Duplicate Logic
- Before writing a new helper, check `apps/shared/` and the relevant subsystem
- Config is loaded once in `shared/config.py` — never read `os.environ` elsewhere
- Supabase client creation is in `api/database.py` (per-request) and `ingestion/db.py` (singleton)
- Tag normalization is in `api/routers/tracked_players.py` → `_normalize_player_tag()`

### Prefer Editing Over Creating
- Add endpoints to existing router files, not new files
- Add UI to existing page components when the feature belongs there
- Add types to `api.ts`, not a separate types file
- Add shared logic to `apps/shared/`, not duplicated across api/ingestion

### Keep Files Under ~500 Lines
- `apps/ingestion/db.py` is ~490 lines — split if adding significant new functions
- `apps/web/src/pages/Legends.tsx` is ~780 lines — consider extracting sub-components if extending
- `apps/web/src/pages/TrackedPlayers.tsx` is ~550 lines — at the upper limit
- `apps/web/src/lib/api.ts` is ~320 lines — acceptable, but group additions logically

### Separate Concerns
- **UI components** (`src/components/`) — rendering only, no data fetching
- **Page components** (`src/pages/`) — own their data fetching via `useEffect`
- **API client** (`src/lib/api.ts`) — all HTTP calls, all TS interfaces
- **API routers** (`apps/api/routers/`) — HTTP-to-database bridge, no external API calls
- **Ingestion** (`apps/ingestion/`) — external API calls + database writes
- **Shared** (`apps/shared/`) — cross-cutting config, logging, domain logic

---

## Naming Consistency

- Use **"player"** not "user/member/account"
- Use **"clan"** not "guild/team/group"
- Use **"tag"** not "id" for Supercell identifiers
- Use **"war"** for clan wars, **"battle"** for individual attacks
- URLs use **kebab-case**: `/tracked-players`
- Python uses **snake_case** everywhere
- TypeScript: **camelCase** functions/vars, **PascalCase** types/components
- DB columns: **snake_case**

---

## When Adding a New Feature

### New API Endpoint
1. Add route handler to the appropriate router in `apps/api/routers/`
2. Use `get_db()` from `apps/api/database.py` for DB access
3. Follow existing pagination pattern if returning lists
4. Use structured `HTTPException` with `error` + `hint` for errors
5. Add structured logging with appropriate `event` key
6. Admin-gated routes: use `Depends(require_admin)`

### New DB Table
1. Create new migration: `supabase/migrations/NNN_descriptive_name.sql`
2. Use the next sequential number (currently: 013)
3. Add indexes on FK columns and temporal fields
4. Use composite unique constraints for natural deduplication
5. Document the table in `docs/database.md`

### New Frontend Page
1. Create `apps/web/src/pages/PageName.tsx`
2. Add route in `apps/web/src/App.tsx`
3. Add nav link in `apps/web/src/components/Layout.tsx`
4. Fetch data via methods in `api.ts` inside `useEffect`
5. Use existing components: `LoadingSpinner`, `EmptyState`, `Pagination`
6. Add TypeScript interfaces to `api.ts`

### New Ingestion Feature
1. Add ingestion logic in `apps/ingestion/` (new file or existing)
2. Add DB helpers in `apps/ingestion/db.py`
3. Wire into orchestration in `apps/ingestion/ingest.py` → `_run_once_inner()`
4. Always use `upsert` with `on_conflict` for idempotency
5. Log with structured events: `ingestion.{domain}.{action}`

---

## What Not to Do

- **Do not refactor unrelated code** when fixing a bug or adding a feature
- **Do not add global state** — pages own their data. Only exceptions: `AdminContext`, `ThemePreferenceContext`
- **Do not bypass the API** — the frontend must never import Supabase
- **Do not add `.env` vars** without updating both `.env.example` and `shared/config.py`
- **Do not change migration files** that have been applied — create a new migration instead
- **Do not commit secrets** — check `.gitignore` for patterns
- **Do not remove the `legacy-v1/` directory** — it's preserved intentionally

---

## After Making Changes

1. **Run tests**: `pytest` from repo root
2. **Check types** (frontend): `cd apps/web && npx tsc --noEmit`
3. **Update docs** if you changed structure:
   - Modified API endpoints → update `docs/api.md`
   - New/modified tables → update `docs/database.md`
   - Structural changes → update `docs/project-map.md` and `docs/architecture.md`
4. **Maintain mobile responsiveness** on UI changes
5. **Preserve existing structured logging patterns** — add `event` keys to new log lines

---

## Existing Code Quality Notes

These are known areas of complexity — be careful when modifying:

| Area | Note |
|------|------|
| `apps/ingestion/db.py` (~490 lines) | Largest Python file; all upsert helpers live here. Split candidate if growing. |
| `apps/web/src/pages/Legends.tsx` (~780 lines) | Most complex page; leaderboard + player detail + day picker. Extract sub-components if extending. |
| `apps/web/src/pages/TrackedPlayers.tsx` (~550 lines) | Complex CRUD UI with filtering and inline editing. |
| `apps/api/routers/tracked_players.py` (~287 lines) | Most complex router; has Pydantic models, tag normalization, row normalization. |
| `apps/api/routers/legends.py` (~231 lines) | In-memory aggregation of battle data. |
| `apps/shared/legends_roster.py` | `current_legends_day()` uses UTC+5 offset (CoC Legends day boundary). |
| Tag normalization | `_normalize_player_tag()` exists only in `tracked_players.py` — shared between routers that need it. |

---

## Quick Reference

| Task | Where |
|------|-------|
| Add env var | `apps/shared/config.py` + `.env.example` |
| Add API route | `apps/api/routers/{feature}.py` |
| Add DB table | `supabase/migrations/013_*.sql` + `docs/database.md` |
| Add frontend page | `apps/web/src/pages/*.tsx` + `App.tsx` + `Layout.tsx` |
| Add test | `tests/test_*.py` |
| Add ingestion step | `apps/ingestion/ingest.py` + `db.py` |
| Fix shared logic | `apps/shared/*.py` |
