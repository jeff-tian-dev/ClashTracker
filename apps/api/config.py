import os
from pathlib import Path
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / ".env.local")

SUPABASE_URL: str = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
# Intentionally lazy: import-time access must not crash tests or tooling without .env.
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

if not SUPABASE_URL and os.environ.get("STRICT_CONFIG", "").lower() in ("1", "true", "yes"):
    raise RuntimeError("SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL is not set (STRICT_CONFIG=1)")
