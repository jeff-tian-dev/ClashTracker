"""Legends ingestion: battle-log cursor baseline (no backfill)."""

from __future__ import annotations

from datetime import datetime, timezone

from ingestion import legends
from shared.battlelog import canonical_snapshot as _canonical_snapshot
from shared.legends_roster import legends_day_containing_utc


def _legend_battle(**kwargs) -> dict:
    row = {
        "battleType": "legend",
        "opponentPlayerTag": "#OPP",
        "stars": 3,
        "destructionPercentage": 100,
        "attack": True,
    }
    row.update(kwargs)
    return row


def test_legends_first_run_sets_cursor_no_battles(monkeypatch):
    cursor_calls: list[tuple[str, dict]] = []
    batch_calls: list[list] = []

    monkeypatch.setattr(legends.db, "get_legends_battlelog_cursor", lambda _tag: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battlelog_cursor",
        lambda tag, snap: cursor_calls.append((tag, snap)),
    )
    monkeypatch.setattr(legends.db, "upsert_player", lambda _p: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battles_batch",
        lambda rows: batch_calls.append(list(rows)),
    )

    battle_log = [_legend_battle(opponentPlayerTag="#A1"), _legend_battle(opponentPlayerTag="#A2", stars=2)]
    monkeypatch.setattr(legends.coc, "get_player", lambda _c, _t: {})
    monkeypatch.setattr(legends.coc, "get_player_battlelog", lambda _c, _t: battle_log)

    legends._ingest_player_legends(object(), "#P1", "2026-03-25", "2026-03-25T00:00:00Z")

    assert len(cursor_calls) == 1
    assert cursor_calls[0][0] == "#P1"
    assert cursor_calls[0][1] == _canonical_snapshot(battle_log[-1])
    assert batch_calls == []


def test_legends_second_run_inserts_only_after_cursor(monkeypatch):
    battle_old = _legend_battle(opponentPlayerTag="#OLD")
    battle_cursor = _legend_battle(opponentPlayerTag="#MID", stars=2, destructionPercentage=80)
    battle_new = _legend_battle(opponentPlayerTag="#NEW", attack=False, stars=1)
    battle_log = [battle_old, battle_cursor, battle_new]

    stored = _canonical_snapshot(battle_cursor)
    monkeypatch.setattr(
        legends.db,
        "get_legends_battlelog_cursor",
        lambda _tag: {"cursor_snapshot": stored},
    )

    cursor_calls: list[tuple[str, dict]] = []
    batch_calls: list[list] = []

    monkeypatch.setattr(legends.db, "upsert_player", lambda _p: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battlelog_cursor",
        lambda tag, snap: cursor_calls.append((tag, snap)),
    )
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battles_batch",
        lambda rows: batch_calls.append(list(rows)),
    )
    monkeypatch.setattr(
        legends.db,
        "get_legends_day_attack_defense_counts",
        lambda _tag, _day: (0, 0),
    )

    monkeypatch.setattr(legends.coc, "get_player", lambda _c, _t: {})
    monkeypatch.setattr(legends.coc, "get_player_battlelog", lambda _c, _t: battle_log)

    legends._ingest_player_legends(object(), "#P1", "2026-03-25", "2026-03-25T00:00:00Z")

    assert len(batch_calls) == 1
    assert len(batch_calls[0]) == 1
    assert batch_calls[0][0]["opponent_tag"] == "#NEW"
    assert batch_calls[0][0]["is_attack"] is False

    assert len(cursor_calls) == 1
    assert cursor_calls[0][1] == _canonical_snapshot(battle_new)


def test_legends_cursor_miss_resets_without_batch(monkeypatch):
    battle_log = [_legend_battle(opponentPlayerTag="#X")]
    ghost_snapshot = _canonical_snapshot(_legend_battle(opponentPlayerTag="#MISSING"))

    monkeypatch.setattr(
        legends.db,
        "get_legends_battlelog_cursor",
        lambda _tag: {"cursor_snapshot": ghost_snapshot},
    )

    cursor_calls: list[tuple[str, dict]] = []
    batch_calls: list[list] = []

    monkeypatch.setattr(legends.db, "upsert_player", lambda _p: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battlelog_cursor",
        lambda tag, snap: cursor_calls.append((tag, snap)),
    )
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battles_batch",
        lambda rows: batch_calls.append(list(rows)),
    )

    monkeypatch.setattr(legends.coc, "get_player", lambda _c, _t: {})
    monkeypatch.setattr(legends.coc, "get_player_battlelog", lambda _c, _t: battle_log)

    legends._ingest_player_legends(object(), "#P1", "2026-03-25", "2026-03-25T00:00:00Z")

    assert batch_calls == []
    assert len(cursor_calls) == 1
    assert cursor_calls[0][1] == _canonical_snapshot(battle_log[-1])


