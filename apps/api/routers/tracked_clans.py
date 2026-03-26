import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_admin
from ..database import get_db
from .tracked_players import _normalize_player_tag

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


class TrackedClanCreate(BaseModel):
    clan_tag: str
    note: str | None = None


@router.get("/tracked-clans")
def list_tracked_clans():
    db = get_db()
    logger.debug("list tracked clans", extra={"event": "api.db.query", "table": "tracked_clans"})
    tracked = (
        db.table("tracked_clans")
        .select("*")
        .order("added_at", desc=True)
        .execute()
    )
    if tracked.data is None or not isinstance(tracked.data, list):
        logger.error(
            "tracked_clans invariant failed",
            extra={"event": "api.invariant.violation", "got_type": type(tracked.data).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "invariant_violation",
                "hint": "tracked_clans select did not return a list.",
            },
        )

    clan_tags = [r["clan_tag"] for r in tracked.data]
    clans_map: dict = {}
    if clan_tags:
        clans_resp = (
            db.table("clans")
            .select("tag, name, badge_url, clan_level, members_count")
            .in_("tag", clan_tags)
            .execute()
        )
        clans_map = {c["tag"]: c for c in clans_resp.data}

    for row in tracked.data:
        row["clans"] = clans_map.get(row["clan_tag"])

    return {"data": tracked.data}


@router.post("/tracked-clans", status_code=201)
def add_tracked_clan(body: TrackedClanCreate, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug("add tracked clan", extra={"event": "api.db.write", "table": "tracked_clans"})
    tag = _normalize_player_tag(body.clan_tag)

    row = {"clan_tag": tag, "note": body.note}
    try:
        resp = db.table("tracked_clans").insert(row).execute()
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg:
            logger.info(
                "tracked_clans conflict",
                extra={"event": "api.db.conflict", "clan_tag": tag},
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "already_tracked",
                    "clan_tag": tag,
                    "hint": "Delete the existing row or use a different clan tag.",
                },
            ) from exc
        logger.exception(
            "tracked_clans insert failed",
            extra={"event": "api.db.error", "clan_tag": tag},
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "database_write_failed",
                "clan_tag": tag,
                "message": str(exc),
                "hint": "Check Supabase logs and API request_id.",
            },
        ) from exc
    if not resp.data:
        logger.warning(
            "insert returned no row",
            extra={"event": "api.db.unexpected", "table": "tracked_clans", "clan_tag": tag},
        )
        return row
    return resp.data[0]


@router.delete("/tracked-clans/{tag:path}", status_code=204)
def remove_tracked_clan(tag: str, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug(
        "remove tracked clan",
        extra={"event": "api.db.write", "table": "tracked_clans", "clan_tag": tag},
    )
    db.table("tracked_clans").delete().eq("clan_tag", tag).execute()
    return None
