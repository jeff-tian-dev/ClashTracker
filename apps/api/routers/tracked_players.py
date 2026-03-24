import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


class TrackedPlayerCreate(BaseModel):
    player_tag: str
    name: str
    note: str | None = None

    @field_validator("name")
    @classmethod
    def name_stripped_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("name is required")
        return s


def _normalize_player_tag(raw: str) -> str:
    tag = raw.strip().upper()
    if not tag.startswith("#"):
        tag = f"#{tag}"
    return tag


@router.get("/tracked-players")
def list_tracked_players():
    db = get_db()
    logger.debug("list tracked_players", extra={"event": "api.db.query", "table": "tracked_players"})
    resp = (
        db.table("tracked_players")
        .select("*")
        .order("added_at", desc=True)
        .execute()
    )
    if resp.data is None or not isinstance(resp.data, list):
        logger.error(
            "tracked_players invariant failed",
            extra={"event": "api.invariant.violation", "got_type": type(resp.data).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "invariant_violation",
                "hint": "tracked_players select did not return a list.",
            },
        )
    return {"data": resp.data}


@router.post("/tracked-players", status_code=201)
def add_tracked_player(body: TrackedPlayerCreate, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug("add tracked_players", extra={"event": "api.db.write", "table": "tracked_players"})
    tag = _normalize_player_tag(body.player_tag)
    row = {"player_tag": tag, "name": body.name, "note": body.note}
    try:
        resp = db.table("tracked_players").insert(row).execute()
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate" in msg or "unique" in msg:
            logger.info(
                "tracked_players conflict",
                extra={"event": "api.db.conflict", "player_tag": tag},
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "already_tracked",
                    "player_tag": tag,
                    "hint": "Remove the existing row or use a different player tag.",
                },
            ) from exc
        logger.exception(
            "tracked_players insert failed",
            extra={"event": "api.db.error", "player_tag": tag},
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "database_write_failed",
                "player_tag": tag,
                "message": str(exc),
                "hint": "Check Supabase logs and API request_id.",
            },
        ) from exc
    if not resp.data:
        logger.warning(
            "insert returned no row",
            extra={"event": "api.db.unexpected", "table": "tracked_players", "player_tag": tag},
        )
        return row
    return resp.data[0]


@router.delete("/tracked-players/{tag:path}", status_code=204)
def remove_tracked_player(tag: str, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug(
        "remove tracked_players",
        extra={"event": "api.db.write", "table": "tracked_players", "player_tag": tag},
    )
    db.table("tracked_players").delete().eq("player_tag", tag).execute()
    return None
