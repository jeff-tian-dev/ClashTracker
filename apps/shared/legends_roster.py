"""Legends League daily roster and shared calendar helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

# Canonical CoC main-village league label (all three tiers share this name).
_LEGEND_LEAGUE_NAME = "Legend League"

# Supercell leagueTier.id values (name is always "Legend League" for each).
LEGEND_LEAGUE_TIER_ID_TO_NUMBER: dict[int, int] = {
    105000036: 1,  # Legend League 1 (highest)
    105000035: 2,
    105000034: 3,
}
LEGEND_LEAGUE_TIER_IDS: frozenset[int] = frozenset(LEGEND_LEAGUE_TIER_ID_TO_NUMBER.keys())
LEGEND_LEAGUE_1_TIER_ID = 105000036

# PostgREST default max rows per request; page to avoid truncation.
_ROSTER_PAGE = 1000


def league_name_is_legends(league_name: str | None) -> bool:
    """True when the stored name is Legend League (optional tier suffix or trailing period)."""
    if not league_name:
        return False
    s = league_name.strip()
    if s.endswith("."):
        s = s[:-1].strip()
    lower = s.casefold()
    if lower == _LEGEND_LEAGUE_NAME.casefold():
        return True
    prefix = f"{_LEGEND_LEAGUE_NAME} "
    if lower.startswith(prefix.casefold()):
        suffix = s[len(prefix) :].strip()
        return suffix.isdigit() and 1 <= int(suffix) <= 3
    return False


def legend_league_tier_number(league_tier_id: int | None) -> int | None:
    """Map CoC leagueTier.id to tier number 1 (highest) … 3, or None."""
    if league_tier_id is None:
        return None
    try:
        return LEGEND_LEAGUE_TIER_ID_TO_NUMBER.get(int(league_tier_id))
    except (TypeError, ValueError):
        return None


def player_in_legend_league(row: dict) -> bool:
    """True when a player row is in any Legend League tier (1–3)."""
    if legend_league_tier_number(row.get("league_tier_id")) is not None:
        return True
    return league_name_is_legends(row.get("league_name"))


def player_in_legends_tab(row: dict) -> bool:
    """True when the player belongs on the Legends tab (Legend League 1 only)."""
    tier_num = legend_league_tier_number(row.get("league_tier_id"))
    if tier_num is not None:
        return tier_num == 1
    league_name = row.get("league_name")
    if not league_name:
        return False
    s = league_name.strip()
    if s.endswith("."):
        s = s[:-1].strip()
    lower = s.casefold()
    if lower == f"{_LEGEND_LEAGUE_NAME} 1".casefold():
        return True
    # Pre–multi-tier rows: bare "Legend League" treated as tier 1 until re-ingested.
    return lower == _LEGEND_LEAGUE_NAME.casefold()


def legend_league_display_name(
    league_tier_id: int | None,
    league_name: str | None = None,
) -> str | None:
    """Human-readable league label; disambiguates tiers when id is known."""
    tier_num = legend_league_tier_number(league_tier_id)
    if tier_num is not None:
        return f"{_LEGEND_LEAGUE_NAME} {tier_num}"
    if league_name_is_legends(league_name):
        return _LEGEND_LEAGUE_NAME
    return league_name


def fetch_tracked_clan_tags(db) -> set[str]:
    """Clan tags on the admin tracked-clans list."""
    r = db.table("tracked_clans").select("clan_tag").execute()
    return {row["clan_tag"] for row in (r.data or []) if row.get("clan_tag")}


def fetch_tracked_player_tags(db) -> set[str]:
    """Player tags on the admin always-tracked list."""
    r = db.table("tracked_players").select("player_tag").execute()
    return {row["player_tag"] for row in (r.data or []) if row.get("player_tag")}


def player_in_tracked_legends_scope(
    row: dict,
    tracked_clan_tags: set[str],
    tracked_player_tags: set[str],
    *,
    active_tags: set[str] | None = None,
) -> bool:
    """True when a player row belongs to tracked clans and/or always-tracked pins.

    When ``active_tags`` is supplied (ingestion after roster reconcile), that set is the
    source of truth — same membership as player-activity tracking.
    """
    tag = row.get("tag")
    if not tag:
        return False
    if active_tags is not None:
        return tag in active_tags
    if tag in tracked_player_tags:
        return True
    if row.get("left_tracked_roster_at") is not None:
        return False
    clan_tag = row.get("clan_tag")
    return bool(clan_tag and clan_tag in tracked_clan_tags)


def fetch_legends_roster_tags(db, *, active_tags: set[str] | None = None) -> list[str]:
    """Legend League 1 tags on the tracked roster (clan members + always-tracked pins).

    Only tier 1 counts for the Legends tab and battle-log ingestion (see ``player_in_legends_tab``).
    Legend League 2 and 3 are excluded even when tracked.
    Untracked Legend League 1 rows in ``players`` (e.g. ex-members never pinned) are excluded
    from ingestion and from the current-day leaderboard roster.

    Uses a broad ILIKE prefilter plus strict Python check: plain `.in_(league_name, ...)` is
    case-sensitive in Postgres (often 0 rows); exact ILIKE misses padded strings. Paginates so
    PostgREST never truncates the roster at the default row limit.

    Pass ``active_tags`` during ingestion (post-``reconcile_tracked_roster``) to match the
    live tracked membership set without extra DB reads.
    """
    tracked_clan_tags: set[str] = set()
    tracked_player_tags: set[str] = set()
    if active_tags is None:
        tracked_clan_tags = fetch_tracked_clan_tags(db)
        tracked_player_tags = fetch_tracked_player_tags(db)

    roster: set[str] = set()
    off = 0
    while True:
        r = (
            db.table("players")
            .select("tag", "league_name", "league_tier_id", "clan_tag", "left_tracked_roster_at")
            .or_(
                f"league_tier_id.eq.{LEGEND_LEAGUE_1_TIER_ID},"
                "league_name.ilike.*Legend League*"
            )
            .range(off, off + _ROSTER_PAGE - 1)
            .execute()
        )
        chunk = r.data or []
        for row in chunk:
            tag = row.get("tag")
            if not tag or not player_in_legends_tab(row):
                continue
            if player_in_tracked_legends_scope(
                row,
                tracked_clan_tags,
                tracked_player_tags,
                active_tags=active_tags,
            ):
                roster.add(tag)
        if len(chunk) < _ROSTER_PAGE:
            break
        off += _ROSTER_PAGE
    return sorted(roster)


def is_always_tracked_legends_roster_player(db, tag: str) -> bool:
    """True if always-tracked and their `players` row is Legend League 1."""
    r = db.table("tracked_players").select("player_tag").eq("player_tag", tag).limit(1).execute()
    if not (r.data or []):
        return False
    pl = db.table("players").select("league_name,league_tier_id").eq("tag", tag).limit(1).execute()
    row = (pl.data or [None])[0]
    return bool(row and player_in_legends_tab(row))


# ── Legends day calendar ──────────────────────────────────────────────

_LEGENDS_RESET_HOUR_UTC = 5  # 1 AM EST = 5 AM UTC

# Start date (CoC legends-day) of the CURRENT Legends season.
# Legend League tournaments run on a 4-week cycle, normally ending on the last
# Monday of the month at 05:00 UTC. Atypical seasons (e.g. the Apr 2026
# Migration Week for the Legend League rework) shift these dates, so we
# hardcode the start and update it when a new season begins.
# Next scheduled update: 2026-04-20 (new season start).
CURRENT_LEGENDS_SEASON_START: date = date(2026, 3, 23)


def legends_day_containing_utc(when: datetime) -> date:
    """Map a UTC instant to the CoC legends calendar date (reset at 5:00 UTC)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    if when.time() < time(_LEGENDS_RESET_HOUR_UTC):
        return when.date() - timedelta(days=1)
    return when.date()


def current_legends_day() -> date:
    """Return the date representing the current legends day.

    The legends day resets at 5:00 AM UTC (1 AM EST).  Before that hour
    the "current" day is still the previous calendar date.
    """
    return legends_day_containing_utc(datetime.now(timezone.utc))


def legends_season_start() -> date:
    """Return the start date of the current Legends season (inclusive)."""
    return CURRENT_LEGENDS_SEASON_START

