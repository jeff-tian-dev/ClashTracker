# Clash of Clans Tracker

A full-stack data pipeline and dashboard that continuously ingests live Clash of Clans game data, stores it in PostgreSQL, serves it through a REST API, and renders it in a React dashboard.

Tracks player statistics, clan war outcomes, Legends League battles, and Clan Capital raid performance across multiple clans — running autonomously with (almost) zero manual intervention.

---

## Tech Stack

| Layer | Technology |
|-------|-----------:|
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 · Radix UI |
| Backend | Python · FastAPI · Uvicorn |
| Ingestion | Python · httpx · supabase-py |
| Database | Supabase (PostgreSQL) · 16 SQL migrations |
| Infra | Oracle Cloud VM · systemd · Caddy · GitHub Actions |

---

## Quick Start

### Prerequisites
- Node.js 20+ · Python 3.11+ · Supabase project · Supercell API key

### 1. Configure environment
```bash
cp .env.example .env.local
# Fill in: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, COC_API_TOKEN
```

### 2. Run database migrations
Apply each file in `supabase/migrations/` (001–016) to your Supabase SQL Editor.

### 3. Start the backend
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r apps/api/requirements.txt -r apps/ingestion/requirements.txt
uvicorn apps.api.main:app --reload
```

### 4. Start the frontend
```bash
cd apps/web && npm install && npm run dev
```

### 5. Run ingestion manually
```bash
python -m apps.ingestion.main
```

### 6. Run tests
```bash
pip install -r requirements-dev.txt && pytest
```

---

## Project Structure

```
apps/
├── api/          FastAPI REST backend (9 routers)
├── ingestion/    Hourly data pipeline (systemd one-shot job)
├── shared/       Cross-cutting utilities (config, logging, domain logic)
└── web/          React SPA (10 pages, 7 components)

supabase/migrations/   SQL migrations (001–016)
tests/                 pytest suite (contract, regression, admin, integration)
deploy/                systemd units, VM setup, HTTPS scripts
docs/                  Comprehensive documentation (see below)
legacy-v1/             V1 implementation (preserved)
```

---

## Documentation

📁 **[`/docs`](docs/)** — structured documentation optimized for AI agents and developers:

| Document | Purpose |
|----------|---------|
| [architecture.md](docs/architecture.md) | System overview, tech stack, folder structure, data flow |
| [project-map.md](docs/project-map.md) | Feature → file navigation guide |
| [conventions.md](docs/conventions.md) | Naming, structure, and coding rules |
| [data-flow.md](docs/data-flow.md) | How data moves from Supercell API → DB → API → UI |
| [api.md](docs/api.md) | All API endpoints, auth, request/response patterns |
| [database.md](docs/database.md) | Complete schema reference (12 tables) |
| [ai-instructions.md](docs/ai-instructions.md) | **Rules for AI agents** modifying this codebase |
| [supercell-coc-openapi.json](docs/supercell-coc-openapi.json) | Supercell CoC API v1 OpenAPI spec (local reference) |

---

## Deployment

Deploy to Oracle Cloud VM via `deploy.ps1`:
1. SCPs Python apps + migrations + env to VM
2. Creates venv and installs dependencies
3. Installs systemd units (API service + ingestion timer, **every 10 minutes**)

Frontend deploys to GitHub Pages via [GitHub Actions](.github/workflows/deploy-gh-pages.yml) on push to `main`.

For HTTPS: `bash deploy/setup-https.sh clashtracker.duckdns.org` (Caddy + Let's Encrypt).

---

## License

Private project.
