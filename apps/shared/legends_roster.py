"""Legends League daily roster: who appears on the leaderboard and is ingested for battle logs."""

from __future__ import annotations

# Canonical CoC main-village league label (source of truth for roster + ingestion).
_LEGEND_LEAGUE_NAME = "Legend League"
# Some payloads or copies may include a trailing period.
_LEGEND_LEAGUE_NAME_WITH_PERIOD = "Legend League."


def league_name_is_legends(league_name: str | None) -> bool:
    """True only when the stored name is Legend League (optional trailing period, case-insensitive)."""
    if not league_name:
        return False
    s = league_name.strip()
    if s.endswith("."):
        s = s[:-1].strip()
    return s.casefold() == _LEGEND_LEAGUE_NAME.casefold()


def fetch_legends_roster_tags(db) -> list[str]:
    """Tags for the Legends day table and `ingest_legends` battle polling.

    Source of truth: `players.league_name` equals Legend League (see league_name_is_legends).
    """
    r = (
        db.table("players")
        .select("tag")
        .in_("league_name", [_LEGEND_LEAGUE_NAME, _LEGEND_LEAGUE_NAME_WITH_PERIOD])
        .execute()
    )
    roster = {row["tag"] for row in (r.data or []) if row.get("tag")}
    return sorted(roster)


def is_always_tracked_legends_roster_player(db, tag: str) -> bool:
    """True if always-tracked and their `players` row is Legend League by name."""
    r = db.table("tracked_players").select("player_tag").eq("player_tag", tag).limit(1).execute()
    if not (r.data or []):
        return False
    pl = db.table("players").select("league_name").eq("tag", tag).limit(1).execute()
    row = (pl.data or [None])[0]
    return bool(row and league_name_is_legends(row.get("league_name")))
