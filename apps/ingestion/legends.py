import logging
from datetime import datetime, timezone

from shared.battlelog import canonical_snapshot, is_attack, snapshots_equal
from shared.legends_roster import current_legends_day, legends_day_containing_utc
from shared.logutil import get_ingestion_run_id, log_event

from . import supercell_client as coc
from . import db

logger = logging.getLogger(__name__)

# current_legends_day is imported from shared.legends_roster


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


# Legends League allows at most 8 attacks and 8 defenses per legends day.
_MAX_LEGENDS_ATTACKS_OR_DEFENSES_PER_DAY = 8


def _legends_day_str_for_battle(battle: dict, fallback_day: str) -> str:
    """Assign DB legends_day from CoC battleTime when present (same 5:00 UTC rule as roster)."""
    raw = battle.get("battleTime")
    if not raw:
        return fallback_day
    iso = db.parse_coc_timestamp(str(raw))
    if not iso:
        return fallback_day
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return fallback_day
    return legends_day_containing_utc(dt).isoformat()


def _take_battles_respecting_per_day_caps(
    player_tag: str,
    battles_newest_first: list[dict],
    *,
    want_attack: bool,
    fallback_day: str,
    day_counts: dict[str, list[int]],
) -> list[dict]:
    """Keep newest-first order; skip battles when that legends_day is already at 8 for the type."""
    idx = 0 if want_attack else 1
    selected: list[dict] = []
    for battle in battles_newest_first:
        day_str = _legends_day_str_for_battle(battle, fallback_day)
        if day_str not in day_counts:
            a, d = db.get_legends_day_attack_defense_counts(player_tag, day_str)
            day_counts[day_str] = [a, d]
        if day_counts[day_str][idx] >= _MAX_LEGENDS_ATTACKS_OR_DEFENSES_PER_DAY:
            continue
        selected.append(battle)
        day_counts[day_str][idx] += 1
    return selected


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

    newest_legend = legend_battles[-1]
    cursor_row = db.get_legends_battlelog_cursor(player_tag)

    if cursor_row is None:
        db.upsert_legends_battlelog_cursor(player_tag, canonical_snapshot(newest_legend))
        log_event(
            logger,
            "ingestion.legends.baseline",
            f"Legends battle log cursor for {player_tag} (no backfill)",
            player_tag=player_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )
        return

    stored = cursor_row["cursor_snapshot"]
    if not isinstance(stored, dict):
        stored = dict(stored)

    new_battles: list[dict] = []
    found_cursor = False
    for b in reversed(legend_battles):
        if snapshots_equal(stored, b):
            found_cursor = True
            break
        new_battles.append(b)

    if not found_cursor:
        log_event(
            logger,
            "ingestion.legends.cursor_miss",
            f"Legends battle log cursor missing from API window for {player_tag}; resetting without backfill",
            player_tag=player_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )
        db.upsert_legends_battlelog_cursor(player_tag, canonical_snapshot(newest_legend))
        return

    # new_battles: newest-first (same order as reversed walk before break).
    new_attacks = [b for b in new_battles if is_attack(b)]
    new_defenses = [b for b in new_battles if not is_attack(b)]

    day_counts: dict[str, list[int]] = {}
    selected_attacks = _take_battles_respecting_per_day_caps(
        player_tag,
        new_attacks,
        want_attack=True,
        fallback_day=legends_day_str,
        day_counts=day_counts,
    )
    selected_defenses = _take_battles_respecting_per_day_caps(
        player_tag,
        new_defenses,
        want_attack=False,
        fallback_day=legends_day_str,
        day_counts=day_counts,
    )

    rows_to_upsert: list[dict] = []
    for battle in selected_attacks + selected_defenses:
        is_attack_flag = is_attack(battle)
        stars = int(battle.get("stars", 0))
        destruction_pct = int(battle.get("destructionPercentage", 0))
        opponent_tag = battle.get("opponentPlayerTag") or ""

        trophies = calculate_trophies(stars, destruction_pct)
        opponent_name = _resolve_opponent_name(client, opponent_tag)

        rows_to_upsert.append({
            "player_tag": player_tag,
            "opponent_tag": opponent_tag,
            "opponent_name": opponent_name,
            "is_attack": is_attack_flag,
            "stars": stars,
            "destruction_pct": destruction_pct,
            "trophies": trophies,
            "legends_day": _legends_day_str_for_battle(battle, legends_day_str),
            "first_seen_at": now_iso,
        })

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

    db.upsert_legends_battlelog_cursor(player_tag, canonical_snapshot(newest_legend))


_opponent_cache: dict[str, str | None] = {}


def _resolve_opponent_name(client, opponent_tag: str) -> str | None:
    if opponent_tag in _opponent_cache:
        return _opponent_cache[opponent_tag]
    player = coc.get_player(client, opponent_tag)
    name = player.get("name") if player else None
    _opponent_cache[opponent_tag] = name
    return name
