"""Ingestion configuration — re-exports shared env vars."""

from shared.config import COC_API_TOKEN, COC_BASE_URL, SUPABASE_KEY, SUPABASE_URL

__all__ = ["COC_API_TOKEN", "COC_BASE_URL", "SUPABASE_KEY", "SUPABASE_URL"]
