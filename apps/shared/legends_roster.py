"""Legends League daily roster and shared calendar helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

# Canonical CoC main-village league label (source of truth for roster + ingestion).
_LEGEND_LEAGUE_NAME = "Legend League"
# Some payloads or copies may include a trailing period.
_LEGEND_LEAGUE_NAME_WITH_PERIOD = "Legend League."

# PostgREST default max rows per request; page to avoid truncation.
_ROSTER_PAGE = 1000


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

    Source of truth: `players.league_name` is Legend League (see league_name_is_legends).

    Uses a broad ILIKE prefilter plus strict Python check: plain `.in_(league_name, ...)` is
    case-sensitive in Postgres (often 0 rows); exact ILIKE misses padded strings. Paginates so
    PostgREST never truncates the roster at the default row limit.
    """
    roster: set[str] = set()
    off = 0
    while True:
        r = (
            db.table("players")
            .select("tag", "league_name")
            .ilike("league_name", "%Legend League%")
            .range(off, off + _ROSTER_PAGE - 1)
            .execute()
        )
        chunk = r.data or []
        for row in chunk:
            tag = row.get("tag")
            if tag and league_name_is_legends(row.get("league_name")):
                roster.add(tag)
        if len(chunk) < _ROSTER_PAGE:
            break
        off += _ROSTER_PAGE
    return sorted(roster)


def is_always_tracked_legends_roster_player(db, tag: str) -> bool:
    """True if always-tracked and their `players` row is Legend League by name."""
    r = db.table("tracked_players").select("player_tag").eq("player_tag", tag).limit(1).execute()
    if not (r.data or []):
        return False
    pl = db.table("players").select("league_name").eq("tag", tag).limit(1).execute()
    row = (pl.data or [None])[0]
    return bool(row and league_name_is_legends(row.get("league_name")))


# ── Legends day calendar ──────────────────────────────────────────────

_LEGENDS_RESET_HOUR_UTC = 5  # 1 AM EST = 5 AM UTC


def current_legends_day() -> date:
    """Return the date representing the current legends day.

    The legends day resets at 5:00 AM UTC (1 AM EST).  Before that hour
    the "current" day is still the previous calendar date.
    """
    now = datetime.now(timezone.utc)
    if now.time() < time(_LEGENDS_RESET_HOUR_UTC):
        return (now - timedelta(days=1)).date()
    return now.date()

