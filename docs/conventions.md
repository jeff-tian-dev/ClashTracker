# Conventions

Strict rules for consistency. AI agents must follow these.

---

## Naming

### Terminology
- **"player"** — always. Never "user", "member", or "account" for in-game entities.
- **"clan"** — always. Never "guild", "team", or "group".
- **"tag"** — the `#`-prefixed Supercell identifier (e.g. `#2GRPGV0VL`). Always call it "tag", not "id" for game entities.
- **"war"** — clan war. Never "battle" (battles are individual attacks within wars or legends).
- **"raid"** — Clan Capital raid weekend event.
- **"legends"** — Legends League daily tracking system.
- **"tracked_players"** / **"tracked_clans"** — admin-managed lists. The naming uses underscores in code and hyphens in URLs.

### URL Conventions
- API routes use **kebab-case**: `/api/tracked-players`, `/api/tracked-clans`
- Frontend routes use **kebab-case**: `/tracked-players`, `/tracked-clans`

### File Naming
- **Python**: `snake_case.py` for all modules
- **TypeScript pages**: `PascalCase.tsx` (e.g. `PlayerDetail.tsx`)
- **TypeScript lib/helpers**: `camelCase.ts` (e.g. `api.ts`, `formatRelativeLeft.ts`)
- **TypeScript components**: `PascalCase.tsx` (e.g. `LoadingSpinner.tsx`)
- **SQL migrations**: `NNN_descriptive_name.sql` (zero-padded 3-digit, e.g. `001_core_tables.sql`)

### Variable & Field Naming
- **Python**: `snake_case` everywhere (functions, variables, dict keys)
- **TypeScript**: `camelCase` for variables/functions, `PascalCase` for types/interfaces/components
- **Database columns**: `snake_case` (matches Python convention)
- **API response keys**: `snake_case` (matches DB columns — no transformation layer)

---

## File Organization

### Separation of Concerns
```
apps/api/         → HTTP handling only (routers, auth, error mapping)
apps/ingestion/   → Data pipeline only (fetch, transform, upsert)
apps/shared/      → Cross-cutting logic (config, logging, domain helpers)
apps/web/src/lib/ → API client, contexts, utility functions
apps/web/src/pages/ → One file per route, collocated data fetching
apps/web/src/components/ → Reusable UI primitives only
```

### Rules
- **No API calls inside UI components** — only pages fetch data via `api.ts` methods in `useEffect`
- **No database access in routers** except through `database.get_db()` — never import `supabase` directly
- **No business logic in `main.py`** — routers handle everything, `main.py` only registers them
- **Config flows one way**: `shared/config.py` → `api/config.py` / `ingestion/config.py` → consumers. Never read `os.environ` directly outside `shared/config.py`.
- **Shared domain logic** goes in `apps/shared/`, not duplicated across api and ingestion
- **Tests** go in `tests/` at repo root, not colocated with source

---

## Type Usage

### Python (Backend / Ingestion)
- Use **type hints** on all function signatures
- Use `str | None` union syntax (Python 3.11+), not `Optional[str]`
- Use **Pydantic models** for API request bodies (not raw dicts)
- API response shapes: plain dicts are acceptable (no Pydantic response models enforced — but see `schemas/contract.py` for test contracts)

### TypeScript (Frontend)
- **No `any` types** — the API client (`api.ts`) has full interfaces for every response shape
- All API response types are defined and exported from `api.ts`
- Components receive **typed props** — use the interfaces from `api.ts`

---

## Styling / UI

- **Tailwind CSS v4** for utility classes
- **Radix UI Themes** for component primitives (tables, cards, badges, dialogs)
- **No custom CSS** for components — use Tailwind utilities only
- `index.css` is minimal (just Tailwind import)
- **Responsive design** — maintain mobile responsiveness on all pages
- **Dark mode** supported via `ThemePreferenceContext.tsx`

---

## Logging

### Structured Logging
- Every log line must include an `event` key for filtering/grep (e.g. `"event": "ingestion.db.upsert"`)
- Use the `extra={}` keyword argument pattern for structured fields
- **API**: `request_id` context on every log line (injected by middleware)
- **Ingestion**: `ingestion_run_id` context on every log line

### Event Naming
- Format: `{subsystem}.{domain}.{action}` (e.g. `api.db.query`, `ingestion.clan.start`, `api.request.complete`)
- Always lowercase, dot-separated

### Logger Setup
- Always use `logging.getLogger(__name__)` in each module
- Configure via `shared/logutil.configure_logging()` — never call `basicConfig()` directly

---

## Error Handling

### API Errors
- Use `HTTPException` with structured `detail` dicts (not plain strings)
- Error responses include: `error` (machine-readable), `hint` (human-readable), optional `request_id`
- PostgREST errors are mapped through `supabase_errors.py`
- **Write conflicts → 409** with structured detail
- **Unconfigured ADMIN_API_KEY → 503** (not 401)
- **Invariant violations → 500** with descriptive `hint`

### Ingestion Errors
- Graceful degradation: private war logs (403) and missing clans (404) are **logged and skipped**
- One clan's API issue does not block ingestion for others
- Fatal errors → `sys.exit(1)` for systemd failure recording

---

## Database

- **Natural primary keys** for game entities (`clans.tag`, `players.tag`)
- **Composite unique constraints** for deduplication (wars, raids, battles)
- `ON DELETE CASCADE` for child tables (`war_attacks`, `raid_members`)
- **No FK from `tracked_clans`/`tracked_players` to `clans`/`players`** (tags can exist before first data fetch)
- Always use `upsert` with `on_conflict` for idempotent ingestion
- Timestamps are always UTC ISO-8601

---

## Testing

- Framework: **pytest**
- Test files: `tests/test_*.py`
- Tests use **TestClient** from FastAPI
- Contract tests validate Pydantic response shapes against fixture data
- **Run before committing**: `pytest` from repo root
- Dev dependencies: `requirements-dev.txt` (pytest, httpx)

---

## Git / Deployment

- Secrets in `.env.local` (gitignored)
- SSH keys gitignored by `*.key` pattern
- Deploy via `deploy.ps1` (SCPs Python code + migrations to Oracle VM)
- Frontend deployed to GitHub Pages via GitHub Actions on push to `main`
