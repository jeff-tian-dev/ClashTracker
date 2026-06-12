import logging
from datetime import datetime, timedelta, timezone

from postgrest import ReturnMethod
from supabase import create_client, Client
from shared.legends_roster import fetch_legends_roster_tags
from shared.player_ingest import (
    player_row_from_coc,
    player_rows_unchanged,
)

from . import db_cache
from . import db_writes
from .config import SUPABASE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

_supabase: Client | None = None


def get_db() -> Client:
    global _supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "ingestion.db.unconfigured: set NEXT_PUBLIC_SUPABASE_URL (or SUPABASE_URL) and "
            "SUPABASE_SERVICE_ROLE_KEY before running ingestion."
        )
    if _supabase is None:
        logger.debug(
            "supabase client created",
            extra={"event": "ingestion.db.client.create"},
        )
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_ingestion_caches() -> None:
    db_cache.reset_ingestion_caches()


def warm_player_compare_cache(tags: set[str]) -> None:
    db_cache.warm_player_compare_cache(get_db(), tags)


def warm_clan_tag_cache() -> None:
    db_cache.warm_clan_tag_cache(get_db())


def warm_legends_snapshot_cache(player_tags: list[str], legends_day: str) -> None:
    db_cache.warm_legends_snapshot_cache(get_db(), player_tags, legends_day)


def _upsert_minimal(table: str, row: dict, *, on_conflict: str) -> None:
    db_writes.upsert_minimal(get_db(), table, row, on_conflict=on_conflict)


def _upsert_minimal_batch(table: str, rows: list[dict], *, on_conflict: str) -> None:
    db_writes.upsert_minimal_batch(get_db(), table, rows, on_conflict=on_conflict)


def _insert_minimal(table: str, row: dict) -> None:
    db_writes.insert_minimal(get_db(), table, row)


def _update_minimal(table: str, values: dict, *, column: str, values_in: list) -> None:
    db_writes.update_minimal(get_db(), table, values, column=column, values_in=values_in)


def get_tracked_clans() -> list[dict]:
    resp = get_db().table("tracked_clans").select("*").execute()
    data = resp.data
    if data is None:
        logger.error(
            "invariant: tracked_clans select returned None",
            extra={"event": "ingestion.invariant.violation", "table": "tracked_clans"},
        )
        return []
    if not isinstance(data, list):
        logger.error(
            "invariant: tracked_clans select returned non-list",
            extra={
                "event": "ingestion.invariant.violation",
                "table": "tracked_clans",
                "got_type": type(data).__name__,
            },
        )
        return []
    return data


def get_tracked_player_tags() -> list[str]:
    """Player tags pinned for ingestion regardless of clan membership."""
    resp = get_db().table("tracked_players").select("player_tag").execute()
    data = resp.data
    if data is None or not isinstance(data, list):
        return []
    return [row["player_tag"] for row in data]


def get_player_tags_for_clan(clan_tag: str) -> set[str]:
    """Last-known member tags stored for this clan (used when clan API fetch fails)."""
    resp = (
        get_db()
        .table("players")
        .select("tag")
        .eq("clan_tag", clan_tag)
        .execute()
    )
    rows = resp.data
    if not rows:
        return set()
    return {r["tag"] for r in rows}


def reconcile_tracked_roster(active_tags: set[str]) -> None:
    """Clear left_tracked_roster_at for active tags; stamp first departure for everyone else still null.

    First detection time after this feature ships — not historical leave dates.
    """
    db = get_db()
    active_list = list(active_tags)
    CHUNK = 200

    if active_list:
        for i in range(0, len(active_list), CHUNK):
            chunk = active_list[i : i + CHUNK]
            _update_minimal("players", {"left_tracked_roster_at": None}, column="tag", values_in=chunk)

    q = get_db().table("players").select("tag").is_("left_tracked_roster_at", None)
    if active_list:
        q = q.not_.in_("tag", active_list)
    resp = q.execute()
    tags_to_mark = [r["tag"] for r in (resp.data or [])]
    now = _now_iso()
    for i in range(0, len(tags_to_mark), CHUNK):
        chunk = tags_to_mark[i : i + CHUNK]
        _update_minimal("players", {"left_tracked_roster_at": now}, column="tag", values_in=chunk)

    if tags_to_mark:
        logger.info(
            "Marked %d player(s) as off tracked roster (first detection)",
            len(tags_to_mark),
            extra={"event": "ingestion.db.reconcile", "marked_count": len(tags_to_mark)},
        )


