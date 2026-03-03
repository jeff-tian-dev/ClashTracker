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
                    |   (hosted, 7 tables, 3 migrations)  |
                    +------^-----------------------------+
                           |
                    +------+------+
                    |   Browser   |
                    | React + TS  |  <--- fetches JSON from FastAPI
                    +-------------+
```

The frontend never communicates with Supabase directly. All database access is server-side, routed through the FastAPI layer using a service-role key that never leaves the backend.

---

## Core Capabilities

- **Multi-clan tracking** -- a `tracked_clans` configuration table drives ingestion dynamically; adding or removing a clan tag requires no code changes or redeployments.
- **Idempotent ingestion** -- every upsert uses composite unique constraints (`ON CONFLICT ... DO UPDATE`), making the pipeline safe to re-run at any frequency without creating duplicates.
- **Hourly automated sync** -- a systemd timer triggers the ingestion service on a fixed schedule with jitter, managed entirely by the OS process supervisor.
- **Read-only REST API** -- paginated, filterable endpoints for players, wars, capital raids, and dashboard summaries, plus CRUD for tracked clans.
- **Responsive dashboard** -- React frontend with loading states, empty states, search, pagination, and drill-down detail views for every entity.

---

## Technical Design Highlights

### Database Schema Design

The schema spans 7 tables across 3 ordered migration files, designed around the domain boundaries of the Supercell API.

**Key decisions:**

- **Natural primary keys for game entities.** `clans` and `players` use the Supercell-assigned tag (e.g. `#2GRPGV0VL`) as the primary key rather than a surrogate. This eliminates lookup joins during ingestion and makes the upsert path a single statement per entity.

- **`tracked_clans` is intentionally not foreign-keyed to `clans`.** A clan tag can be added to the tracking list before the first ingestion run populates the `clans` table. This avoids a chicken-and-egg dependency between configuration and data.

- **Composite unique constraints for deduplication.** Wars are deduplicated on `(clan_tag, preparation_start_time)` and capital raids on `(clan_tag, start_time)`. These are the natural identifiers from the Supercell API and allow safe `UPSERT` semantics without maintaining external state.

- **Cascading deletes on child tables.** `war_attacks` and `raid_members` use `ON DELETE CASCADE` referencing their parent records, keeping orphan cleanup automatic.

- **Indexes on all foreign keys and temporal columns.** Every FK column and `updated_at` field is indexed to support the API's filtering and ordering queries without full table scans.

### Ingestion Pipeline

The ingestion service is a single-purpose Python process designed to run as a one-shot job (`Type=oneshot` in systemd). It follows a straightforward pipeline:

1. Query `tracked_clans` from Supabase to get the current list of clan tags.
2. For each clan: fetch clan metadata, current war status, capital raid seasons, and full player details for every member.
3. Upsert all data through the Supabase REST API using the service-role key.

**Design choices:**

- **Synchronous HTTP with `httpx`.** The Supercell API is rate-limited and the dataset per clan is bounded (~50 members, 1 active war, 5 raid seasons). Async would add complexity without meaningful throughput gains at this scale.
- **Graceful degradation.** Private war logs (HTTP 403) and missing clans (HTTP 404) are logged and skipped rather than aborting the entire run. One clan's API issue does not block ingestion for others.
- **Non-zero exit on fatal errors.** Unhandled exceptions propagate to `sys.exit(1)`, which systemd records as a failure -- visible in `journalctl` and compatible with alerting.

### API Layer

The backend is a FastAPI application with 6 routers, each handling a single domain. All routes are read-only except for the tracked clans management endpoints (POST/DELETE).

- **Pagination** is offset-based via `page` and `page_size` query parameters. Every list endpoint returns `{ data, total, page, page_size }` to support frontend pagination controls.
- **Filtering** is scoped per resource: players support `clan_tag` and `search` (name ILIKE), wars support `clan_tag` and `state`, raids support `clan_tag`.
- **Detail endpoints** for wars and raids eagerly load child records (attacks and member contributions) in a second query, returned as a nested `attacks` or `members` array.
- **CORS** is configured via environment variable (`CORS_ORIGINS`) to allow extension beyond the default `localhost:5173` without code changes.

### Frontend Architecture

The frontend is a single-page React application built with Vite, TypeScript, Tailwind CSS, and Radix UI Themes.

- **Typed API client** (`src/lib/api.ts`) -- a single module with full TypeScript interfaces for every API response shape, a generic `request<T>()` wrapper, and named methods for each endpoint. No `any` types.
- **Collocated page components** -- each route maps to a page component in `src/pages/` that owns its own data fetching via `useEffect`, loading state, and error handling. No global state management; the data model is simple enough that per-page fetching is the right tradeoff.
- **Reusable primitives** -- `LoadingSpinner`, `EmptyState`, and `Pagination` components are shared across all list views.
- **Radix UI Themes** for accessible, consistent UI components (tables, cards, badges, dialogs) without writing custom component logic.

---

## Security Considerations

- **All secrets live in a single `.env.local` file** at the project root, excluded from version control via `.gitignore`. The SSH private key is similarly gitignored by extension (`*.key`).
- **The Supercell API token and Supabase service-role key never reach the browser.** The frontend only knows the backend's public URL (`VITE_API_URL`). All database and external API access is server-side.
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
```

### 2. Run database migrations

Paste the contents of each file in `supabase/migrations/` into the Supabase SQL Editor, in order (001, 002, 003).

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

---

## Deployment Overview

The backend and ingestion service are deployed to an Oracle Cloud VM (Ubuntu 24.04) via a single PowerShell script (`deploy.ps1`) that:

1. SCPs `apps/`, `deploy/`, and `.env.local` to the VM.
2. Creates a Python virtual environment and installs all dependencies.
3. Installs two systemd units:
   - `clash-tracker-api.service` -- runs uvicorn on port 8000, restarts on failure.
   - `clash-tracker-ingestion.timer` -- triggers the ingestion service hourly with randomized jitter.
4. Configures iptables to allow inbound traffic on port 8000.

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

## Project Structure

```
Analytics-Dashboard/
├── apps/
│   ├── api/                     # FastAPI backend
│   │   ├── main.py              # App entrypoint, CORS, router registration
│   │   ├── config.py            # Environment loading
│   │   ├── database.py          # Supabase client factory
│   │   └── routers/             # health, dashboard, players, wars, raids, tracked_clans
│   ├── ingestion/               # Data pipeline
│   │   ├── main.py              # CLI entrypoint
│   │   ├── ingest.py            # Orchestrator (run_once)
│   │   ├── supercell_client.py  # Supercell API wrapper
│   │   ├── db.py                # Supabase upsert helpers
│   │   └── config.py            # Environment loading
│   └── web/                     # React frontend
│       └── src/
│           ├── lib/api.ts       # Typed API client
│           ├── pages/           # Dashboard, Players, Wars, Raids, TrackedClans
│           └── components/      # Layout, Pagination, LoadingSpinner, EmptyState
├── deploy/                      # systemd units + VM setup script
├── supabase/migrations/         # 001_core_tables, 002_wars, 003_capital_raids
├── legacy-v1/                   # Original V1 implementation (HTML/CSS + Python + JSON)
├── deploy.ps1                   # One-command deployment to Oracle VM
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
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Radix UI Themes |
| Backend | Python, FastAPI, Uvicorn |
| Ingestion | Python, httpx, supabase-py |
| Database | Supabase (hosted PostgreSQL) |
| Infrastructure | Oracle Cloud VM, systemd, iptables |
| External API | Supercell Clash of Clans API v1 |
