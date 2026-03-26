# Architecture

## Subsystems

```
apps/
├── api/          FastAPI REST backend (read + admin endpoints)
├── ingestion/    Supabase data pipeline (one-shot systemd job)
├── shared/       Cross-cutting utilities (logging, config, legends, battlelog)
└── web/          React SPA (Vite + TypeScript + Tailwind + Radix UI)
```

## Layer Map

| Layer | Module | Responsibility |
|-------|--------|---------------|
| Config | `shared/config.py` | Single env‐loading entrypoint for all services |
| Config | `api/config.py`, `ingestion/config.py` | Thin re‐exports of shared config |
| Logging | `shared/logutil.py` | JSON‐line formatter, correlation IDs |
| Domain | `shared/legends_roster.py` | Legends League roster queries + `current_legends_day()` |
| Domain | `shared/battlelog.py` | Battle‐log cursor, snapshot comparison, attack detection |
| API Auth | `api/auth.py` | Bearer admin key dependency |
| API DB | `api/database.py` | Per‐request Supabase client factory |
| API Errors | `api/supabase_errors.py` | PostgREST error → HTTP exception mapping |
| API Schemas | `api/schemas/contract.py` | Pydantic response shapes for contract tests |
| API Routers | `api/routers/*.py` | 9 routers: health, dashboard, players, wars, raids, legends, tracked_clans, tracked_players, admin |
| Ingestion DB | `ingestion/db.py` | Supabase upsert helpers (singleton client) |
| Ingestion Orchestrator | `ingestion/ingest.py` | `run_once()` coordinator |
| Ingestion External | `ingestion/supercell_client.py` | CoC API HTTP wrapper |
| Ingestion Features | `ingestion/legends.py` | Legends battle‐log ingestion |
| Ingestion Features | `ingestion/player_activity.py` | Multiplayer battle timestamp ingestion |
| Frontend | `web/src/lib/api.ts` | Typed API client |
| Frontend | `web/src/lib/AdminContext.tsx` | Session‐scoped admin key |
| Frontend | `web/src/pages/*.tsx` | 10 page components |
| Frontend | `web/src/components/*.tsx` | 7 shared UI components |

## Database

PostgreSQL via Supabase REST. **12 migrations** in `supabase/migrations/` (001–012).

## Conventions

- **Tag normalization**: `_normalize_player_tag()` in `api/routers/tracked_players.py`; shared between tracked_clans and tracked_players routers.
- **Row normalization**: `_normalize_tracked_row()` handles legacy `name` → `display_name`, default `tracking_group`, and `legends_bracket` defaults.
- **Structured logging**: Every log line includes `event` key for grep/filtering. API adds `request_id`; ingestion adds `ingestion_run_id`.
- **Error handling**: PostgREST errors mapped via `supabase_errors.py`; write conflicts → 409 with structured detail.
- **Config**: All env vars loaded once in `shared/config.py`; subsystem configs are thin re-exports.
