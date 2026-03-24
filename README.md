# Clash of Clans Tracker

A full-stack data pipeline and web application that continuously ingests live game data from the Supercell API, stores it in a normalized Postgres database, serves it through a REST API, and renders it in a React dashboard. The system runs autonomously on an Oracle Cloud VM, pulling fresh data every hour with zero manual intervention.

Built to track player statistics, clan war outcomes, and Clan Capital raid performance across multiple clans over time.

---

## Project Evolution

This project has gone through two major iterations:

### V1 (Legacy) -- `legacy-v1/`

The original implementation used a lightweight approach:
- **Frontend**: Static HTML/CSS pages served via GitHub Pages
- **Data collection**: Python scripts calling the Supercell API
- **Storage**: Raw JSON files committed directly to this GitHub repository
- **Scheduling**: Cron job on an Oracle Cloud VM, auto-committing data on each run
- **Dashboards**: [War Player List](https://jeff-tian-dev.github.io/clan_tracker/war_player_list.html) | [Raid Player List](https://jeff-tian-dev.github.io/clan_tracker/raid_player_list.html)

The V1 code is fully preserved and independently runnable in the `legacy-v1/` directory. All git history for the original file paths is retained.

### V2 (Current) -- Repository Root

A complete rewrite with a proper full-stack architecture:
- **Frontend**: React + TypeScript + Vite + Tailwind CSS + Radix UI
- **Backend**: Python FastAPI REST API
- **Database**: Supabase (hosted PostgreSQL) with SQL migrations
- **Ingestion**: Python pipeline with idempotent upserts, managed by systemd
- **Infrastructure**: Oracle Cloud VM running both the API and ingestion service

---

## System Architecture

```
                          +---------------------+
                          |   Supercell API      |
                          | (Clash of Clans v1)  |
                          +----------+----------+
                                     |
                          hourly pull (Bearer JWT)
                                     |
               +---------------------v-----------------------+
               |          Oracle Cloud VM (Ubuntu 24.04)     |
               |                                             |
               |  +-------------------+  +-----------------+ |
               |  | Ingestion Service |  | FastAPI Backend | |
               |  | (systemd timer)   |  | (systemd svc)   | |
               |  +--------+----------+  +--------+--------+ |
               |           |                      |          |
               +-----------+----------------------+----------+
                           |                      |
                     upsert (REST)          query (REST)
                           |                      |
                    +------v----------------------v------+
                    |        Supabase Postgres            |
                    |   (hosted, 8 tables, 4 migrations)  |
                    +------^-----------------------------+
                           |
                    +------+------+
                    |   Browser   |
                    | React + TS  |  <--- fetches JSON from FastAPI
                    +-------------+
```

The frontend never communicates with Supabase directly. All database access is server-side, routed through the FastAPI layer using a service-role key that never leaves the backend. If you deploy a build under `static/`, the browser loads the UI from the same FastAPI origin; the SPA still calls the JSON API only, not Supabase.

---

## Core Capabilities

- **Multi-clan tracking** -- a `tracked_clans` configuration table drives ingestion dynamically; changing the list requires no code changes or redeployments. Adding or removing clan tags via the API (or dashboard admin mode) uses the same admin key as tracked players when `ADMIN_API_KEY` is set.
- **Tracked players** -- a `tracked_players` table lists player tags to ingest even when they are not in a tracked clan; the pipeline merges clan rosters with these tags. Roster reconciliation records when members leave tracked clans (`left_tracked_roster_at` on `players`).
- **Idempotent ingestion** -- every upsert uses composite unique constraints (`ON CONFLICT ... DO UPDATE`), making the pipeline safe to re-run at any frequency without creating duplicates.
- **Hourly automated sync** -- a systemd timer triggers the ingestion service on a fixed schedule with jitter, managed entirely by the OS process supervisor.
- **REST API** -- paginated, filterable read endpoints for players, wars, capital raids, and dashboard summaries; writes for `tracked_clans` and `tracked_players` (POST/DELETE) require `Authorization: Bearer <ADMIN_API_KEY>` when the key is configured. Structured logging with `X-Request-Id` on responses.
- **Responsive dashboard** -- React SPA with `HashRouter` (GitHub Pages–friendly base path), loading and empty states, search, pagination, drill-down views, **Tracked clans** and **Tracked players** screens, and an optional admin mode (Bearer token) for mutating both lists.
- **Optional same-origin UI** -- if a production build exists at repo root `static/`, FastAPI serves the SPA and `/assets` alongside the JSON API (useful when you want one origin behind HTTPS without GitHub Pages).

---

## Technical Design Highlights

### Database Schema Design

The schema spans **8 tables** across **4** ordered migration files (`001`–`004`), designed around the domain boundaries of the Supercell API.

**Key decisions:**

- **Natural primary keys for game entities.** `clans` and `players` use the Supercell-assigned tag (e.g. `#2GRPGV0VL`) as the primary key rather than a surrogate. This eliminates lookup joins during ingestion and makes the upsert path a single statement per entity.

- **`tracked_clans` is intentionally not foreign-keyed to `clans`.** A clan tag can be added to the tracking list before the first ingestion run populates the `clans` table. This avoids a chicken-and-egg dependency between configuration and data.

- **`tracked_players` is intentionally not foreign-keyed to `players`.** Tags can be registered before the first successful player fetch, mirroring the `tracked_clans` pattern.

- **Roster visibility.** Migration `004` adds `left_tracked_roster_at` and a generated sort bucket on `players` so the UI can separate current tracked-roster members from players who left while still retaining history.

- **Composite unique constraints for deduplication.** Wars are deduplicated on `(clan_tag, preparation_start_time)` and capital raids on `(clan_tag, start_time)`. These are the natural identifiers from the Supercell API and allow safe `UPSERT` semantics without maintaining external state.

- **Cascading deletes on child tables.** `war_attacks` and `raid_members` use `ON DELETE CASCADE` referencing their parent records, keeping orphan cleanup automatic.

- **Indexes on all foreign keys and temporal columns.** Every FK column and `updated_at` field is indexed to support the API's filtering and ordering queries without full table scans.

### Ingestion Pipeline

The ingestion service is a single-purpose Python process designed to run as a one-shot job (`Type=oneshot` in systemd). It follows a straightforward pipeline:

1. Query `tracked_clans` and `tracked_players` from Supabase for clan tags and always-tracked player tags.
2. For each clan: fetch clan metadata, current war status, capital raid seasons, and full player details for every member. Ingest always-tracked players even when no clans are configured.
3. Reconcile roster membership: clear `left_tracked_roster_at` for players still in the active tag set; stamp it for former members who were on the roster and have now left.
4. Upsert all data through the Supabase REST API using the service-role key.

**Design choices:**

- **Synchronous HTTP with `httpx`.** The Supercell API is rate-limited and the dataset per clan is bounded (~50 members, 1 active war, 5 raid seasons). Async would add complexity without meaningful throughput gains at this scale.
- **Graceful degradation.** Private war logs (HTTP 403) and missing clans (HTTP 404) are logged and skipped rather than aborting the entire run. One clan's API issue does not block ingestion for others.
- **Non-zero exit on fatal errors.** Unhandled exceptions propagate to `sys.exit(1)`, which systemd records as a failure -- visible in `journalctl` and compatible with alerting.

### API Layer

The backend is a FastAPI application with **8 routers** (`health`, `dashboard`, `players`, `wars`, `raids`, `tracked_clans`, `tracked_players`, `admin`). Most routes are read-oriented. **`POST`/`DELETE` on `tracked_clans` and `tracked_players`**, **`POST /api/admin/verify`**, and destructive admin routes on players/wars/raids require `Authorization: Bearer <ADMIN_API_KEY>` when `ADMIN_API_KEY` is set on the server; if the key is unset, those routes return **503**.

- **Pagination** is offset-based via `page` and `page_size` query parameters. Every list endpoint returns `{ data, total, page, page_size }` to support frontend pagination controls.
- **Filtering** is scoped per resource: players support `clan_tag` and `search` (name ILIKE), wars support `clan_tag` and `state`, raids support `clan_tag`.
- **Detail endpoints** for wars and raids eagerly load child records (attacks and member contributions) in a second query, returned as a nested `attacks` or `members` array.
- **CORS** is configured via environment variable (`CORS_ORIGINS`) to allow extension beyond the default `localhost:5173` without code changes.

### Frontend Architecture

The frontend is a single-page React application built with Vite, TypeScript, Tailwind CSS, and Radix UI Themes. Routing uses **`HashRouter`** so the app works when hosted under a subpath on GitHub Pages (`#/players`, etc.).

- **Typed API client** (`src/lib/api.ts`) -- a single module with full TypeScript interfaces for every API response shape, a generic `request<T>()` wrapper, and named methods for each endpoint. No `any` types.
- **Admin context** (`src/lib/AdminContext.tsx`) -- stores an optional admin API key in `sessionStorage` and sends `Authorization: Bearer …` for tracked-clan and tracked-player mutations when configured.
- **Collocated page components** -- each route maps to a page component in `src/pages/` that owns its own data fetching via `useEffect`, loading state, and error handling. No global state management beyond admin key context; the data model is simple enough that per-page fetching is the right tradeoff.
- **Reusable primitives** -- `LoadingSpinner`, `EmptyState`, and `Pagination` components are shared across all list views.
- **Radix UI Themes** for accessible, consistent UI components (tables, cards, badges, dialogs) without writing custom component logic.

---

## Security Considerations

- **All secrets live in a single `.env.local` file** at the project root, excluded from version control via `.gitignore`. The SSH private key is similarly gitignored by extension (`*.key`).
- **`ADMIN_API_KEY`** gates tracked-clan and tracked-player writes, admin verification, and other admin-only API actions. Generate a strong value (see `.env.example`). Anyone who knows the key can change the tracked-clan and tracked-player lists via the API.
- **The Supercell API token and Supabase service-role key never reach the browser.** The frontend only knows the backend's public URL (`VITE_API_URL`). All database and external API access is server-side. (If you enable admin mode in the UI, that key is stored in **sessionStorage** and sent as a Bearer token—treat the browser session as trusted only on your own machine.)
- **The Supercell API token is IP-whitelisted** to the Oracle Cloud VM's public IP, meaning the token is useless if leaked without access to that specific network.
- **The backend uses the Supabase service-role key**, which bypasses Row Level Security. This is acceptable because the API is read-only for data tables, and the service-role key is confined to the server process.
- **`.env.example` documents every required variable** without exposing real values, making onboarding safe.

---

## Scalability and Engineering Tradeoffs

This is an MVP scoped for a small number of tracked clans (1-20). The design reflects that scope intentionally:

| Decision | Tradeoff |
|----------|----------|
| Supabase REST API for all DB access (ingestion + backend) | Simpler deployment (no direct Postgres driver needed), but adds HTTP overhead per query. Acceptable at this scale; a direct `asyncpg` connection would be the next step. |
| Fresh Supabase client per API request | Avoids stale HTTP/2 connection errors in the long-running FastAPI process. Adds ~10ms of client setup per request, negligible compared to network round-trip. |
| Synchronous ingestion, one player at a time | Simple, debuggable, respects Supercell rate limits. For 20+ clans, batched async fetching with semaphore-based concurrency would be warranted. |
| Offset-based pagination | Straightforward for the frontend to implement. Cursor-based pagination would perform better on large datasets but adds client complexity. |
| No caching layer | The dataset updates hourly. Adding Redis or in-memory caching is unnecessary when the data is inherently stale by design. |
| Single VM hosts both API and ingestion | Reduces infrastructure cost and complexity. For production scale, these would be separated -- the API behind a load balancer, ingestion as a scheduled container job. |

---

## Local Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- A Supabase project with the migrations applied
- A Supercell API key (from [developer.clashofclans.com](https://developer.clashofclans.com))

### 1. Configure environment

```bash
cp .env.example .env.local
# Fill in: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, COC_API_TOKEN
# Optional: ADMIN_API_KEY for tracked-clan / tracked-player POST/DELETE, /api/admin/verify, etc.
```

### 2. Run database migrations

Paste the contents of each file in `supabase/migrations/` into the Supabase SQL Editor, in order (`001_core_tables`, `002_wars`, `003_capital_raids`, `004_player_roster_and_tracked_players`).

### 3. Start the backend

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r apps/api/requirements.txt -r apps/ingestion/requirements.txt
uvicorn apps.api.main:app --reload
```

### 4. Start the frontend

```bash
cd apps/web
npm install
# Set VITE_API_URL in apps/web/.env to your backend URL (default: http://localhost:8000)
npm run dev
```

### 5. Run ingestion manually

```bash
python -m apps.ingestion.main
```

### 6. Run tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Deployment Overview

The backend and ingestion service are deployed to an Oracle Cloud VM (Ubuntu 24.04) via a single PowerShell script (`deploy.ps1`) that:

1. SCPs **`apps/api`**, **`apps/ingestion`**, **`apps/shared`**, `supabase/`, `deploy/`, and `.env.local` to the VM (not the full `apps/` tree—frontend dependencies and `node_modules` stay local).
2. Creates a Python virtual environment and installs all dependencies.
3. Installs two systemd units:
   - `clash-tracker-api.service` -- runs uvicorn on port 8000, restarts on failure.
   - `clash-tracker-ingestion.timer` -- triggers the ingestion service hourly with randomized jitter.
4. Configures iptables to allow inbound traffic on port 8000.

To serve the built React app from the same uvicorn process, copy a production build into **`static/`** at the project root on the VM (matching what `apps/api/main.py` expects) and include `static/` in your deploy sync; otherwise the VM only exposes the JSON API.

Post-deployment management:

```bash
# View API logs
journalctl -u clash-tracker-api -f

# View last ingestion run
journalctl -u clash-tracker-ingestion.service -n 100

# Trigger immediate ingestion
sudo systemctl start clash-tracker-ingestion.service

# Check next scheduled run
systemctl status clash-tracker-ingestion.timer
```

---

## GitHub Pages (Public Sharing)

To let others view the dashboard at `https://jeff-tian-dev.github.io/Analytics-Dashboard/`, the backend must serve over **HTTPS**. Browsers block HTTP API calls from HTTPS pages (mixed content).

### Automated deploy (recommended)

The workflow [`.github/workflows/deploy-gh-pages.yml`](.github/workflows/deploy-gh-pages.yml) runs on every push to **`main`**: it builds `apps/web` with `npm run build:gh-pages`, uploads the artifact, and deploys to **GitHub Pages** (configure the repo’s Pages source to **GitHub Actions** if you use this path). The workflow sets `VITE_API_URL` to the production API URL (currently `https://clashtracker.duckdns.org`); adjust the workflow env if your API host changes.

### Manual / local gh-pages scripts

You can still use `npm run deploy:gh-pages` from `apps/web` (see `package.json`) if you prefer publishing from your machine.

### 1. Get a free domain

Create a subdomain at [DuckDNS](https://www.duckdns.org) (e.g. `clashtracker.duckdns.org`) and point it to your VM's public IP. DuckDNS does this automatically when you create the subdomain.

### 2. Open ports 80 and 443

In Oracle Cloud: VCN → Security Lists → your list → Add Ingress Rule for ports 80 and 443 (source 0.0.0.0/0).

### 3. Run the HTTPS setup on the VM

```bash
ssh -i your-key.key ubuntu@YOUR_VM_IP
cd /home/ubuntu/clash-tracker
bash deploy/setup-https.sh clashtracker.duckdns.org
```

This installs Caddy, obtains a free Let's Encrypt certificate, and reverse-proxies HTTPS to the FastAPI backend.

### 4. Build and deploy the frontend for GitHub Pages

```bash
cd apps/web
cp .env.gh-pages.example .env.gh-pages
# Edit .env.gh-pages: set VITE_API_URL=https://clashtracker.duckdns.org
npm run deploy:gh-pages
```

If `gh-pages` fails (e.g. due to special characters in the repo), build manually and push:

```bash
npm run build:gh-pages
# Then push the contents of dist/ to the gh-pages branch (see deploy docs)
```

### 5. Enable GitHub Pages

Repo → Settings → Pages → choose **GitHub Actions** as the source if you use the workflow above, or **Deploy from branch** → branch `gh-pages` if you publish with `gh-pages` / manual `dist` pushes.

The dashboard will be live at `https://jeff-tian-dev.github.io/Analytics-Dashboard/` and will load data from your HTTPS API.

---

## Project Structure

```
Analytics-Dashboard/
├── apps/
│   ├── api/                     # FastAPI backend
│   │   ├── main.py              # App entrypoint, CORS, routers, optional static SPA
│   │   ├── auth.py              # Bearer ADMIN_API_KEY dependency
│   │   ├── config.py            # Environment loading
│   │   ├── database.py          # Supabase client factory
│   │   ├── schemas/             # Shared API contract types (e.g. tests / fixtures)
│   │   └── routers/             # health, dashboard, players, wars, raids,
│   │                            # tracked_clans, tracked_players, admin
│   ├── ingestion/               # Data pipeline
│   │   ├── main.py              # CLI entrypoint
│   │   ├── ingest.py            # Orchestrator (run_once)
│   │   ├── supercell_client.py  # Supercell API wrapper
│   │   ├── db.py                # Supabase upsert helpers, roster reconciliation
│   │   └── config.py            # Environment loading
│   ├── shared/                  # Shared Python (structured logging / correlation IDs)
│   └── web/                     # React frontend (Vite)
│       └── src/
│           ├── lib/             # api.ts, AdminContext, helpers
│           ├── pages/           # Dashboard, Players, PlayerDetail, Wars, WarDetail,
│           │                    # Raids, RaidDetail, TrackedClans, TrackedPlayers
│           └── components/      # Layout, Pagination, LoadingSpinner, EmptyState
├── .github/workflows/           # e.g. deploy-gh-pages.yml
├── deploy/                      # systemd units + VM / HTTPS setup scripts
├── supabase/migrations/         # 001–004 (core, wars, raids, roster + tracked_players)
├── tests/                       # pytest (API contract, smoke, admin behavior)
├── fixtures/                    # Sample JSON for contract tests
├── static/                      # Optional production SPA + assets (served by FastAPI)
├── scripts/                     # e.g. run_tests.sh
├── legacy-v1/                   # Original V1 implementation (HTML/CSS + Python + JSON)
├── deploy.ps1                   # Sync Python apps + supabase + deploy to Oracle VM
├── requirements-dev.txt         # pytest, httpx (dev/CI)
├── coc-api-docs.json            # Local reference copy of CoC API docs (optional)
├── logs/                        # Local scratch output for one-off scripts (gitignored JSON)
├── .env.example                 # Template (no secrets)
└── .gitignore
```

---

## Future Improvements

- **War log history** -- the current war endpoint only returns the active war. Polling the war log endpoint on a shorter interval would capture completed wars that rotate out between hourly runs.
- **Clan War League (CWL) tracking** -- CWL uses a separate API surface (`/clanwarleagues/wars/{warTag}`) with its own data model. Supporting it requires additional tables and ingestion logic.
- **Time-series player snapshots** -- currently, player records are overwritten on each ingestion. Appending to a `player_snapshots` table would enable trophy progression charts and activity tracking over time.
- **WebSocket or SSE for live updates** -- the frontend currently polls on page load. For active war tracking, server-sent events from the backend would reduce perceived latency.
- **Containerized deployment** -- replacing the systemd-based deployment with Docker Compose (or a container orchestrator) would simplify environment management and enable horizontal scaling of the API layer.
- **Rate limit backoff** -- the Supercell API enforces per-second rate limits. The current sequential approach stays well under the limit for small clan counts, but a backoff/retry strategy would be necessary for tracking 50+ clans.

---

## Screenshots

*Coming soon -- screenshots of the dashboard, player list, war detail, and raid detail views.*

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI Themes, react-router-dom (HashRouter) |
| Backend | Python, FastAPI, Uvicorn |
| Ingestion | Python, httpx, supabase-py |
| Database | Supabase (hosted PostgreSQL) |
| Infrastructure | Oracle Cloud VM, systemd, iptables |
| External API | Supercell Clash of Clans API v1 |
