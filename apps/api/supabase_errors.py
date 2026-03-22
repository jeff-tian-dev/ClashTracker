"""Map Supabase/PostgREST errors to HTTP responses with actionable detail."""

from __future__ import annotations

from fastapi import HTTPException
from postgrest.exceptions import APIError


def http_exception_for_single_lookup(
    exc: APIError,
    *,
    resource: str,
    identifier: str,
) -> HTTPException:
    """PostgREST returns PGRST116 when .single() matches zero (or multiple) rows."""
    msg = str(exc).lower()
    if "pgrst116" in msg or "0 rows" in msg or "contains 0 rows" in msg:
        return HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "resource": resource,
                "identifier": identifier,
                "hint": f"No {resource} found for this identifier. Verify the tag or id and ingestion.",
            },
        )
    return HTTPException(
        status_code=502,
        detail={
            "error": "database_error",
            "resource": resource,
            "identifier": identifier,
            "message": str(exc),
            "hint": "Upstream PostgREST/Supabase rejected the query; check API logs for request_id and Supabase status.",
        },
    )
