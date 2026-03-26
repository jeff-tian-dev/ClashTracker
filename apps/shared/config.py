"""Unified environment loading for API and ingestion services."""

import os
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env.local")

# ── Supabase ──────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get(
    "NEXT_PUBLIC_SUPABASE_URL", os.environ.get("SUPABASE_URL", "")
)
# Intentionally lazy: import-time access must not crash tests or tooling without .env.
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Admin ─────────────────────────────────────────────────────────────
ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

# ── Supercell API ─────────────────────────────────────────────────────
COC_API_TOKEN: str = os.environ.get("COC_API_TOKEN", "")
COC_BASE_URL: str = "https://api.clashofclans.com/v1"

# ── Strict mode (CI / production) ────────────────────────────────────
if not SUPABASE_URL and os.environ.get("STRICT_CONFIG", "").lower() in ("1", "true", "yes"):
    raise RuntimeError("SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL is not set (STRICT_CONFIG=1)")