def clan_row_exists(tag: str) -> bool:
    """True if `clans` has a row for this tag (for players.clan_tag FK)."""
    return db_cache.clan_tag_known(get_db(), tag)


def upsert_clan(clan_data: dict) -> None:
    badge = clan_data.get("badgeUrls", {})
    row = {
        "tag": clan_data["tag"],
        "name": clan_data["name"],
        "description": clan_data.get("description", ""),
        "badge_url": badge.get("large", badge.get("medium", "")),
        "clan_level": clan_data.get("clanLevel", 0),
        "members_count": clan_data.get("members", 0),
        "clan_points": clan_data.get("clanPoints", 0),
        "clan_capital_points": clan_data.get("clanCapitalPoints", 0),
        "war_frequency": clan_data.get("warFrequency", ""),
        "war_win_streak": clan_data.get("warWinStreak", 0),
        "war_wins": clan_data.get("warWins", 0),
        "war_ties": clan_data.get("warTies", 0),
        "war_losses": clan_data.get("warLosses", 0),
        "war_league_id": (clan_data.get("warLeague") or {}).get("id"),
        "capital_league_id": (clan_data.get("capitalLeague") or {}).get("id"),
        "is_war_log_public": clan_data.get("isWarLogPublic", False),
        "updated_at": _now_iso(),
    }
    _upsert_minimal("clans", row, on_conflict="tag")
    db_cache.remember_clan_tag(row["tag"])
    logger.info(
        "Upserted clan",
        extra={"event": "ingestion.db.upsert", "table": "clans", "tag": row["tag"], "clan_name": row["name"]},
    )


def upsert_player(player_data: dict) -> bool:
    """Upsert player when CoC fields changed; return True if a write occurred."""
    clan = player_data.get("clan")
    if isinstance(clan, dict):
        ctag = (clan.get("tag") or "").strip()
        if ctag and not clan_row_exists(ctag):
            upsert_clan(clan)
            logger.info(
                "Ensured clan row from player.clan (stub; not yet ingested via tracked clans)",
                extra={"event": "ingestion.db.clan_stub", "clan_tag": ctag, "player_tag": player_data.get("tag")},
            )

    row = player_row_from_coc(player_data)
    tag = row["tag"]
    db = get_db()
    existing = db_cache.get_player_compare_row(db, tag)
    if player_rows_unchanged(existing, row):
        logger.debug(
            "Skipped unchanged player upsert",
            extra={"event": "ingestion.db.upsert_skip", "table": "players", "tag": tag},
        )
        return False

    row["updated_at"] = _now_iso()
    _upsert_minimal("players", row, on_conflict="tag")
    db_cache.remember_player_compare_row(row)
    logger.debug(
        "Upserted player",
        extra={"event": "ingestion.db.upsert", "table": "players", "tag": tag},
    )
    return True


def parse_coc_timestamp(ts: str | None) -> str | None:
    """Parse CoC API time strings (e.g. battle or war times) into ISO-8601 UTC."""
    return _parse_coc_time(ts)


def _parse_coc_time(ts: str | None) -> str | None:
    """Parse '20240315T123456.000Z' into ISO-8601."""
    if not ts:
        return None
    ts = ts.replace(".", "").replace("Z", "")
    try:
        dt = datetime.strptime(ts, "%Y%m%dT%H%M%S%f")
    except ValueError:
        try:
            dt = datetime.strptime(ts, "%Y%m%dT%H%M%S")
        except ValueError:
            return ts
    return dt.replace(tzinfo=timezone.utc).isoformat()


