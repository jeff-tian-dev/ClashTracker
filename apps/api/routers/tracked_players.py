import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator

from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

_TRACKING_GROUPS = frozenset({"clan_july", "external"})


class TrackedPlayerCreate(BaseModel):
    player_tag: str
    """Omit to resolve from `players` table, else fall back to \"Unknown player\"."""
    display_name: str | None = None
    note: str | None = None
    tracking_group: str = "clan_july"

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_name_key(cls, data):
        if isinstance(data, dict) and "display_name" not in data and "name" in data:
            return {**data, "display_name": data["name"]}
        return data

    @field_validator("display_name")
    @classmethod
    def display_name_optional_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = (v or "").strip()
        return s if s else None

    @field_validator("tracking_group")
    @classmethod
    def tracking_group_valid(cls, v: str) -> str:
        s = (v or "").strip()
        if s not in _TRACKING_GROUPS:
            raise ValueError(f"tracking_group must be one of: {sorted(_TRACKING_GROUPS)}")
        return s


class TrackedPlayerUpdate(BaseModel):
    display_name: str | None = None
    tracking_group: str | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_if_provided(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = (v or "").strip()
        if not s:
            raise ValueError("display_name cannot be empty")
        return s

    @field_validator("tracking_group")
    @classmethod
    def tracking_group_if_provided(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = (v or "").strip()
        if s not in _TRACKING_GROUPS:
            raise ValueError(f"tracking_group must be one of: {sorted(_TRACKING_GROUPS)}")
        return s

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.display_name is None and self.tracking_group is None:
            raise ValueError("Provide display_name and/or tracking_group")
        return self


def _normalize_player_tag(raw: str) -> str:
    tag = raw.strip().upper()
    if not tag.startswith("#"):
        tag = f"#{tag}"
    return tag


def _resolve_display_name_from_players(db, tag: str) -> str:
    pres = db.table("players").select("name").eq("tag", tag).limit(1).execute()
    rows = pres.data or []
    if rows:
        n = (rows[0].get("name") or "").strip()
        if n:
            return n
    return "Unknown player"


@router.get("/tracked-players")
def list_tracked_players(
    tracking_group: str | None = Query(
        None,
        description="Filter: clan_july or external. Omit to return all.",
    ),
):
    db = get_db()
    if tracking_group is not None and tracking_group not in _TRACKING_GROUPS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_tracking_group",
                "hint": f"Use one of: {sorted(_TRACKING_GROUPS)}",
            },
        )
    logger.debug("list tracked_players", extra={"event": "api.db.query", "table": "tracked_players"})
    query = db.table("tracked_players").select("*")
    if tracking_group is not None:
        query = query.eq("tracking_group", tracking_group)
    resp = query.order("added_at", desc=True).execute()
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
    rows = resp.data
    for row in rows:
        if "display_name" not in row and row.get("name") is not None:
            row["display_name"] = row["name"]
        elif "display_name" not in row:
            row["display_name"] = ""

    need_fallback = [
        r["player_tag"] for r in rows if not (str(r.get("display_name") or "")).strip()
    ]
    if need_fallback:
        pres = db.table("players").select("tag,name").in_("tag", need_fallback).execute()
        pmap = {p["tag"]: (p.get("name") or "").strip() for p in (pres.data or [])}
        for r in rows:
            if not (str(r.get("display_name") or "")).strip():
                fn = pmap.get(r["player_tag"])
                if fn:
                    r["display_name"] = fn

    for row in rows:
        row.pop("name", None)
        if not row.get("tracking_group"):
            row["tracking_group"] = "clan_july"

    return {"data": rows}


@router.post("/tracked-players", status_code=201)
def add_tracked_player(body: TrackedPlayerCreate, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug("add tracked_players", extra={"event": "api.db.write", "table": "tracked_players"})
    tag = _normalize_player_tag(body.player_tag)
    display_name = (
        body.display_name
        if body.display_name
        else _resolve_display_name_from_players(db, tag)
    )
    row = {
        "player_tag": tag,
        "display_name": display_name,
        "note": body.note,
        "tracking_group": body.tracking_group,
    }
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
        row.setdefault("tracking_group", body.tracking_group)
        return row
    out = resp.data[0]
    if isinstance(out, dict):
        if "display_name" not in out and out.get("name") is not None:
            out["display_name"] = out["name"]
        out.pop("name", None)
        if not out.get("tracking_group"):
            out["tracking_group"] = body.tracking_group
    return out


@router.patch("/tracked-players/{tag:path}")
def update_tracked_player(tag: str, body: TrackedPlayerUpdate, _: None = Depends(require_admin)):
    db = get_db()
    norm_tag = _normalize_player_tag(tag)
    update_payload: dict = {}
    if body.display_name is not None:
        update_payload["display_name"] = body.display_name
    if body.tracking_group is not None:
        update_payload["tracking_group"] = body.tracking_group
    logger.debug(
        "patch tracked_players",
        extra={"event": "api.db.write", "table": "tracked_players", "player_tag": norm_tag},
    )
    resp = db.table("tracked_players").update(update_payload).eq("player_tag", norm_tag).execute()
    rows = resp.data or []
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "player_tag": tag, "hint": "No tracked player row for this tag."},
        )
    out = rows[0]
    if isinstance(out, dict):
        if "display_name" not in out and out.get("name") is not None:
            out["display_name"] = out["name"]
        out.pop("name", None)
        if not out.get("tracking_group"):
            out["tracking_group"] = "clan_july"
    return out


@router.delete("/tracked-players/{tag:path}", status_code=204)
def remove_tracked_player(tag: str, _: None = Depends(require_admin)):
    db = get_db()
    logger.debug(
        "remove tracked_players",
        extra={"event": "api.db.write", "table": "tracked_players", "player_tag": tag},
    )
    db.table("tracked_players").delete().eq("player_tag", tag).execute()
    return None
