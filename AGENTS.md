# AGENTS.md

This file defines how AI agents must operate in this repository.

You are a **senior full-stack engineer** maintaining this system.
Prioritize **correctness, consistency, and minimal changes**.

---

## 🚨 BEFORE MAKING ANY CHANGES

You MUST follow this order:

1. Read `/docs/project-map.md` → understand file locations
4. Check existing implementations before writing new code

**Trivial change shortcut:** If the task is **only** typo/grammar in a single doc, comment-only clarification, or **single-file** presentational UI copy/styling with **no** behavior, routing, API, schema, or ingestion change — read **`/docs/project-map.md` only** (skip steps 2–3 unless something is unclear). The task-type table at the top of project-map lists when to open the other docs.

Treat **`docs/api.md`**, route summaries in docs, and migration tables as **hints** — **verify** HTTP routes and shapes against `apps/api/routers/*.py` (and migrations when touching the DB).

Do NOT proceed if you do not understand the relevant system.

---

## 🎯 SYSTEM OVERVIEW

This is a full-stack system with:

* **Frontend** (React)
* **API** (FastAPI)
* **Ingestion pipeline** (external API → DB)
* **PostgreSQL (Supabase)** database
* **Shared layer** (`apps/shared/`) for cross-cutting logic

**Ingestion cadence (VM):** `deploy/clash-tracker-ingestion.timer` runs **`python -m apps.ingestion.main` every 10 minutes** (with up to ~2 minutes jitter). Do not describe it as hourly.

---

## ⚠️ CORE RULES (MANDATORY)

### 1. Do Not Duplicate Logic

* Always search for existing implementations first
* Shared logic belongs in `apps/shared/`
* Never reimplement existing helpers

Critical existing patterns:

* Config → `shared/config.py` (never use `os.environ` elsewhere)
* Supabase clients → `api/database.py` (request), `ingestion/db.py` (singleton)
* Tag normalization → `_normalize_player_tag()` in `tracked_players.py`
* Clash of Clans HTTP → `apps/ingestion/supercell_client.py` (or a shared module both API and ingestion import); reuse `_encode_tag` / `create_client()` patterns — do not duplicate ad-hoc CoC clients

---

### 2. Prefer Editing Over Creating

* Modify existing files whenever possible
* Do not create new routers, pages, or helpers unnecessarily
* Extend existing systems instead of duplicating them

---

### 3. Respect File Size Limits

* Keep files under ~500 lines
* If extending large files, extract modular subcomponents/functions

High-risk files:

* `apps/ingestion/db.py` (~490 lines)
* `apps/web/src/pages/Legends.tsx` (~780 lines)
* `apps/web/src/pages/TrackedPlayers.tsx` (~550 lines)

---

### 4. Maintain Separation of Concerns

* UI (`components/`) → rendering only
* Pages (`pages/`) → data fetching
* API client (`api.ts`) → HTTP + types
* API routers → **DB by default**. Calls to the **Clash of Clans API** are allowed when the feature needs live or not-yet-ingested data; use the Supercell client pattern below (no scattered raw `httpx`, never expose `COC_API_TOKEN` to the browser)
* Ingestion → external API + DB writes
* Shared → reusable logic

---

## 🧠 HOW TO APPROACH TASKS

When given a task:

1. Identify affected layer:

   * frontend / API / ingestion / database

2. Read relevant docs BEFORE coding

3. Locate existing related code

4. Modify or extend existing logic

5. Ensure consistency with existing patterns

For **known-large files** (e.g. `apps/web/src/pages/Legends.tsx`, `apps/web/src/pages/TrackedPlayers.tsx`, `apps/ingestion/db.py`), prefer **path-scoped search or grep** before broad codebase semantic search so results stay on-target.

---

## 🏗️ FEATURE IMPLEMENTATION RULES

### API Endpoint

* Add to existing router in `apps/api/routers/`
* Use `get_db()` for DB access
* Follow pagination patterns
* Use structured `HTTPException` (`error` + `hint`)
* Add structured logging (`event` key)
* Use `Depends(require_admin)` for admin routes
* If the handler calls Supercell, keep the route thin: validate input → call a small module function → return a DTO

### Supercell / Clash of Clans API (API layer)

* **When:** Prefer reading the DB when ingestion already has the row; use CoC for on-demand lookups, missing players/clans, or explicitly live data.
* **How:** Reuse or extend `apps/ingestion/supercell_client.py`. If both API and ingestion need the same helpers long-term, move shared pieces to `apps/shared/` and import from there — do not fork duplicate HTTP logic.
* **Config:** `COC_API_TOKEN` and `COC_BASE_URL` only via `shared/config.py`.
* **Security:** The frontend must only call your FastAPI routes; the CoC token stays server-side.
* **Resilience:** Use timeouts; map CoC 404 / 429 / 5xx to structured errors and log with `event` keys (e.g. `coc.*`).
* **Docs:** Document new routes in `docs/api.md`. Schema reference → `/docs/supercell-coc-openapi.json` — **search** that file by path key (e.g. `"/players"`); do **not** load the entire OpenAPI JSON into context.

---

### Database Changes

* Create new migration (`supabase/migrations/NNN_*.sql`)
* Do NOT modify existing migrations
* Add indexes on FK + time fields
* Use composite unique constraints
* Update `docs/database.md`

---

### Frontend Changes

* Pages → `apps/web/src/pages/`
* Add route in `App.tsx`
* Add nav in `Layout.tsx`
* Fetch via `api.ts` only
* Use shared components (LoadingSpinner, etc.)
* Add types in `api.ts`

---

### Ingestion Changes

* Add logic in `apps/ingestion/`
* Use `upsert` with `on_conflict`
* Wire into `_run_once_inner()`
* Log with `ingestion.{domain}.{action}`

---

## 🏷️ NAMING RULES

* "player" (not user/member)
* "clan" (not guild/team)
* "tag" (not id for Supercell)
* "war" vs "battle" distinction

Conventions:

* Python → snake_case
* TypeScript → camelCase / PascalCase
* URLs → kebab-case
* DB → snake_case

---

## 🚫 WHAT NOT TO DO

* Do NOT refactor unrelated code
* Do NOT create parallel systems
* Do NOT bypass API from frontend
* Do NOT add global state (except approved contexts)
* Do NOT modify applied migrations
* Do NOT commit secrets
* Do NOT remove `legacy-v1/`

**Cursor index:** `legacy-v1/` is listed in **`.cursorignore`** — it is excluded from typical AI codebase indexing. **Do not** use `legacy-v1/` as reference for the current stack unless the task explicitly involves v1.

---

## 🧪 AFTER MAKING CHANGES

1. Run tests → `pytest`
2. Type check → `cd apps/web && npx tsc --noEmit`
3. Update docs if needed:

   * API → `docs/api.md`
   * DB → `docs/database.md`
   * Structure → `docs/project-map.md`, `docs/architecture.md`
4. Maintain mobile responsiveness
5. Preserve structured logging (`event` keys)

---

## 📚 REFERENCE

* Structure → `/docs/project-map.md`
* Architecture → `/docs/architecture.md`
* API → `/docs/api.md`
* Supercell API → `/docs/supercell-coc-openapi.json` (grep/search by path segment; file is huge)
* Database → `/docs/database.md`
* Conventions → `/docs/conventions.md`
