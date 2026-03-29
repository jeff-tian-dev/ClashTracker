import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from ..auth import require_admin
from ..database import get_db
from ..supabase_errors import http_exception_for_single_lookup

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _tracked_players_by_tag(db) -> dict[str, str]:
    r = db.table("tracked_players").select("player_tag,tracking_group").execute()
    out: dict[str, str] = {}
    for row in r.data or []:
        tag = row.get("player_tag")
        if not tag:
            continue
        g = row.get("tracking_group") or "clan_july"
        out[tag] = g
    return out


def _attach_tracked_flags(rows: list, by_tag: dict[str, str]) -> None:
    for row in rows:
        tag = row["tag"]
        group = by_tag.get(tag)
        row["is_always_tracked"] = group is not None
        row["tracking_group"] = group


def _attack_stats_7d_for_tags(db, tags: list[str], since_iso: str) -> dict[str, dict]:
    """Count + earliest attacked_at per tag since since_iso (SQL aggregate, no row cap)."""
    if not tags:
        return {}
    out: dict[str, dict] = {}
    chunk_size = 200
    for i in range(0, len(tags), chunk_size):
        chunk = tags[i : i + chunk_size]
        resp = db.rpc(
            "player_attack_counts_since",
            {"p_since": since_iso, "p_tags": chunk},
        ).execute()
        for row in resp.data or []:
            tag = row.get("player_tag")
            if tag is None:
                continue
            first = row.get("first_attacked_at")
            out[tag] = {
                "count": int(row.get("attack_count") or 0),
                "first_at": first if first else None,
            }
    return out


def _attach_attacks_7d(db, rows: list, since_iso: str) -> None:
    tags = [r["tag"] for r in rows]
    by_tag = _attack_stats_7d_for_tags(db, tags, since_iso)
    for row in rows:
        stats = by_tag.get(row["tag"])
        if not stats:
            row["attacks_7d"] = 0
            row["attacks_7d_first_at"] = None
            continue
        row["attacks_7d"] = stats["count"]
        row["attacks_7d_first_at"] = stats["first_at"]


def _fetch_all_players_filtered(db, clan_tag: str | None, search: str | None) -> list:
    """Paginate through PostgREST range in case of large rosters."""
    all_rows: list = []
    batch = 1000
    start = 0
    while True:
        q = db.table("players").select("*")
        if clan_tag:
            q = q.eq("clan_tag", clan_tag)
        if search:
            q = q.ilike("name", f"%{search}%")
        resp = q.range(start, start + batch - 1).execute()
        chunk = resp.data or []
        all_rows.extend(chunk)
        if len(chunk) < batch:
            break
        start += batch
    return all_rows


@router.get("/players")
def list_players(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clan_tag: str | None = None,
    search: str | None = None,
    sort: Literal["roster", "name", "trophies", "attacks_7d"] = "roster",
    order: Literal["asc", "desc"] = "asc",
):
    db = get_db()
    logger.debug(
        "list players",
        extra={
            "event": "api.db.query",
            "table": "players",
            "page": page,
            "page_size": page_size,
            "sort": sort,
        },
    )
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    if sort == "attacks_7d":
        rows = _fetch_all_players_filtered(db, clan_tag, search)
        total = len(rows)
        _attach_attacks_7d(db, rows, since_7d)

        def _name_key(r: dict) -> str:
            return (r.get("name") or "").lower()

        if order == "desc":
            rows.sort(key=lambda r: (-r["attacks_7d"], _name_key(r)))
        else:
            rows.sort(key=lambda r: (r["attacks_7d"], _name_key(r)))
        offset = (page - 1) * page_size
        data = rows[offset : offset + page_size]
        by_tag = _tracked_players_by_tag(db)
        _attach_tracked_flags(data, by_tag)
        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    query = db.table("players").select("*", count="exact")

    if clan_tag:
        query = query.eq("clan_tag", clan_tag)
    if search:
        query = query.ilike("name", f"%{search}%")

    if sort == "roster":
        query = (
            query.order("roster_sort_bucket")
            .order("left_tracked_roster_at", desc=True)
            .order("name")
        )
    elif sort == "name":
        query = query.order("name", desc=(order == "desc"))
    else:
        query = query.order("trophies", desc=(order == "desc"))

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)
    resp = query.execute()

    by_tag = _tracked_players_by_tag(db)
    data = resp.data or []
    _attach_tracked_flags(data, by_tag)
    _attach_attacks_7d(db, data, since_7d)

    return {
        "data": data,
        "total": resp.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/players/{tag:path}/activity")
def get_player_activity(tag: str):
    """Attack timestamps (UTC) from battle logs for the last 90 days (client charts use local dates)."""
    db = get_db()
    logger.debug(
        "get player activity",
        extra={"event": "api.db.query", "table": "player_attack_events", "player_tag": tag},
    )
    try:
        db.table("players").select("tag").eq("tag", tag).single().execute()
    except APIError as exc:
        raise http_exception_for_single_lookup(exc, resource="player", identifier=tag) from exc

    since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    resp = (
        db.table("player_attack_events")
        .select("attacked_at")
        .eq("player_tag", tag)
        .gte("attacked_at", since)
        .order("attacked_at", desc=False)
        .execute()
    )
    rows = resp.data or []
    return {"attacks": [{"attacked_at": r["attacked_at"]} for r in rows]}


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
    by_tag = _tracked_players_by_tag(db)
    row = resp.data
    tag = row["tag"]
    group = by_tag.get(tag)
    row["is_always_tracked"] = group is not None
    row["tracking_group"] = group
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    _attach_attacks_7d(db, [row], since_7d)
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
