import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from postgrest.exceptions import APIError

from ..auth import require_admin
from ..database import get_db
from ..supabase_errors import http_exception_for_single_lookup
from .tracked_players import _normalize_player_tag

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

_WAR_LEADERBOARD_LAST_WARS = frozenset({5, 10, 15})

_SORT_FIELDS = frozenset({
    "avg_offense_stars",
    "avg_offense_destruction",
    "offense_count",
    "attacks_missed",
    "avg_defense_stars",
    "avg_defense_destruction",
    "defense_count",
    "wars_participated",
    "player_name",
})


def _normalize_clan_tag(raw: str) -> str:
    tag = raw.strip().upper()
    if not tag.startswith("#"):
        tag = f"#{tag}"
    return tag


def _assert_tracked_clan(db, clan_tag: str) -> None:
    row = (
        db.table("tracked_clans")
        .select("clan_tag")
        .eq("clan_tag", clan_tag)
        .limit(1)
        .execute()
    )
    if not (row.data and len(row.data) > 0):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "resource": "tracked_clan",
                "identifier": clan_tag,
                "hint": "clan_tag must be a tracked clan.",
            },
        )


def _coerce_rpc_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize numeric types from PostgREST JSON for stable sorting/JSON."""
    out = dict(row)
    for k in (
        "offense_count",
        "defense_count",
        "wars_participated",
        "attacks_missed",
    ):
        if k in out and out[k] is not None:
            out[k] = int(out[k])
    for k in (
        "avg_offense_stars",
        "avg_offense_destruction",
        "avg_defense_stars",
        "avg_defense_destruction",
    ):
        if k in out and out[k] is not None:
            out[k] = float(out[k])
    if out.get("war_id") is not None:
        out["war_id"] = int(out["war_id"])
    if out.get("stars") is not None:
        out["stars"] = int(out["stars"])
    if out.get("attack_order") is not None:
        out["attack_order"] = int(out["attack_order"])
    if out.get("duration") is not None:
        out["duration"] = int(out["duration"])
    if out.get("destruction_percentage") is not None:
        out["destruction_percentage"] = float(out["destruction_percentage"])
    return out


def _sort_leaderboard_rows(
    rows: list[dict[str, Any]],
    sort: str,
    order: Literal["asc", "desc"],
) -> None:
    desc = order == "desc"

    def key(r: dict[str, Any]):
        v = r.get(sort)
        if sort == "player_name":
            return (v or "").casefold()
        if sort.startswith("avg_"):
            if v is None:
                return (True, 0.0)
            fv = float(v)
            return (False, -fv) if desc else (False, fv)
        iv = int(v or 0)
        return -iv if desc else iv

    if sort == "player_name":
        rows.sort(key=key, reverse=desc)
    else:
        rows.sort(key=key)


@router.get("/wars/player-stats")
def war_player_stats(
    clan_tag: str = Query(..., min_length=1),
    sort: str = Query("avg_offense_stars"),
    order: Literal["asc", "desc"] = Query("desc"),
    last_wars: int | None = Query(None, description="Last N ended wars by start time; omit or null = all"),
):
    """Aggregated war performance per player for one tracked clan (ended wars)."""
    db = get_db()
    normalized = _normalize_clan_tag(clan_tag)
    if last_wars is not None and last_wars not in _WAR_LEADERBOARD_LAST_WARS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_last_wars",
                "hint": "last_wars must be one of: 5, 10, 15, or omitted for all wars",
            },
        )
    if sort not in _SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_sort",
                "hint": f"sort must be one of: {sorted(_SORT_FIELDS)}",
            },
        )
    _assert_tracked_clan(db, normalized)

    logger.debug(
        "war player stats",
        extra={
            "event": "api.wars.player_stats",
            "clan_tag": normalized,
            "sort": sort,
            "order": order,
            "last_wars": last_wars,
        },
    )

    rpc_args: dict[str, Any] = {"p_clan_tag": normalized}
    if last_wars is not None:
        rpc_args["p_max_wars"] = last_wars
    resp = db.rpc("war_player_leaderboard_stats", rpc_args).execute()
    raw = resp.data or []
    rows = [_coerce_rpc_row(dict(r)) for r in raw]
    _sort_leaderboard_rows(rows, sort, order)

    return {
        "data": rows,
        "clan_tag": normalized,
        "sort": sort,
        "order": order,
        "last_wars": last_wars,
    }


@router.get("/wars/players/{tag}/history")
def war_player_history(
    tag: str,
    clan_tag: str = Query(..., min_length=1),
    last_wars: int | None = Query(None, description="Last N ended wars; omit or null = all"),
):
    """Offense and defense attack rows for one player in one tracked clan."""
    db = get_db()
    normalized_clan = _normalize_clan_tag(clan_tag)
    player_tag = _normalize_player_tag(tag)
    if last_wars is not None and last_wars not in _WAR_LEADERBOARD_LAST_WARS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_last_wars",
                "hint": "last_wars must be one of: 5, 10, 15, or omitted for all wars",
            },
        )
    _assert_tracked_clan(db, normalized_clan)

    logger.debug(
        "war player history",
        extra={
            "event": "api.wars.player_history",
            "clan_tag": normalized_clan,
            "player_tag": player_tag,
            "last_wars": last_wars,
        },
    )

    rpc_hist: dict[str, Any] = {
        "p_clan_tag": normalized_clan,
        "p_player_tag": player_tag,
    }
    if last_wars is not None:
        rpc_hist["p_max_wars"] = last_wars
    resp = db.rpc("war_player_attack_history", rpc_hist).execute()
    raw = resp.data or []
    rows = [_coerce_rpc_row(dict(r)) for r in raw]

    def _strip_kind(row: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k != "kind"}

    offenses = [_strip_kind(r) for r in rows if r.get("kind") == "offense"]
    defenses = [_strip_kind(r) for r in rows if r.get("kind") == "defense"]
    return {
        "player_tag": player_tag,
        "clan_tag": normalized_clan,
        "last_wars": last_wars,
        "offenses": offenses,
        "defenses": defenses,
    }


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