def test_collect_new_legends_since_cursor_frozen_anchor_finds_gap():
    """Older anchor than DB tail finds battles inserted 'above' the live cursor (simulated late API row)."""
    # Order matches existing tests: index 0 = older in list, -1 = newest.
    battle_old = _legend_battle(opponentPlayerTag="#OLD")
    battle_mid = _legend_battle(opponentPlayerTag="#MID", attack=False, stars=2, destructionPercentage=69)
    battle_new = _legend_battle(opponentPlayerTag="#NEW", stars=2, destructionPercentage=91)
    legend_battles = [battle_old, battle_mid, battle_new]

    stored = _canonical_snapshot(battle_old)
    new_battles, found = legends.collect_new_legends_since_cursor(legend_battles, stored)
    assert found is True
    assert len(new_battles) == 2
    assert new_battles[0] == battle_new
    assert new_battles[1] == battle_mid


def test_ingest_confirmation_override_uses_frozen_cursor_not_db(monkeypatch):
    """Override path diffs against provided snapshot even if DB cursor is newer."""
    battle_old = _legend_battle(opponentPlayerTag="#OLD")
    battle_mid = _legend_battle(opponentPlayerTag="#MID", attack=False, stars=2, destructionPercentage=69)
    battle_new = _legend_battle(opponentPlayerTag="#NEW", stars=2, destructionPercentage=91)
    battle_log = [battle_old, battle_mid, battle_new]

    db_cursor = _canonical_snapshot(battle_new)
    monkeypatch.setattr(
        legends.db,
        "get_legends_battlelog_cursor",
        lambda _tag: {"cursor_snapshot": db_cursor},
    )

    batch_calls: list[list] = []
    cursor_calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(legends.db, "upsert_player", lambda _p: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battlelog_cursor",
        lambda tag, snap: cursor_calls.append((tag, snap)),
    )
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battles_batch",
        lambda rows: batch_calls.append(list(rows)),
    )
    monkeypatch.setattr(
        legends.db,
        "get_legends_day_attack_defense_counts",
        lambda _tag, _day: (0, 0),
    )

    monkeypatch.setattr(legends.coc, "get_player", lambda _c, _t: {})
    monkeypatch.setattr(legends.coc, "get_player_battlelog", lambda _c, _t: battle_log)

    frozen = _canonical_snapshot(battle_old)
    legends._ingest_player_legends(
        object(),
        "#P1",
        "2026-03-25",
        "2026-03-25T00:00:00Z",
        cursor_snapshot_override=frozen,
        confirmation_run=True,
    )

    assert len(batch_calls) == 1
    tags = {r["opponent_tag"] for r in batch_calls[0]}
    assert tags == {"#MID", "#NEW"}

    assert len(cursor_calls) == 1
    assert cursor_calls[0][1] == _canonical_snapshot(battle_new)


def test_legends_day_containing_utc_respects_5am_boundary():
    before = datetime(2026, 3, 25, 4, 59, 0, tzinfo=timezone.utc)
    assert legends_day_containing_utc(before).isoformat() == "2026-03-24"
    at_reset = datetime(2026, 3, 25, 5, 0, 0, tzinfo=timezone.utc)
    assert legends_day_containing_utc(at_reset).isoformat() == "2026-03-25"


def test_legends_row_legends_day_from_battle_time(monkeypatch):
    battle_old = _legend_battle(opponentPlayerTag="#OLD", battleTime="20260324T120000.000Z")
    battle_cursor = _legend_battle(
        opponentPlayerTag="#MID", stars=2, destructionPercentage=80, battleTime="20260324T130000.000Z"
    )
    battle_new = _legend_battle(
        opponentPlayerTag="#NEW", attack=False, stars=1, battleTime="20260325T060000.000Z"
    )
    battle_log = [battle_old, battle_cursor, battle_new]

    stored = _canonical_snapshot(battle_cursor)
    monkeypatch.setattr(
        legends.db,
        "get_legends_battlelog_cursor",
        lambda _tag: {"cursor_snapshot": stored},
    )

    batch_calls: list[list] = []

    monkeypatch.setattr(legends.db, "upsert_player", lambda _p: None)
    monkeypatch.setattr(legends.db, "upsert_legends_battlelog_cursor", lambda *_a, **_k: None)
    monkeypatch.setattr(
        legends.db,
        "upsert_legends_battles_batch",
        lambda rows: batch_calls.append(list(rows)),
    )
    monkeypatch.setattr(
        legends.db,
        "get_legends_day_attack_defense_counts",
        lambda _tag, _day: (0, 0),
    )

    monkeypatch.setattr(legends.coc, "get_player", lambda _c, _t: {})
    monkeypatch.setattr(legends.coc, "get_player_battlelog", lambda _c, _t: battle_log)

    legends._ingest_player_legends(object(), "#P1", "2026-03-24", "2026-03-25T00:00:00Z")

    assert len(batch_calls) == 1
    assert len(batch_calls[0]) == 1
    assert batch_calls[0][0]["legends_day"] == "2026-03-25"
