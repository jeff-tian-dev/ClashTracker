import logging

from fastapi import APIRouter, HTTPException
from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/dashboard")
def dashboard_summary():
    db = get_db()
    logger.debug("dashboard summary", extra={"event": "api.db.query", "scope": "dashboard"})

    clans = db.table("clans").select("*", count="exact").execute()
    players = db.table("players").select("*", count="exact").execute()
    wars = db.table("wars").select("*", count="exact").execute()
    active_wars = db.table("wars").select("*", count="exact").in_("state", ["preparation", "inWar"]).execute()
    raids = db.table("capital_raids").select("*", count="exact").execute()

    recent_wars = (
        db.table("wars")
        .select("id, clan_tag, opponent_name, state, result, start_time, clan_stars, opponent_stars")
        .order("start_time", desc=True)
        .limit(5)
        .execute()
    )
    recent_raids = (
        db.table("capital_raids")
        .select("id, clan_tag, state, start_time, capital_total_loot, raids_completed")
        .order("start_time", desc=True)
        .limit(5)
        .execute()
    )

    for label, payload in (
        ("recent_wars", recent_wars.data),
        ("recent_raids", recent_raids.data),
    ):
        if payload is None:
            logger.error(
                "dashboard invariant: list field is None",
                extra={"event": "api.invariant.violation", "field": label},
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "invariant_violation",
                    "field": label,
                    "hint": "Expected a list from Supabase select; got None. Check DB connectivity and RLS.",
                },
            )
        if not isinstance(payload, list):
            logger.error(
                "dashboard invariant: list field wrong type",
                extra={
                    "event": "api.invariant.violation",
                    "field": label,
                    "got_type": type(payload).__name__,
                },
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "invariant_violation",
                    "field": label,
                    "hint": f"Expected list from database; got {type(payload).__name__}.",
                },
            )

    return {
        "total_clans": clans.count or 0,
        "total_players": players.count or 0,
        "total_wars": wars.count or 0,
        "active_wars": active_wars.count or 0,
        "total_raids": raids.count or 0,
        "recent_wars": recent_wars.data,
        "recent_raids": recent_raids.data,
    }
