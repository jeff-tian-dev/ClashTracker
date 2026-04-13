# Architecture

## Overview

Clash of Clans Tracker — a full-stack data pipeline and dashboard that:
1. **Ingests** live game data on a **10-minute** systemd timer (with jitter) from the Supercell CoC API
2. **Stores** it in Supabase PostgreSQL (16 migrations)
3. **Serves** it via a FastAPI REST API
4. **Renders** it in a React SPA dashboard

Runs autonomously on an Oracle Cloud VM. The frontend never touches the database directly.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI Themes, react-router-dom (HashRouter) |
| Backend | Python, FastAPI, Uvicorn |
| Ingestion | Python, httpx, supabase-py |
| Database | Supabase (hosted PostgreSQL), 16 SQL migrations |
| Infrastructure | Oracle Cloud VM (Ubuntu 24.04), systemd, iptables, Caddy (HTTPS) |
| External API | Supercell Clash of Clans API v1 |

---

## Subsystem Map

```
apps/
├── api/          FastAPI REST backend (read + admin endpoints)
├── ingestion/    Supabase data pipeline (one-shot systemd job)
├── shared/       Cross-cutting utilities (config, logging, legends, battlelog)
└── web/          React SPA (Vite + TypeScript + Tailwind + Radix UI)
```

### API (`apps/api/`)
- **Entry point**: `main.py` — FastAPI app, CORS, middleware, router registration
- **9 routers** in `routers/`: health, dashboard, players, wars, raids, legends, tracked_clans, tracked_players, admin
- **Auth**: `auth.py` — Bearer `ADMIN_API_KEY` dependency
- **DB access**: `database.py` — fresh Supabase client per request (avoids stale HTTP/2)
- **Error mapping**: `supabase_errors.py` — PostgREST error → HTTP exception
- **Schemas**: `schemas/contract.py` — Pydantic response shapes for contract tests

### Ingestion (`apps/ingestion/`)
- **Entry point**: `main.py` → calls `ingest.run_once()`
- **Orchestrator**: `ingest.py` — fetches tracked clans/players, iterates, upserts
- **External API**: `supercell_client.py` — synchronous httpx wrapper for CoC API
- **DB helpers**: `db.py` — singleton Supabase client, all upsert functions (~490 lines)
- **Features**: `legends.py` (Legends battle-log ingestion), `player_activity.py` (multiplayer attack timestamps)

### Shared (`apps/shared/`)
- **Config**: `config.py` — single env-loading entrypoint for all services
- **Logging**: `logutil.py` — JSON-line formatter, correlation IDs (`request_id`, `ingestion_run_id`)
- **Domain**: `legends_roster.py` — Legends League roster queries, `current_legends_day()`
- **Domain**: `battlelog.py` — battle-log cursor and snapshot comparison

### Frontend (`apps/web/`)
- **Entry point**: `src/main.tsx` → `App.tsx` (HashRouter)
- **10 pages** in `src/pages/`: Dashboard, Players, PlayerDetail, Wars, WarDetail, Raids, RaidDetail, Legends, TrackedClans, TrackedPlayers
- **7 components** in `src/components/`: Layout, Pagination, LoadingSpinner, EmptyState, AttackActivityHeatmap, ShieldIcon, TableScrollArea
- **API client**: `src/lib/api.ts` — typed fetch wrapper, all endpoint methods and TS interfaces
- **Contexts**: `AdminContext.tsx` (session-scoped admin key), `ThemePreferenceContext.tsx`

---

## Layer Map

