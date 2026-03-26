"""API configuration — re-exports shared env vars."""

from shared.config import ADMIN_API_KEY, SUPABASE_KEY, SUPABASE_URL

__all__ = ["ADMIN_API_KEY", "SUPABASE_KEY", "SUPABASE_URL"]
