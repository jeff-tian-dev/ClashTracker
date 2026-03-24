"""Legends League daily roster: who appears on the leaderboard and is ingested for battle logs."""

from __future__ import annotations

# PostgREST URL length / param limits — chunk tracked tag lookups.
_TRACKED_PLAYERS_IN_CHUNK = 100


def league_name_is_legends(league_name: str | None) -> bool:
    return "legend" in (league_name or "").lower()


def fetch_legends_roster_tags(db) -> list[str]:
    """Tags for the Legends day table and `ingest_legends` battle polling.

    Includes:
    - Every `players` row whose league name indicates Legends League.
    - Every `tracked_players` tag whose `players` profile indicates Legends League (explicit merge
      so always-tracked accounts are never omitted from the roster path even if queries diverge).
    """
    roster: set[str] = set()

    r1 = db.table("players").select("tag").ilike("league_name", "%legend%").execute()
    roster.update(row["tag"] for row in (r1.data or []) if row.get("tag"))

    r2 = db.table("tracked_players").select("player_tag").execute()
    tracked = [row["player_tag"] for row in (r2.data or []) if row.get("player_tag")]
    for i in range(0, len(tracked), _TRACKED_PLAYERS_IN_CHUNK):
        chunk = tracked[i : i + _TRACKED_PLAYERS_IN_CHUNK]
        r3 = db.table("players").select("tag, league_name").in_("tag", chunk).execute()
        for row in r3.data or []:
            if league_name_is_legends(row.get("league_name")) and row.get("tag"):
                roster.add(row["tag"])

    return sorted(roster)


def is_always_tracked_legends_roster_player(db, tag: str) -> bool:
    """True if `tag` is on `tracked_players` and their stored profile indicates Legends League."""
    r = db.table("tracked_players").select("player_tag").eq("player_tag", tag).limit(1).execute()
    if not (r.data or []):
        return False
    pl = db.table("players").select("league_name").eq("tag", tag).limit(1).execute()
    row = (pl.data or [None])[0]
    if not row:
        return False
    return league_name_is_legends(row.get("league_name"))