| Layer | Module | Responsibility |
|-------|--------|---------------|
| Config | `shared/config.py` | Single env-loading entrypoint for all services |
| Config | `api/config.py`, `ingestion/config.py` | Thin re-exports of shared config |
| Logging | `shared/logutil.py` | JSON-line formatter, correlation IDs |
| Domain | `shared/legends_roster.py` | Legends League roster queries + `current_legends_day()` |
| Domain | `shared/battlelog.py` | Battle-log cursor, snapshot comparison, attack detection |
| API Auth | `api/auth.py` | Bearer admin key dependency |
| API DB | `api/database.py` | Per-request Supabase client factory |
| API Errors | `api/supabase_errors.py` | PostgREST error → HTTP exception mapping |
| API Schemas | `api/schemas/contract.py` | Pydantic response shapes for contract tests |
| API Routers | `api/routers/*.py` | 9 routers: health, dashboard, players, wars, raids, legends, tracked_clans, tracked_players, admin |
| Ingestion DB | `ingestion/db.py` | Supabase upsert helpers (singleton client) |
| Ingestion Orchestrator | `ingestion/ingest.py` | `run_once()` coordinator |
| Ingestion External | `ingestion/supercell_client.py` | CoC API HTTP wrapper |
| Ingestion Features | `ingestion/legends.py` | Legends battle-log ingestion |
| Ingestion Features | `ingestion/player_activity.py` | Multiplayer battle timestamp ingestion |
| Frontend | `web/src/lib/api.ts` | Typed API client |
| Frontend | `web/src/lib/AdminContext.tsx` | Session-scoped admin key |
| Frontend | `web/src/pages/*.tsx` | 10 page components |
| Frontend | `web/src/components/*.tsx` | 7 shared UI components |

---

## Folder Structure

```
Analytics-Dashboard/
├── apps/
│   ├── api/                     # FastAPI backend
│   │   ├── main.py              # App entrypoint
│   │   ├── auth.py              # Admin auth dependency
│   │   ├── config.py            # Re-exports shared config
│   │   ├── database.py          # Supabase per-request client
│   │   ├── supabase_errors.py   # Error mapping
│   │   ├── schemas/             # Pydantic contract types
│   │   └── routers/             # 9 route modules
│   ├── ingestion/               # Data pipeline
│   │   ├── main.py              # CLI entrypoint
│   │   ├── ingest.py            # Orchestrator
│   │   ├── supercell_client.py  # CoC API wrapper
│   │   ├── db.py                # DB upsert helpers
│   │   ├── legends.py           # Legends ingestion
│   │   └── player_activity.py   # Attack timestamp ingestion
│   ├── shared/                  # Shared config, logging, domain logic
│   └── web/                     # React frontend (Vite + TS)
│       └── src/
│           ├── lib/             # API client, contexts, helpers
│           ├── pages/           # 10 page components
│           └── components/      # 7 shared UI components
├── supabase/migrations/         # 001–016 SQL migrations
├── tests/                       # pytest (contract, regression, admin, integration)
├── deploy/                      # systemd units, VM setup, HTTPS scripts
├── scripts/                     # Test runner scripts
├── fixtures/                    # Sample JSON for contract tests
├── static/                      # Optional production SPA served by FastAPI
├── legacy-v1/                   # V1 implementation (preserved, independently runnable)
├── docs/                        # Project documentation (this folder)
├── deploy.ps1                   # PowerShell deploy script
├── .env.example                 # Environment template
└── README.md
```

---

## Key Entry Points

| Purpose | File | Command |
|---------|------|---------|
| Start API server | `apps/api/main.py` | `uvicorn apps.api.main:app --reload` |
| Run ingestion | `apps/ingestion/main.py` | `python -m apps.ingestion.main` |
| Start frontend dev | `apps/web/` | `cd apps/web && npm run dev` |
| Run tests | repo root | `pytest` |
| Deploy to VM | repo root | `./deploy.ps1` |

---

## Data Flow (High-Level)

```
Supercell CoC API
      │
      │  every 10 minutes (systemd timer + jitter)
      ▼
apps/ingestion/
      │  supercell_client.py → ingest.py → db.py
      │  (fetch → transform → upsert)
      ▼
Supabase PostgreSQL  ◄──────  16 migrations define schema
      │
      │  per-request REST queries
      ▼
apps/api/
      │  routers/*.py → database.py
      │  (query → shape → JSON response)
      ▼
apps/web/
      │  api.ts → pages/*.tsx
      │  (fetch → render)
      ▼
Browser (React SPA)
```

All database access is server-side. The frontend only knows the API URL (`VITE_API_URL`).

---

## Infrastructure

- **Oracle Cloud VM** runs both API (uvicorn, systemd service) and ingestion (systemd timer, **every 10 minutes**)
- **Caddy** reverse-proxies HTTPS to FastAPI on port 8000
- **GitHub Actions** deploys frontend to GitHub Pages on push to `main`
- **DuckDNS** provides a free subdomain pointing to the VM

---

## Reference Files

- `docs/supercell-coc-openapi.json` — Local copy of the Supercell Clash of Clans API v1 OpenAPI spec. Used as reference for ingestion development; not loaded at runtime.