def upsert_war(war_data: dict, clan_tag: str) -> int | None:
    """Upsert war and return the war id."""
    clan_side = war_data.get("clan", {})
    opponent_side = war_data.get("opponent", {})

    prep_start = _parse_coc_time(war_data.get("preparationStartTime"))
    if not prep_start:
        logger.warning("War for %s has no preparationStartTime, skipping", clan_tag)
        return None

    result = None
    state = war_data.get("state", "")
    if state == "warEnded":
        clan_stars = clan_side.get("stars", 0)
        opp_stars = opponent_side.get("stars", 0)
        if clan_stars > opp_stars:
            result = "win"
        elif clan_stars < opp_stars:
            result = "lose"
        else:
            result = "tie"

    row = {
        "clan_tag": clan_tag,
        "opponent_tag": opponent_side.get("tag", ""),
        "opponent_name": opponent_side.get("name", ""),
        "state": state,
        "team_size": war_data.get("teamSize"),
        "attacks_per_member": war_data.get("attacksPerMember"),
        "preparation_start_time": prep_start,
        "start_time": _parse_coc_time(war_data.get("startTime")),
        "end_time": _parse_coc_time(war_data.get("endTime")),
        "clan_stars": clan_side.get("stars", 0),
        "clan_destruction_pct": clan_side.get("destructionPercentage", 0),
        "opponent_stars": opponent_side.get("stars", 0),
        "opponent_destruction_pct": opponent_side.get("destructionPercentage", 0),
        "result": result,
        "updated_at": _now_iso(),
    }

    resp = get_db().table("wars").upsert(row, on_conflict="clan_tag,preparation_start_time").execute()
    war_id = resp.data[0]["id"] if resp.data else None
    if war_id:
        logger.info("Upserted war id=%d for clan %s (state=%s)", war_id, clan_tag, state)
    return war_id


def resolve_stale_wars(clan_tag: str) -> int:
    """Resolve wars stuck in 'inWar'/'preparation' whose end_time has passed.

    Returns the number of wars resolved.
    """
    now = _now_iso()
    resp = (
        get_db()
        .table("wars")
        .select("id, clan_stars, opponent_stars, clan_destruction_pct, opponent_destruction_pct")
        .eq("clan_tag", clan_tag)
        .in_("state", ["inWar", "preparation"])
        .lt("end_time", now)
        .execute()
    )

    resolved = 0
    for war in resp.data or []:
        clan_stars = war["clan_stars"] or 0
        opp_stars = war["opponent_stars"] or 0
        clan_dest = float(war["clan_destruction_pct"] or 0)
        opp_dest = float(war["opponent_destruction_pct"] or 0)

        if clan_stars > opp_stars:
            result = "win"
        elif clan_stars < opp_stars:
            result = "lose"
        elif clan_dest > opp_dest:
            result = "win"
        elif clan_dest < opp_dest:
            result = "lose"
        else:
            result = "tie"

        get_db().table("wars").update(
            {
                "state": "warEnded",
                "result": result,
                "updated_at": _now_iso(),
            },
            returning=ReturnMethod.minimal,
        ).eq("id", war["id"]).execute()

        logger.info(
            "Resolved stale war id=%d for clan %s → %s",
            war["id"], clan_tag, result,
        )
        resolved += 1

    return resolved


