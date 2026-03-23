import logging
from datetime import date, datetime, time, timezone, timedelta

from fastapi import APIRouter, HTTPException

from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

_LEGENDS_RESET_HOUR_UTC = 5


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

    resp = (
        db.table("legends_battles")
        .select("player_tag, is_attack, trophies")
        .eq("legends_day", legends_day)
        .execute()
    )
    battles = resp.data or []

    agg: dict[str, dict] = {}
    for b in battles:
        tag = b["player_tag"]
        if tag not in agg:
            agg[tag] = {"attack_total": 0, "defense_total": 0}
        if b["is_attack"]:
            agg[tag]["attack_total"] += b["trophies"]
        else:
            agg[tag]["defense_total"] += b["trophies"]

    if not agg:
        return {"data": [], "legends_day": legends_day}

    player_tags = list(agg.keys())
    player_resp = (
        db.table("players")
        .select("tag, name, trophies")
        .in_("tag", player_tags)
        .execute()
    )
    player_map = {p["tag"]: p for p in (player_resp.data or [])}

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
        })

    rows.sort(key=lambda r: r["net"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    return {"data": rows, "legends_day": legends_day}


@router.get("/legends/{tag:path}")
def legends_player_detail(tag: str):
    db = get_db()
    legends_day = _current_legends_day().isoformat()

    logger.debug(
        "legends player detail",
        extra={"event": "api.db.query", "table": "legends_battles", "player_tag": tag},
    )

    resp = (
        db.table("legends_battles")
        .select("*")
        .eq("player_tag", tag)
        .eq("legends_day", legends_day)
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
        "legends_day": legends_day,
        "attacks": attacks,
        "defenses": defenses,
    }
