import logging
from datetime import date, datetime, time, timezone, timedelta

from fastapi import APIRouter, HTTPException, Query

from shared.legends_roster import fetch_legends_roster_tags, is_always_tracked_legends_roster_player

from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

_LEGENDS_RESET_HOUR_UTC = 5

# Dedup-only archive dates (e.g. rows moved off the live day) — omit from player day picker.
_HIDDEN_FROM_LEGENDS_DAY_PICKER: frozenset[str] = frozenset({"2026-03-22"})


def _current_legends_day() -> date:
    now = datetime.now(timezone.utc)
    if now.time() < time(_LEGENDS_RESET_HOUR_UTC):
        return (now - timedelta(days=1)).date()
    return now.date()


@router.get("/legends")
def legends_leaderboard():
    db = get_db()
    legends_day = _current_legends_day().isoformat()

    logger.debug(
        "legends leaderboard",
        extra={"event": "api.db.query", "table": "legends_battles", "legends_day": legends_day},
    )

    legends_roster_tags = fetch_legends_roster_tags(db)

    resp = (
        db.table("legends_battles")
        .select("player_tag, is_attack, trophies")
        .eq("legends_day", legends_day)
        .execute()
    )
    battles = resp.data or []

    tags_with_battles: set[str] = set()
    agg: dict[str, dict] = {}
    for b in battles:
        tag = b["player_tag"]
        tags_with_battles.add(tag)
        if tag not in agg:
            agg[tag] = {"attack_total": 0, "defense_total": 0}
        if b["is_attack"]:
            agg[tag]["attack_total"] += b["trophies"]
        else:
            agg[tag]["defense_total"] += b["trophies"]

    for tag in legends_roster_tags:
        if tag not in agg:
            agg[tag] = {"attack_total": 0, "defense_total": 0}

    if not agg:
        return {"data": [], "legends_day": legends_day}

    player_tags = list(agg.keys())
    player_map: dict = {}
    _chunk = 100
    for i in range(0, len(player_tags), _chunk):
        batch = player_tags[i : i + _chunk]
        player_resp = (
            db.table("players")
            .select("tag, name, trophies")
            .in_("tag", batch)
            .execute()
        )
        for p in player_resp.data or []:
            player_map[p["tag"]] = p

    rows = []
    for tag, totals in agg.items():
        player = player_map.get(tag, {})
        net = totals["attack_total"] - totals["defense_total"]
        current_trophies = player.get("trophies", 0)
        rows.append({
            "player_tag": tag,
            "name": player.get("name", tag),
            "attack_total": totals["attack_total"],
            "defense_total": totals["defense_total"],
            "net": net,
            "initial_trophies": current_trophies - net,
            "final_trophies": current_trophies,
            "has_battles": tag in tags_with_battles,
        })

    rows.sort(key=lambda r: r["net"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    return {"data": rows, "legends_day": legends_day}


@router.get("/legends/{tag}/days")
def legends_player_days(tag: str):
    """Distinct legends_day values for this player (newest first)."""
    db = get_db()
    resp = (
        db.table("legends_battles")
        .select("legends_day")
        .eq("player_tag", tag)
        .execute()
    )
    days = sorted({r["legends_day"] for r in (resp.data or [])}, reverse=True)
    days = [d for d in days if d not in _HIDDEN_FROM_LEGENDS_DAY_PICKER]
    current = _current_legends_day().isoformat()
    if (
        current not in _HIDDEN_FROM_LEGENDS_DAY_PICKER
        and is_always_tracked_legends_roster_player(db, tag)
        and current not in days
    ):
        days = sorted([current, *days], reverse=True)
    return {"legends_days": days}


@router.get("/legends/{tag:path}")
def legends_player_detail(
    tag: str,
    legends_day: str | None = Query(default=None, description="YYYY-MM-DD; omit for current legends day"),
):
    db = get_db()
    current_str = _current_legends_day().isoformat()
    if legends_day is None:
        chosen = current_str
    else:
        try:
            chosen = date.fromisoformat(legends_day).isoformat()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_legends_day", "message": "legends_day must be YYYY-MM-DD"},
            )

    if chosen in _HIDDEN_FROM_LEGENDS_DAY_PICKER:
        raise HTTPException(
            status_code=404,
            detail={"error": "legends_day_hidden", "message": "This legends day is not available."},
        )

    is_current_legends_day = chosen == current_str

    logger.debug(
        "legends player detail",
        extra={
            "event": "api.db.query",
            "table": "legends_battles",
            "player_tag": tag,
            "legends_day": chosen,
        },
    )

    resp = (
        db.table("legends_battles")
        .select("*")
        .eq("player_tag", tag)
        .eq("legends_day", chosen)
        .order("first_seen_at", desc=True)
        .execute()
    )
    battles = resp.data or []

    player_resp = db.table("players").select("tag, name, trophies").eq("tag", tag).execute()
    player = (player_resp.data or [None])[0]
    if not player:
        raise HTTPException(status_code=404, detail={"error": "not_found", "resource": "player", "identifier": tag})

    attacks = [b for b in battles if b["is_attack"]]
    defenses = [b for b in battles if not b["is_attack"]]

    return {
        "player_tag": tag,
        "player_name": player["name"],
        "current_trophies": player["trophies"],
        "legends_day": chosen,
        "is_current_legends_day": is_current_legends_day,
        "attacks": attacks,
        "defenses": defenses,
    }
