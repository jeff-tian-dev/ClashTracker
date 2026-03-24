"""Legends League daily roster: who appears on the leaderboard and is ingested for battle logs."""

from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta

# PostgREST URL length / param limits — chunk tracked tag lookups.
_TRACKED_PLAYERS_IN_CHUNK = 100

# Include anyone with stored battles in this legends-day window (stale/null league_name fallback).
RECENT_LEGENDS_ROSTER_LOOKBACK_DAYS = 14

# Main-village Legend League starts at 5000 trophies (CoC). Catches players when `league_name`
# is null, non-English, or not synced while trophies are current.
LEGEND_LEAGUE_MIN_TROPHIES = 5000

_PLAYERS_PAGE = 1000

_LEGENDS_RESET_HOUR_UTC = 5


def _current_legends_day() -> date:
    now = datetime.now(timezone.utc)
    if now.time() < time(_LEGENDS_RESET_HOUR_UTC):
        return (now - timedelta(days=1)).date()
    return now.date()


def league_name_is_legends(league_name: str | None) -> bool:
    return "legend" in (league_name or "").lower()


def fetch_legends_roster_tags(db) -> list[str]:
    """Tags for the Legends day table and `ingest_legends` battle polling.

    Includes:
    - Every `players` row whose league name indicates Legends League.
    - Every `players` row with trophies >= LEGEND_LEAGUE_MIN_TROPHIES (main-village Legend floor).
    - Every `tracked_players` tag whose `players` profile indicates Legends League.
    - Every `player_tag` with a `legends_battles` row in the last RECENT_LEGENDS_ROSTER_LOOKBACK_DAYS
      calendar days of legends_day (covers stale or null `league_name` while still tied to Legends data).
    """
    roster: set[str] = set()

    r1 = db.table("players").select("tag").ilike("league_name", "%legend%").execute()
    roster.update(row["tag"] for row in (r1.data or []) if row.get("tag"))

    off = 0
    while True:
        r_trophy = (
            db.table("players")
            .select("tag")
            .gte("trophies", LEGEND_LEAGUE_MIN_TROPHIES)
            .range(off, off + _PLAYERS_PAGE - 1)
            .execute()
        )
        chunk = r_trophy.data or []
        roster.update(row["tag"] for row in chunk if row.get("tag"))
        if len(chunk) < _PLAYERS_PAGE:
            break
        off += _PLAYERS_PAGE

    r2 = db.table("tracked_players").select("player_tag").execute()
    tracked = [row["player_tag"] for row in (r2.data or []) if row.get("player_tag")]
    for i in range(0, len(tracked), _TRACKED_PLAYERS_IN_CHUNK):
        chunk = tracked[i : i + _TRACKED_PLAYERS_IN_CHUNK]
        r3 = db.table("players").select("tag, league_name").in_("tag", chunk).execute()
        for row in r3.data or []:
            if league_name_is_legends(row.get("league_name")) and row.get("tag"):
                roster.add(row["tag"])

    cutoff = (_current_legends_day() - timedelta(days=RECENT_LEGENDS_ROSTER_LOOKBACK_DAYS)).isoformat()
    _page = 1000
    _off = 0
    while True:
        rb = (
            db.table("legends_battles")
            .select("player_tag")
            .gte("legends_day", cutoff)
            .range(_off, _off + _page - 1)
            .execute()
        )
        chunk = rb.data or []
        roster.update(row["player_tag"] for row in chunk if row.get("player_tag"))
        if len(chunk) < _page:
            break
        _off += _page

    return sorted(roster)


def is_always_tracked_legends_roster_player(db, tag: str) -> bool:
    """True if always-tracked and (Legends by name, trophies floor, or recent legends_battles)."""
    r = db.table("tracked_players").select("player_tag").eq("player_tag", tag).limit(1).execute()
    if not (r.data or []):
        return False

    pl = db.table("players").select("league_name, trophies").eq("tag", tag).limit(1).execute()
    row = (pl.data or [None])[0]
    if row:
        if league_name_is_legends(row.get("league_name")):
            return True
        try:
            if int(row.get("trophies") or 0) >= LEGEND_LEAGUE_MIN_TROPHIES:
                return True
        except (TypeError, ValueError):
            pass

    cutoff = (_current_legends_day() - timedelta(days=RECENT_LEGENDS_ROSTER_LOOKBACK_DAYS)).isoformat()
    lb = (
        db.table("legends_battles")
        .select("id")
        .eq("player_tag", tag)
        .gte("legends_day", cutoff)
        .limit(1)
        .execute()
    )
    return bool(lb.data)
