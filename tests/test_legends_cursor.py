"""Legends ingestion: battle-log cursor baseline (no backfill)."""

from __future__ import annotations

from ingestion import legends
from shared.battlelog import canonical_snapshot as _canonical_snapshot


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
