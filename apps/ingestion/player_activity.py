"""Ingest multiplayer battle log attack timestamps for hourly activity charts."""

import logging
from typing import Iterable

from shared.logutil import get_ingestion_run_id, log_event

from . import supercell_client as coc
from . import db

logger = logging.getLogger(__name__)

_RETENTION_DAYS = 14


def _canonical_snapshot(b: dict) -> dict:
    atk = b.get("attackKey")
    if atk is not None:
        attack_bool = bool(atk)
    else:
        attack_bool = bool(b.get("attack", True))
    return {
        "battleTime": b.get("battleTime"),
        "opponentPlayerTag": b.get("opponentPlayerTag") or "",
        "battleType": b.get("battleType") or "",
        "attack": attack_bool,
        "stars": int(b.get("stars", 0)),
        "destructionPercentage": int(b.get("destructionPercentage", 0)),
    }


def _snapshots_equal(stored: dict, battle: dict) -> bool:
    return _canonical_snapshot(stored) == _canonical_snapshot(battle)


def _is_attack(battle: dict) -> bool:
    if "attackKey" in battle:
        return bool(battle.get("attackKey"))
    return bool(battle.get("attack", True))


def _ingest_one_player(client, player_tag: str) -> None:
    battles = coc.get_player_battlelog(client, player_tag)
    if not battles:
        return

    newest = battles[-1]
    cursor_row = db.get_battlelog_cursor(player_tag)

    if cursor_row is None:
        db.upsert_battlelog_cursor(player_tag, _canonical_snapshot(newest))
        log_event(
            logger,
            "ingestion.player_activity.baseline",
            f"Baseline battle log cursor for {player_tag} (no backfill)",
            player_tag=player_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )
        return

    stored = cursor_row["cursor_snapshot"]
    if not isinstance(stored, dict):
        stored = dict(stored)

    new_battles: list[dict] = []
    found_cursor = False
    for b in reversed(battles):
        if _snapshots_equal(stored, b):
            found_cursor = True
            break
        new_battles.append(b)

    if not found_cursor:
        log_event(
            logger,
            "ingestion.player_activity.cursor_miss",
            f"Battle log cursor missing from API window for {player_tag}; resetting cursor without backfill",
            player_tag=player_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )
        db.upsert_battlelog_cursor(player_tag, _canonical_snapshot(newest))
        return

    rows: list[dict] = []
    for b in new_battles:
        if not _is_attack(b):
            continue
        raw_time = b.get("battleTime")
        attacked_at = db.parse_coc_timestamp(raw_time) if raw_time else None
        if not attacked_at:
            logger.warning(
                "Battle log entry missing or invalid battleTime; skipping",
                extra={
                    "event": "ingestion.player_activity.skip_time",
                    "player_tag": player_tag,
                    "battleTime": raw_time,
                    "ingestion_run_id": get_ingestion_run_id(),
                },
            )
            continue
        rows.append(
            {
                "player_tag": player_tag,
                "attacked_at": attacked_at,
                "opponent_tag": b.get("opponentPlayerTag") or "",
            }
        )

    if rows:
        db.insert_player_attack_events_batch(rows)
        log_event(
            logger,
            "ingestion.player_activity.stored",
            f"Stored {len(rows)} attack timestamp(s) for {player_tag}",
            player_tag=player_tag,
            new_attacks=len(rows),
            ingestion_run_id=get_ingestion_run_id(),
        )

    db.upsert_battlelog_cursor(player_tag, _canonical_snapshot(newest))


def ingest_player_activity(client, player_tags: Iterable[str]) -> None:
    db.prune_player_attack_events_older_than_days(_RETENTION_DAYS)

    tags = list(player_tags)
    log_event(
        logger,
        "ingestion.player_activity.start",
        f"Player battle activity for {len(tags)} tag(s)",
        player_count=len(tags),
        ingestion_run_id=get_ingestion_run_id(),
    )

    for tag in sorted(tags):
        try:
            _ingest_one_player(client, tag)
        except Exception:
            logger.exception(
                "Failed to ingest battle activity for player %s",
                tag,
                extra={
                    "event": "ingestion.player_activity.player_error",
                    "player_tag": tag,
                    "ingestion_run_id": get_ingestion_run_id(),
                },
            )

    log_event(
        logger,
        "ingestion.player_activity.complete",
        "Player battle activity ingestion complete",
        ingestion_run_id=get_ingestion_run_id(),
    )
