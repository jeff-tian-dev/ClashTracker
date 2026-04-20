import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from shared.legends_roster import (
    current_legends_day as _current_legends_day,
    fetch_legends_roster_tags,
    is_always_tracked_legends_roster_player,
    legends_season_start,
)

from ..database import get_db

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# Dedup-only archive dates (e.g. rows moved off the live day) — omit from player day picker.
_HIDDEN_FROM_LEGENDS_DAY_PICKER: frozenset[str] = frozenset({"2026-03-22"})

# PostgREST default response cap is 1000 rows per request — match it so our exit condition
# (`len(chunk) < page`) correctly distinguishes "final partial page" from "PostgREST truncated us".
_LEGENDS_DAYS_PAGE = 1000
_LEGENDS_BATTLES_PAGE = 1000

# Players who left every tracked clan more than this long ago are hidden from the Legends
# leaderboard entirely. Always-tracked pins (July roster / external) are exempt.
_LEGENDS_HIDE_AFTER_LEFT = timedelta(days=3)


# _current_legends_day is imported from shared.legends_roster


def _legends_empty_totals() -> dict:
    return {
        "attack_total": 0,
        "defense_total": 0,
        "attack_battle_count": 0,
        "defense_battle_count": 0,
    }


def _aggregate_legends_day_battles(
    battles: list[dict],
    legends_roster_tags: list[str],
) -> tuple[dict[str, dict], set[str]]:
    """Per-player trophy totals and battle counts for one legends day (plus roster placeholders)."""
    tags_with_battles: set[str] = set()
    agg: dict[str, dict] = {}
    for b in battles:
        tag = b["player_tag"]
        tags_with_battles.add(tag)
        if tag not in agg:
            agg[tag] = _legends_empty_totals()
        if b["is_attack"]:
            agg[tag]["attack_total"] += b["trophies"]
            agg[tag]["attack_battle_count"] += 1
        else:
            agg[tag]["defense_total"] += b["trophies"]
            agg[tag]["defense_battle_count"] += 1

    for tag in legends_roster_tags:
        if tag not in agg:
            agg[tag] = _legends_empty_totals()

    return agg, tags_with_battles


def _parse_legends_day_param(
    legends_day: str | None,
    *,
    enforce_season_start: bool,
) -> tuple[str, bool]:
    """Validate legends_day query param; return (chosen_day_iso, is_current).

    Raises HTTPException 400 for invalid format or (when enforce_season_start) out-of-season,
    404 for hidden archive days.
    """
    current_str = _current_legends_day().isoformat()
    if legends_day is None:
        return current_str, True
    try:
        chosen_date = date.fromisoformat(legends_day)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_legends_day", "message": "legends_day must be YYYY-MM-DD"},
        )
    chosen = chosen_date.isoformat()
    if chosen in _HIDDEN_FROM_LEGENDS_DAY_PICKER:
        raise HTTPException(
            status_code=404,
            detail={"error": "legends_day_hidden", "message": "This legends day is not available."},
        )
    if enforce_season_start and chosen_date < legends_season_start():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "out_of_season",
                "message": f"legends_day must be on or after {legends_season_start().isoformat()}",
            },
        )
    return chosen, chosen == current_str


def _fetch_legends_battles_for_day(
    db,
    legends_day: str,
    *,
    exclude_tags: set[str] | None = None,
) -> list[dict]:
    """Page through `legends_battles` for one day, optionally excluding stale tags.

    PostgREST caps a single request at ~1000 rows, but one legends day can exceed that
    (82-player roster × up to 16 rows/player ≈ 1,300). Ordering by `id` guarantees no
    duplicates or gaps across pages.

    `exclude_tags` drops stale-leaver rows at the DB boundary so the fetch stays small
    — see `_fetch_stale_leaver_tags`.
    """
    exclude = list(exclude_tags) if exclude_tags else []
    rows: list[dict] = []
    off = 0
    while True:
        q = (
            db.table("legends_battles")
            .select("player_tag, is_attack, trophies")
            .eq("legends_day", legends_day)
        )
        if exclude:
            q = q.not_.in_("player_tag", exclude)
        q = q.order("id").range(off, off + _LEGENDS_BATTLES_PAGE - 1)
        r = q.execute()
        chunk = r.data or []
        rows.extend(chunk)
        if len(chunk) < _LEGENDS_BATTLES_PAGE:
            break
        off += _LEGENDS_BATTLES_PAGE
    return rows


