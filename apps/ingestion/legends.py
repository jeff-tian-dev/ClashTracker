import logging
from datetime import date, datetime, time, timezone, timedelta

from shared.logutil import get_ingestion_run_id, log_event

from . import supercell_client as coc
from . import db

logger = logging.getLogger(__name__)

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


def calculate_trophies(stars: int, destruction_pct: int) -> int:
    if stars == 3:
        return 40
    if stars == 2:
        return max(0, 16 + (destruction_pct - 50) // 3)
    if stars == 1:
        return max(0, 5 + (destruction_pct - 1) // 9)
    return max(0, destruction_pct // 10)


def ingest_legends(client) -> None:
    """Fetch battle logs for all legends-league players and store new battles."""
    legends_day = current_legends_day()
    legends_day_str = legends_day.isoformat()

    player_tags = db.get_legends_player_tags()
    if not player_tags:
        log_event(
            logger,
            "ingestion.legends.skip",
            "No players in Legends league — skipping legends ingestion",
            ingestion_run_id=get_ingestion_run_id(),
        )
        return

    log_event(
        logger,
        "ingestion.legends.start",
        f"Processing legends battles for {len(player_tags)} player(s), day={legends_day_str}",
        player_count=len(player_tags),
        legends_day=legends_day_str,
        ingestion_run_id=get_ingestion_run_id(),
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    for tag in player_tags:
        try:
            _ingest_player_legends(client, tag, legends_day_str, now_iso)
        except Exception:
            logger.exception(
                "Failed to ingest legends for player %s",
                tag,
                extra={
                    "event": "ingestion.legends.player_error",
                    "player_tag": tag,
                    "ingestion_run_id": get_ingestion_run_id(),
                },
            )

    log_event(
        logger,
        "ingestion.legends.complete",
        "Legends ingestion complete",
        ingestion_run_id=get_ingestion_run_id(),
    )


_LOOKBACK_DAYS = 3
# Legends League allows at most 8 attacks and 8 defenses per legends day.
_MAX_LEGENDS_ATTACKS_OR_DEFENSES_PER_DAY = 8


def _ingest_player_legends(
    client, player_tag: str, legends_day_str: str, now_iso: str
) -> None:
    player_data = coc.get_player(client, player_tag)
    if player_data:
        db.upsert_player(player_data)

    battles = coc.get_player_battlelog(client, player_tag)
    legend_battles = [b for b in battles if b.get("battleType") == "legend"]
    if not legend_battles:
        return

    since_day = (current_legends_day() - timedelta(days=_LOOKBACK_DAYS)).isoformat()
    seen_keys = db.get_recent_legends_keys(player_tag, since_day)

    # Battles not yet in DB (any day in lookback), in API order (oldest → newest).
    new_attack_battles: list[dict] = []
    new_defense_battles: list[dict] = []
    for battle in legend_battles:
        is_attack = battle.get("attack", True)
        stars = battle.get("stars", 0)
        destruction_pct = battle.get("destructionPercentage", 0)
        opponent_tag = battle.get("opponentPlayerTag", "")

        dedup_key = (opponent_tag, is_attack, stars, destruction_pct)
        if dedup_key in seen_keys:
            continue

        if is_attack:
            new_attack_battles.append(battle)
        else:
            new_defense_battles.append(battle)

    db_attack_count, db_defense_count = db.get_legends_day_attack_defense_counts(
        player_tag, legends_day_str
    )
    attack_slots = max(0, _MAX_LEGENDS_ATTACKS_OR_DEFENSES_PER_DAY - db_attack_count)
    defense_slots = max(0, _MAX_LEGENDS_ATTACKS_OR_DEFENSES_PER_DAY - db_defense_count)

    # Prefer the newest battles (tail of API list) up to remaining slots. This avoids
    # stuffing prior-season rows when the log is a rolling window without timestamps.
    take_attacks = min(len(new_attack_battles), attack_slots)
    take_defenses = min(len(new_defense_battles), defense_slots)
    selected_attacks = new_attack_battles[-take_attacks:] if take_attacks else []
    selected_defenses = new_defense_battles[-take_defenses:] if take_defenses else []

    rows_to_upsert: list[dict] = []
    for battle in selected_attacks + selected_defenses:
        is_attack = battle.get("attack", True)
        stars = battle.get("stars", 0)
        destruction_pct = battle.get("destructionPercentage", 0)
        opponent_tag = battle.get("opponentPlayerTag", "")

        trophies = calculate_trophies(stars, destruction_pct)
        opponent_name = _resolve_opponent_name(client, opponent_tag)

        rows_to_upsert.append({
            "player_tag": player_tag,
            "opponent_tag": opponent_tag,
            "opponent_name": opponent_name,
            "is_attack": is_attack,
            "stars": stars,
            "destruction_pct": destruction_pct,
            "trophies": trophies,
            "legends_day": legends_day_str,
            "first_seen_at": now_iso,
        })
        seen_keys.add((opponent_tag, is_attack, stars, destruction_pct))

    if rows_to_upsert:
        db.upsert_legends_battles_batch(rows_to_upsert)
        log_event(
            logger,
            "ingestion.legends.player_done",
            f"Stored {len(rows_to_upsert)} new legends battle(s) for {player_tag}",
            player_tag=player_tag,
            new_battles=len(rows_to_upsert),
            ingestion_run_id=get_ingestion_run_id(),
        )


_opponent_cache: dict[str, str | None] = {}


def _resolve_opponent_name(client, opponent_tag: str) -> str | None:
    if opponent_tag in _opponent_cache:
        return _opponent_cache[opponent_tag]
    player = coc.get_player(client, opponent_tag)
    name = player.get("name") if player else None
    _opponent_cache[opponent_tag] = name
    return name
