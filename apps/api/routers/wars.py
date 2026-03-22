import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from ..auth import require_admin
from ..database import get_db
from ..supabase_errors import http_exception_for_single_lookup

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/wars")
def list_wars(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clan_tag: str | None = None,
    state: str | None = None,
):
    db = get_db()
    logger.debug(
        "list wars",
        extra={"event": "api.db.query", "table": "wars", "page": page, "page_size": page_size},
    )
    query = db.table("wars").select("*", count="exact")

    if clan_tag:
        query = query.eq("clan_tag", clan_tag)
    if state:
        query = query.eq("state", state)

    offset = (page - 1) * page_size
    query = query.order("start_time", desc=True).range(offset, offset + page_size - 1)
    resp = query.execute()

    return {
        "data": resp.data,
        "total": resp.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/wars/{war_id}")
def get_war(war_id: int):
    db = get_db()
    logger.debug(
        "get war",
        extra={"event": "api.db.query", "table": "wars", "war_id": war_id},
    )
    try:
        war = db.table("wars").select("*").eq("id", war_id).single().execute()
    except APIError as exc:
        raise http_exception_for_single_lookup(exc, resource="war", identifier=str(war_id)) from exc
    attacks = (
        db.table("war_attacks")
        .select("*")
        .eq("war_id", war_id)
        .order("attack_order")
        .execute()
    )
    result = war.data
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "resource": "war",
                "identifier": str(war_id),
                "hint": "War row missing after query (unexpected empty data).",
            },
        )
    if not isinstance(attacks.data, list):
        logger.error(
            "invariant failed: war_attacks.data must be a list",
            extra={"event": "api.invariant.violation", "war_id": war_id, "got_type": type(attacks.data).__name__},
        )
        raise RuntimeError("war_attacks query returned non-list data")
    result["attacks"] = attacks.data
    return result


@router.delete("/wars/{war_id}", status_code=204)
def delete_war(war_id: int, _: None = Depends(require_admin)):
    db = get_db()
    db.table("wars").delete().eq("id", war_id).execute()
    logger.info(
        "war deleted",
        extra={"event": "admin.delete.war", "war_id": war_id},
    )
