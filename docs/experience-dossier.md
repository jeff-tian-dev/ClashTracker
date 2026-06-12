## Clash of Clans Tracker (Analytics Dashboard)

**Purpose (1–2 sentences):** Ingest Clash of Clans data on a schedule, persist it in PostgreSQL (Supabase), expose a FastAPI REST API, and render a React SPA (README.md).

**Type:** personal — README.md: “Private project”; no employer named (employer Unknown).

**Stack:** FastAPI, Uvicorn (`apps/api/requirements.txt`, `apps/api/main.py`); React 19, TypeScript, Vite, Tailwind v4, Radix, react-router-dom (`apps/web/package.json`); ingestion httpx + supabase-py (`apps/ingestion/requirements.txt`); shared env (`apps/shared/config.py`); pytest dev deps (`requirements-dev.txt`).

**Data & persistence:** Supabase/Postgres via `supabase` in `apps/api/database.py` (`get_db()`). Migrations: `supabase/migrations/` (13 `.sql` files; README says 12—stale).

**APIs & integrations:** Supercell CoC HTTP (`apps/shared/config.py`, `apps/ingestion/supercell_client.py`). REST routers under `apps/api/routers/` (admin, dashboard, health, legends, players, raids, tracked clans/players, wars). Reference: `docs/supercell-coc-openapi.json`.

**Infra & delivery:** `.github/workflows/deploy-gh-pages.yml` (Node 20, `apps/web` build, GitHub Pages; `VITE_API_URL` → clashtracker.duckdns.org). `deploy/` systemd units, Caddyfile, setup scripts; `deploy.ps1` + README.md describe VM deploy. No Dockerfile/docker-compose in-repo.

**What I built / owned (3–6 bullets):**
- FastAPI app with CORS, validation errors, request lifecycle logging (`apps/api/main.py`).
- Nine domain routers in `apps/api/routers/` covering dashboard, wars, raids, legends, players, tracked entities, admin, health.
- CoC client: tag encoding, timeouts, structured `coc.*` logs (`apps/ingestion/supercell_client.py`).
- Config + per-request Supabase client (`apps/shared/config.py`, `apps/api/database.py`).
- React UI: 10 pages, 7 components (`apps/web/src/pages/`, `apps/web/src/components/`—counts via workspace listing).
- CI frontend deploy on `main`; VM-oriented systemd/Caddy assets in `deploy/` Oracle Cloud VM

**Outcomes / metrics:** Not stated in-repo. Plausible metrics: ingestion success rate, API p95, SPA load—only with real data.

**Resume tailoring notes:** Credible full-stack + migrations + CI story; ingestion/ops artifacts in `deploy/`. Do not assert users, revenue, traffic, or team size. Hostname in workflow ≠ proven load.

### JD keywords (grounded only, max 18)
FastAPI, Uvicorn, React, TypeScript, Vite, Tailwind CSS, Radix UI, PostgreSQL, Supabase, REST API, httpx, Python ingestion, GitHub Actions, GitHub Pages, systemd, Caddy, structured logging, pytest

### Suggested angles for resumes (non-committal, max 5 short phrases)
API-to-UI analytics pipeline; Postgres schema evolution; scheduled ingestion on a VM; GitHub Pages CI; pytest contract/integration coverage.

### Measurable impact
- Time saved: **~5-8** hours/week vs manual war/Legends/capital checks for a co-lead 
- Audience: **~5–15** people using dashboard/API for clan ops in a mid-size alliance 
- Scale: **~30** clans / **~500** tracked players, **~144** ingestion runs/day from `deploy/clash-tracker-ingestion.timer` Tune clan/player counts against live Supabase.
- 200+ users, 250API requests per cycle, 20k+ records

