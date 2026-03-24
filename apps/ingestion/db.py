import logging
from datetime import datetime, timezone

from supabase import create_client, Client
from shared.legends_roster import fetch_legends_roster_tags

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
            db.table("players").update({"left_tracked_roster_at": None}).in_("tag", chunk).execute()

    q = db.table("players").select("tag").is_("left_tracked_roster_at", None)
    if active_list:
        q = q.not_.in_("tag", active_list)
    resp = q.execute()
    tags_to_mark = [r["tag"] for r in (resp.data or [])]
    now = _now_iso()
    for i in range(0, len(tags_to_mark), CHUNK):
        chunk = tags_to_mark[i : i + CHUNK]
        db.table("players").update({"left_tracked_roster_at": now}).in_("tag", chunk).execute()

    if tags_to_mark:
        logger.info(
            "Marked %d player(s) as off tracked roster (first detection)",
            len(tags_to_mark),
            extra={"event": "ingestion.db.reconcile", "marked_count": len(tags_to_mark)},
        )


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
    get_db().table("clans").upsert(row, on_conflict="tag").execute()
    logger.info(
        "Upserted clan",
        extra={"event": "ingestion.db.upsert", "table": "clans", "tag": row["tag"], "clan_name": row["name"]},
    )


def upsert_player(player_data: dict) -> None:
    clan = player_data.get("clan")
    league_tier = player_data.get("leagueTier") or {}
    league_obj = player_data.get("league") or {}
    # Prefer leagueTier.name (granular tier); fall back to league.name if tier omitted.
    league_name = league_tier.get("name") or league_obj.get("name")
    row = {
        "tag": player_data["tag"],
        "name": player_data["name"],
        "clan_tag": clan["tag"] if clan else None,
        "town_hall_level": player_data.get("townHallLevel", 1),
        "exp_level": player_data.get("expLevel", 1),
        "trophies": player_data.get("trophies", 0),
        "best_trophies": player_data.get("bestTrophies", 0),
        "war_stars": player_data.get("warStars", 0),
        "attack_wins": player_data.get("attackWins", 0),
        "defense_wins": player_data.get("defenseWins", 0),
        "role": player_data.get("role"),
        "war_preference": player_data.get("warPreference"),
        "clan_capital_contributions": player_data.get("clanCapitalContributions", 0),
        "league_name": league_name,
        "updated_at": _now_iso(),
    }
    get_db().table("players").upsert(row, on_conflict="tag").execute()
    logger.debug(
        "Upserted player",
        extra={"event": "ingestion.db.upsert", "table": "players", "tag": row["tag"]},
    )


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

        get_db().table("wars").update({
            "state": "warEnded",
            "result": result,
            "updated_at": _now_iso(),
        }).eq("id", war["id"]).execute()

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
                })
    if attacks:
        get_db().table("war_attacks").upsert(
            attacks, on_conflict="war_id,attacker_tag,attack_order"
        ).execute()
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


def get_legends_player_tags() -> list[str]:
    """Return tags on the Legends daily roster (see shared.legends_roster)."""
    return fetch_legends_roster_tags(get_db())


def get_existing_legends_keys(player_tag: str, legends_day: str) -> set[tuple]:
    """Return dedup keys already stored for a player on the given legends day."""
    resp = (
        get_db()
        .table("legends_battles")
        .select("opponent_tag, is_attack, stars, destruction_pct")
        .eq("player_tag", player_tag)
        .eq("legends_day", legends_day)
        .execute()
    )
    return {
        (r["opponent_tag"], r["is_attack"], r["stars"], r["destruction_pct"])
        for r in (resp.data or [])
    }


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


def get_recent_legends_keys(player_tag: str, since_day: str) -> set[tuple]:
    """Return dedup keys for a player across all days >= since_day.

    Used to avoid re-adding old battles from the API response under
    the current day (the battle log has no timestamps, so old battles
    still appear in the response).
    """
    resp = (
        get_db()
        .table("legends_battles")
        .select("opponent_tag, is_attack, stars, destruction_pct")
        .eq("player_tag", player_tag)
        .gte("legends_day", since_day)
        .execute()
    )
    return {
        (r["opponent_tag"], r["is_attack"], r["stars"], r["destruction_pct"])
        for r in (resp.data or [])
    }


def upsert_legends_battle(row: dict) -> None:
    get_db().table("legends_battles").upsert(
        row,
        on_conflict="player_tag,opponent_tag,is_attack,stars,destruction_pct,legends_day",
    ).execute()


def upsert_legends_battles_batch(rows: list[dict]) -> None:
    if not rows:
        return
    get_db().table("legends_battles").upsert(
        rows,
        on_conflict="player_tag,opponent_tag,is_attack,stars,destruction_pct,legends_day",
    ).execute()
    logger.info(
        "Upserted %d legends battle(s)",
        len(rows),
        extra={"event": "ingestion.db.upsert", "table": "legends_battles", "count": len(rows)},
    )


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
        get_db().table("raid_members").upsert(rows, on_conflict="raid_id,player_tag").execute()
        logger.info("Upserted %d raid members for raid id=%d", len(rows), raid_id)
