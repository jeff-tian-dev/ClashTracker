import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from ..auth import require_admin
from ..database import get_db
from ..supabase_errors import http_exception_for_single_lookup

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/raids")
def list_raids(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clan_tag: str | None = None,
):
    db = get_db()
    logger.debug(
        "list raids",
        extra={"event": "api.db.query", "table": "capital_raids", "page": page, "page_size": page_size},
    )
    query = db.table("capital_raids").select("*", count="exact")

    if clan_tag:
        query = query.eq("clan_tag", clan_tag)

    offset = (page - 1) * page_size
    query = query.order("start_time", desc=True).range(offset, offset + page_size - 1)
    resp = query.execute()

    return {
        "data": resp.data,
        "total": resp.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/raids/{raid_id}")
def get_raid(raid_id: int):
    db = get_db()
    logger.debug(
        "get raid",
        extra={"event": "api.db.query", "table": "capital_raids", "raid_id": raid_id},
    )
    try:
        raid = db.table("capital_raids").select("*").eq("id", raid_id).single().execute()
    except APIError as exc:
        raise http_exception_for_single_lookup(exc, resource="raid", identifier=str(raid_id)) from exc
    members = (
        db.table("raid_members")
        .select("*")
        .eq("raid_id", raid_id)
        .order("capital_resources_looted", desc=True)
        .execute()
    )
    result = raid.data
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "resource": "raid",
                "identifier": str(raid_id),
                "hint": "Raid row missing after query (unexpected empty data).",
            },
        )
    if not isinstance(members.data, list):
        logger.error(
            "invariant failed: raid_members.data must be a list",
            extra={"event": "api.invariant.violation", "raid_id": raid_id, "got_type": type(members.data).__name__},
        )
        raise RuntimeError("raid_members query returned non-list data")
    result["members"] = members.data
    return result


@router.delete("/raids/{raid_id}", status_code=204)
def delete_raid(raid_id: int, _: None = Depends(require_admin)):
    db = get_db()
    db.table("capital_raids").delete().eq("id", raid_id).execute()
    logger.info(
        "raid deleted",
        extra={"event": "admin.delete.raid", "raid_id": raid_id},
    )