def upsert_war_attacks(war_id: int, war_data: dict) -> None:
    attacks: list[dict] = []
    for side_key in ("clan", "opponent"):
        side = war_data.get(side_key, {})
        is_home_attacker = side_key == "clan"
        for member in side.get("members", []):
            for atk in member.get("attacks", []):
                attacks.append({
                    "war_id": war_id,
                    "attacker_tag": atk["attackerTag"],
                    "defender_tag": atk["defenderTag"],
                    "stars": atk.get("stars", 0),
                    "destruction_percentage": atk.get("destructionPercentage", 0),
                    "attack_order": atk.get("order", 0),
                    "duration": atk.get("duration"),
                    "is_home_attacker": is_home_attacker,
                })
    if attacks:
        _upsert_minimal_batch("war_attacks", attacks, on_conflict="war_id,attacker_tag,attack_order")
        logger.info("Upserted %d attacks for war id=%d", len(attacks), war_id)


def upsert_capital_raid(raid_data: dict, clan_tag: str) -> int | None:
    start_time = _parse_coc_time(raid_data.get("startTime"))
    if not start_time:
        return None

    row = {
        "clan_tag": clan_tag,
        "state": raid_data.get("state", ""),
        "start_time": start_time,
        "end_time": _parse_coc_time(raid_data.get("endTime")) or start_time,
        "capital_total_loot": raid_data.get("capitalTotalLoot", 0),
        "raids_completed": raid_data.get("raidsCompleted", 0),
        "total_attacks": raid_data.get("totalAttacks", 0),
        "enemy_districts_destroyed": raid_data.get("enemyDistrictsDestroyed", 0),
        "offensive_reward": raid_data.get("offensiveReward", 0),
        "defensive_reward": raid_data.get("defensiveReward", 0),
        "updated_at": _now_iso(),
    }

    resp = get_db().table("capital_raids").upsert(row, on_conflict="clan_tag,start_time").execute()
    raid_id = resp.data[0]["id"] if resp.data else None
    if raid_id:
        logger.info("Upserted raid id=%d for clan %s", raid_id, clan_tag)
    return raid_id


def get_legends_player_tags(active_tags: set[str] | None = None) -> list[str]:
    """Return tracked Legend League tags for legends ingestion (see shared.legends_roster)."""
    return fetch_legends_roster_tags(get_db(), active_tags=active_tags)


def get_legends_day_attack_defense_counts(player_tag: str, legends_day: str) -> tuple[int, int]:
    """Return (attack_count, defense_count) for this player on the given legends day."""
    resp = (
        get_db()
        .table("legends_battles")
        .select("is_attack")
        .eq("player_tag", player_tag)
        .eq("legends_day", legends_day)
        .execute()
    )
    rows = resp.data or []
    attacks = sum(1 for r in rows if r.get("is_attack"))
    defenses = sum(1 for r in rows if not r.get("is_attack"))
    return attacks, defenses


