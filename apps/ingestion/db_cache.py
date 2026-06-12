"""Run-scoped caches for ingestion DB reads/writes (reset each ingest run)."""

from __future__ import annotations

import logging
from typing import Iterable

from shared.player_ingest import PLAYER_COMPARE_KEYS, player_row_compare_slice

logger = logging.getLogger(__name__)

_CHUNK = 200

_player_compare: dict[str, dict] = {}
_known_clan_tags: set[str] | None = None
_legends_snapshot_trophies: dict[tuple[str, str], int] = {}


def reset_ingestion_caches() -> None:
    global _known_clan_tags
    _player_compare.clear()
    _known_clan_tags = None
    _legends_snapshot_trophies.clear()


def warm_player_compare_cache(db, tags: Iterable[str]) -> None:
    """Batch-load comparable player columns for skip-if-unchanged upserts."""
    tag_list = sorted({t for t in tags if t})
    if not tag_list:
        return
    cols = ",".join(PLAYER_COMPARE_KEYS)
    loaded = 0
    for i in range(0, len(tag_list), _CHUNK):
        chunk = tag_list[i : i + _CHUNK]
        resp = db.table("players").select(cols).in_("tag", chunk).execute()
        for row in resp.data or []:
            tag = row.get("tag")
            if tag:
                _player_compare[tag] = player_row_compare_slice(row)
                loaded += 1
    logger.debug(
        "Warmed player compare cache",
        extra={"event": "ingestion.db.cache.warm_players", "loaded": loaded, "requested": len(tag_list)},
    )


def get_player_compare_row(db, tag: str) -> dict | None:
    cached = _player_compare.get(tag)
    if cached is not None:
        return cached
    cols = ",".join(PLAYER_COMPARE_KEYS)
    resp = db.table("players").select(cols).eq("tag", tag).limit(1).execute()
    rows = resp.data or []
    if not rows:
        return None
    sliced = player_row_compare_slice(rows[0])
    _player_compare[tag] = sliced
    return sliced


def remember_player_compare_row(row: dict) -> None:
    tag = row.get("tag")
    if tag:
        _player_compare[tag] = player_row_compare_slice(row)


def warm_clan_tag_cache(db) -> None:
    global _known_clan_tags
    if _known_clan_tags is not None:
        return
    tags: set[str] = set()
    off = 0
    batch = 1000
    while True:
        resp = db.table("clans").select("tag").range(off, off + batch - 1).execute()
        chunk = resp.data or []
        for row in chunk:
            t = row.get("tag")
            if t:
                tags.add(t)
        if len(chunk) < batch:
            break
        off += batch
    _known_clan_tags = tags
    logger.debug(
        "Warmed clan tag cache",
        extra={"event": "ingestion.db.cache.warm_clans", "count": len(tags)},
    )


def clan_tag_known(db, tag: str) -> bool:
    if not tag:
        return False
    warm_clan_tag_cache(db)
    assert _known_clan_tags is not None
    if tag in _known_clan_tags:
        return True
    resp = db.table("clans").select("tag").eq("tag", tag).limit(1).execute()
    exists = bool(resp.data)
    if exists:
        _known_clan_tags.add(tag)
    return exists


def remember_clan_tag(tag: str) -> None:
    global _known_clan_tags
    if not tag:
        return
    if _known_clan_tags is None:
        _known_clan_tags = set()
    _known_clan_tags.add(tag)


def warm_legends_snapshot_cache(db, player_tags: Iterable[str], legends_day: str) -> None:
    """Batch-load trophy snapshots for the current legends day."""
    tag_list = sorted({t for t in player_tags if t})
    if not tag_list:
        return
    loaded = 0
    for i in range(0, len(tag_list), _CHUNK):
        chunk = tag_list[i : i + _CHUNK]
        resp = (
            db.table("legends_day_snapshots")
            .select("player_tag,trophies")
            .eq("legends_day", legends_day)
            .in_("player_tag", chunk)
            .execute()
        )
        for row in resp.data or []:
            pt = row.get("player_tag")
            if pt is not None and row.get("trophies") is not None:
                _legends_snapshot_trophies[(pt, legends_day)] = int(row["trophies"])
                loaded += 1
    logger.debug(
        "Warmed legends snapshot cache",
        extra={
            "event": "ingestion.db.cache.warm_legends_snapshots",
            "legends_day": legends_day,
            "loaded": loaded,
            "requested": len(tag_list),
        },
    )


def legends_snapshot_unchanged(player_tag: str, legends_day: str, trophies: int) -> bool:
    key = (player_tag, legends_day)
    cached = _legends_snapshot_trophies.get(key)
    return cached is not None and cached == trophies


def remember_legends_snapshot(player_tag: str, legends_day: str, trophies: int) -> None:
    _legends_snapshot_trophies[(player_tag, legends_day)] = trophies
