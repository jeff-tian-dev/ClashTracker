import logging

from supabase import create_client, Client

from .config import SUPABASE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)


def get_db() -> Client:
    """Create a fresh Supabase client per call to avoid stale HTTP/2 connections."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "database.unconfigured: set NEXT_PUBLIC_SUPABASE_URL (or SUPABASE_URL) and "
            "SUPABASE_SERVICE_ROLE_KEY before handling requests that need the database."
        )
    logger.debug(
        "supabase client created",
        extra={"event": "db.client.create", "supabase_host": _host_hint(SUPABASE_URL)},
    )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _host_hint(url: str) -> str:
    try:
        from urllib.parse import urlparse

        netloc = urlparse(url).netloc
        return netloc or "unknown"
    except Exception:
        return "unknown"