def _fetch_stale_leaver_tags(db, always_tracked_tags: set[str], *, now: datetime) -> set[str]:
    """Tags to exclude from the Legends leaderboard entirely.

    A "stale leaver" is a player whose `left_tracked_roster_at` is set to more than
    `_LEGENDS_HIDE_AFTER_LEFT` ago AND who is not on the always-tracked pin list.

    Uses an `lt` filter on the indexed timestamp column; excluding these tags upstream
    shaves the `legends_battles` fetch size (today's roster is ~60% ex-members of
    tracked clans who remain in Legend League and thus still ingested).
    """
    cutoff_iso = (now - _LEGENDS_HIDE_AFTER_LEFT).isoformat()
    resp = (
        db.table("players")
        .select("tag")
        .lt("left_tracked_roster_at", cutoff_iso)
        .execute()
    )
    candidate_tags = {row["tag"] for row in (resp.data or []) if row.get("tag")}
    return candidate_tags - always_tracked_tags


def _parse_iso_timestamp(value: object) -> datetime | None:
    """Best-effort parse of Supabase `timestamptz` strings; returns None if unparseable."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_stale_left_roster(left_at: object, *, now: datetime) -> bool:
    """True when the player left all tracked clans more than `_LEGENDS_HIDE_AFTER_LEFT` ago."""
    dt = _parse_iso_timestamp(left_at)
    if dt is None:
        return False
    return (now - dt) > _LEGENDS_HIDE_AFTER_LEFT


def _fetch_distinct_legends_days_since(db, since_iso: str) -> set[str]:
    """Paginated scan of legends_battles.legends_day column (distinct via Python set)."""
    days: set[str] = set()
    off = 0
    while True:
        r = (
            db.table("legends_battles")
            .select("legends_day")
            .gte("legends_day", since_iso)
            .range(off, off + _LEGENDS_DAYS_PAGE - 1)
            .execute()
        )
        chunk = r.data or []
        for row in chunk:
            d = row.get("legends_day")
            if d:
                days.add(d)
        if len(chunk) < _LEGENDS_DAYS_PAGE:
            break
        off += _LEGENDS_DAYS_PAGE
    return days


@router.get("/legends")
def legends_leaderboard(
    legends_day: str | None = Query(default=None, description="YYYY-MM-DD; omit for current legends day"),
):
    chosen_day, is_current_day = _parse_legends_day_param(legends_day, enforce_season_start=True)
    db = get_db()

    logger.debug(
        "legends leaderboard",
        extra={"event": "api.db.query", "table": "legends_battles", "legends_day": chosen_day},
    )

    tracked_rows = (
        db.table("tracked_players").select("player_tag,tracking_group,legends_bracket").execute().data or []
    )
    always_tracked_tags = {row["player_tag"] for row in tracked_rows}

    # Compute the stale-leaver set once and apply it to every downstream fetch: excluding
    # them at the DB boundary keeps today's `legends_battles` fetch well under the
    # PostgREST page cap (~60% of today's battle writers have already left tracked clans
    # but remain in Legend League, so they're still ingested).
    stale_leaver_tags = _fetch_stale_leaver_tags(
        db, always_tracked_tags, now=datetime.now(timezone.utc)
    )

    battles = _fetch_legends_battles_for_day(db, chosen_day, exclude_tags=stale_leaver_tags)

    if is_current_day:
        roster_tags = [t for t in fetch_legends_roster_tags(db) if t not in stale_leaver_tags]
        if not roster_tags and battles:
            logger.warning(
                "legends_leaderboard: roster query returned 0 Legend League players but battles exist "
                "for legends_day=%s — leaderboard will only list attackers/defenders; check league_name "
                "casing/spacing, Supabase data, and that apps/shared is deployed on the API host.",
                chosen_day,
            )
    else:
        # Historical day: roster = (tags with battles that day) UNION (currently tracked players).
        # Battle tags are added by _aggregate_legends_day_battles; pad with tracked tags so always-tracked
        # pins still appear as zero-battle rows (greyed client-side).
        roster_tags = sorted(always_tracked_tags)

    agg, tags_with_battles = _aggregate_legends_day_battles(battles, roster_tags)

    if not agg:
        return {"data": [], "legends_day": chosen_day}

    tag_to_tracking_group = {
        row["player_tag"]: (row.get("tracking_group") or "clan_july") for row in tracked_rows
    }
    tag_to_legends_bracket: dict[str, int] = {}
    for row in tracked_rows:
        lb = row.get("legends_bracket")
        tag_to_legends_bracket[row["player_tag"]] = 1 if lb not in (1, 2) else int(lb)

    player_tags = list(agg.keys())
    player_map: dict = {}
    _chunk = 100
    for i in range(0, len(player_tags), _chunk):
        batch = player_tags[i : i + _chunk]
        player_resp = (
            db.table("players")
            .select("tag, name, trophies, left_tracked_roster_at")
            .in_("tag", batch)
            .execute()
        )
        for p in player_resp.data or []:
            player_map[p["tag"]] = p

    # For past days, use the frozen end-of-day trophy snapshot (migration 021) so
    # final_trophies reflects what the player had when the day ended — not their live
    # trophies today. Past days without a snapshot (predate the feature) return null
    # for both initial_trophies and final_trophies; the UI renders them as "Unknown".
    # Current day: keep using live `players.trophies` (the day isn't over so its
    # final is inherently "latest observed").
    snapshot_map: dict[str, int] = {}
    if not is_current_day and player_tags:
        for i in range(0, len(player_tags), _chunk):
            batch = player_tags[i : i + _chunk]
            snap_resp = (
                db.table("legends_day_snapshots")
                .select("player_tag, trophies")
                .eq("legends_day", chosen_day)
                .in_("player_tag", batch)
                .execute()
            )
            for row in snap_resp.data or []:
                snapshot_map[row["player_tag"]] = int(row["trophies"])

    rows = []
    for tag, totals in agg.items():
        player = player_map.get(tag, {})
        net = totals["attack_total"] - totals["defense_total"]
        if is_current_day:
            final_trophies: int | None = player.get("trophies", 0)
        elif tag in snapshot_map:
            final_trophies = snapshot_map[tag]
        else:
            final_trophies = None
        initial_trophies = None if final_trophies is None else final_trophies - net
        rows.append({
            "player_tag": tag,
            "name": player.get("name", tag),
            "attack_total": totals["attack_total"],
            "defense_total": totals["defense_total"],
            "attack_battle_count": totals["attack_battle_count"],
            "defense_battle_count": totals["defense_battle_count"],
            "net": net,
            "initial_trophies": initial_trophies,
            "final_trophies": final_trophies,
            "has_battles": tag in tags_with_battles,
            "is_always_tracked": tag in always_tracked_tags,
            "tracking_group": tag_to_tracking_group.get(tag) if tag in always_tracked_tags else None,
            "legends_bracket": tag_to_legends_bracket.get(tag) if tag in always_tracked_tags else None,
            "left_tracked_roster_at": player.get("left_tracked_roster_at"),
        })

    # Drop rows for players who have been off every tracked clan roster for >3 days.
    # Always-tracked pins (July / external) are exempt — they're pinned by admin intent.
    now = datetime.now(timezone.utc)
    rows = [
        r for r in rows
        if r["is_always_tracked"]
        or not _is_stale_left_roster(r["left_tracked_roster_at"], now=now)
    ]

    # Sort rows with known trophies first (descending), then unknown-trophy rows by net.
    def _sort_key(r: dict) -> tuple:
        has_trophies = r["final_trophies"] is not None
        # has_trophies=False should sort AFTER has_trophies=True: invert boolean via `not`.
        return (not has_trophies, -(r["final_trophies"] or 0), -r["net"])

    rows.sort(key=_sort_key)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    return {"data": rows, "legends_day": chosen_day}


# NOTE: route ordering matters — declare `/legends/days` BEFORE `/legends/{tag:path}`
# so the greedy path param doesn't swallow it.
@router.get("/legends/days")
def legends_days_in_season():
    """Distinct legends_day values in the current season (newest first), for the leaderboard picker."""
    db = get_db()
    season_start_iso = legends_season_start().isoformat()
    days = _fetch_distinct_legends_days_since(db, season_start_iso)
    days = {d for d in days if d not in _HIDDEN_FROM_LEGENDS_DAY_PICKER}
    current = _current_legends_day().isoformat()
    if current not in _HIDDEN_FROM_LEGENDS_DAY_PICKER:
        days.add(current)
    return {"legends_days": sorted(days, reverse=True)}


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
    chosen, is_current_legends_day = _parse_legends_day_param(legends_day, enforce_season_start=False)

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
        .order("first_seen_at", desc=False)
        .execute()
    )
    battles = resp.data or []

    player_resp = db.table("players").select("tag, name, trophies").eq("tag", tag).execute()
    player = (player_resp.data or [None])[0]
    if not player:
        raise HTTPException(status_code=404, detail={"error": "not_found", "resource": "player", "identifier": tag})

    attacks = [b for b in battles if b["is_attack"]]
    defenses = [b for b in battles if not b["is_attack"]]

    # For past days, prefer the end-of-day snapshot so the header reflects the day
    # being viewed rather than the player's live trophies today. When no snapshot
    # exists (past days predating migration 021), return None so the UI can display
    # "Unknown" instead of misleading live trophies.
    display_trophies: int | None = player["trophies"]
    if not is_current_legends_day:
        snap_resp = (
            db.table("legends_day_snapshots")
            .select("trophies")
            .eq("player_tag", tag)
            .eq("legends_day", chosen)
            .limit(1)
            .execute()
        )
        snap_rows = snap_resp.data or []
        display_trophies = int(snap_rows[0]["trophies"]) if snap_rows else None

    return {
        "player_tag": tag,
        "player_name": player["name"],
        "current_trophies": display_trophies,
        "legends_day": chosen,
        "is_current_legends_day": is_current_legends_day,
        "attacks": attacks,
        "defenses": defenses,
    }
