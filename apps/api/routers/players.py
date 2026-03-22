import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from ..auth import require_admin
from ..database import get_db
from ..supabase_errors import http_exception_for_single_lookup

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _always_tracked_tag_set(db) -> set[str]:
    r = db.table("tracked_players").select("player_tag").execute()
    return {row["player_tag"] for row in (r.data or [])}


def _attach_always_flag(rows: list, always: set[str]) -> None:
    for row in rows:
        row["is_always_tracked"] = row["tag"] in always


@router.get("/players")
def list_players(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clan_tag: str | None = None,
    search: str | None = None,
):
    db = get_db()
    logger.debug(
        "list players",
        extra={"event": "api.db.query", "table": "players", "page": page, "page_size": page_size},
    )
    query = db.table("players").select("*", count="exact")

    if clan_tag:
        query = query.eq("clan_tag", clan_tag)
    if search:
        query = query.ilike("name", f"%{search}%")

    offset = (page - 1) * page_size
    query = (
        query.order("roster_sort_bucket")
        .order("left_tracked_roster_at", desc=True)
        .order("name")
        .range(offset, offset + page_size - 1)
    )
    resp = query.execute()

    always = _always_tracked_tag_set(db)
    data = resp.data or []
    _attach_always_flag(data, always)

    return {
        "data": data,
        "total": resp.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/players/{tag:path}")
def get_player(tag: str):
    db = get_db()
    logger.debug(
        "get player by tag",
        extra={"event": "api.db.query", "table": "players", "lookup": "tag"},
    )
    try:
        resp = db.table("players").select("*").eq("tag", tag).single().execute()
    except APIError as exc:
        raise http_exception_for_single_lookup(exc, resource="player", identifier=tag) from exc
    if resp.data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "resource": "player",
                "identifier": tag,
                "hint": "Player row missing after query (unexpected empty data).",
            },
        )
    always = _always_tracked_tag_set(db)
    row = resp.data
    row["is_always_tracked"] = row["tag"] in always
    return row


@router.delete("/players/{tag:path}", status_code=204)
def delete_player(tag: str, _: None = Depends(require_admin)):
    db = get_db()
    db.table("tracked_players").delete().eq("player_tag", tag).execute()
    db.table("players").delete().eq("tag", tag).execute()
    logger.info(
        "player deleted",
        extra={"event": "admin.delete.player", "player_tag": tag},
    )