def get_legends_battlelog_cursor(player_tag: str) -> dict | None:
    resp = (
        get_db()
        .table("legends_battlelog_cursor")
        .select("player_tag, cursor_snapshot, updated_at")
        .eq("player_tag", player_tag)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_legends_battlelog_cursor(player_tag: str, cursor_snapshot: dict) -> None:
    row = {
        "player_tag": player_tag,
        "cursor_snapshot": cursor_snapshot,
        "updated_at": _now_iso(),
    }
    get_db().table("legends_battlelog_cursor").upsert(
        row, on_conflict="player_tag", returning=ReturnMethod.minimal
    ).execute()


def upsert_legends_battle(row: dict) -> None:
    _upsert_minimal(
        "legends_battles",
        row,
        on_conflict="player_tag,opponent_tag,is_attack,stars,destruction_pct,legends_day",
    )


def upsert_legends_day_snapshot(player_tag: str, legends_day: str, trophies: int) -> bool:
    """Record trophy count for a legends day when it changed; return True if written.

    On conflict the row is overwritten, so the LAST snapshot written before the 5:00 UTC
    daily reset becomes that day's authoritative ``final_trophies`` (see docs/database.md).
    """
    trophies_int = int(trophies)
    if db_cache.legends_snapshot_unchanged(player_tag, legends_day, trophies_int):
        logger.debug(
            "Skipped unchanged legends day snapshot",
            extra={
                "event": "ingestion.db.upsert_skip",
                "table": "legends_day_snapshots",
                "player_tag": player_tag,
                "legends_day": legends_day,
            },
        )
        return False

    _upsert_minimal(
        "legends_day_snapshots",
        {
            "player_tag": player_tag,
            "legends_day": legends_day,
            "trophies": trophies_int,
            "snapshot_at": _now_iso(),
        },
        on_conflict="player_tag,legends_day",
    )
    db_cache.remember_legends_snapshot(player_tag, legends_day, trophies_int)
    return True


def upsert_legends_battles_batch(rows: list[dict]) -> None:
    if not rows:
        return
    _upsert_minimal_batch(
        "legends_battles",
        rows,
        on_conflict="player_tag,opponent_tag,is_attack,stars,destruction_pct,legends_day",
    )
    logger.info(
        "Upserted %d legends battle(s)",
        len(rows),
        extra={"event": "ingestion.db.upsert", "table": "legends_battles", "count": len(rows)},
    )


def insert_legends_confirmation_queue(player_tag: str, cursor_snapshot: dict, run_after_iso: str) -> None:
    _insert_minimal(
        "legends_confirmation_queue",
        {
            "player_tag": player_tag,
            "cursor_snapshot": cursor_snapshot,
            "run_after": run_after_iso,
        },
    )


def fetch_due_legends_confirmations(limit: int = 200) -> list[dict]:
    resp = (
        get_db()
        .table("legends_confirmation_queue")
        .select("id,player_tag,cursor_snapshot,run_after,created_at")
        .lte("run_after", _now_iso())
        .order("run_after", desc=False)
        .limit(limit)
        .execute()
    )
    return list(resp.data or [])


def delete_legends_confirmation_queue(queue_id: int) -> None:
    get_db().table("legends_confirmation_queue").delete(returning=ReturnMethod.minimal).eq(
        "id", queue_id
    ).execute()


def upsert_raid_members(raid_id: int, members: list[dict]) -> None:
    rows = [
        {
            "raid_id": raid_id,
            "player_tag": m["tag"],
            "name": m.get("name", ""),
            "attacks": m.get("attacks", 0),
            "attack_limit": m.get("attackLimit", 0),
            "bonus_attack_limit": m.get("bonusAttackLimit", 0),
            "capital_resources_looted": m.get("capitalResourcesLooted", 0),
        }
        for m in members
    ]
    if rows:
        _upsert_minimal_batch("raid_members", rows, on_conflict="raid_id,player_tag")
        logger.info("Upserted %d raid members for raid id=%d", len(rows), raid_id)


def get_battlelog_cursor(player_tag: str) -> dict | None:
    resp = (
        get_db()
        .table("player_battlelog_cursor")
        .select("player_tag, cursor_snapshot, updated_at")
        .eq("player_tag", player_tag)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_battlelog_cursor(player_tag: str, cursor_snapshot: dict) -> None:
    row = {
        "player_tag": player_tag,
        "cursor_snapshot": cursor_snapshot,
        "updated_at": _now_iso(),
    }
    get_db().table("player_battlelog_cursor").upsert(
        row, on_conflict="player_tag", returning=ReturnMethod.minimal
    ).execute()


def insert_player_attack_events_batch(rows: list[dict]) -> None:
    if not rows:
        return
    _upsert_minimal_batch(
        "player_attack_events",
        rows,
        on_conflict="player_tag,attacked_at,opponent_tag",
    )
    logger.info(
        "Upserted %d player attack event(s)",
        len(rows),
        extra={"event": "ingestion.db.upsert", "table": "player_attack_events", "count": len(rows)},
    )


def prune_player_attack_events_older_than_days(days: int = 90) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    get_db().table("player_attack_events").delete(returning=ReturnMethod.minimal).lt(
        "attacked_at", cutoff
    ).execute()
