"""Unit tests for legends leaderboard battle aggregation."""

from __future__ import annotations

from api.routers.legends import _aggregate_legends_day_battles


def test_aggregate_counts_attacks_and_defenses():
    battles = [
        {"player_tag": "#X", "is_attack": True, "trophies": 30},
        {"player_tag": "#X", "is_attack": True, "trophies": 20},
        {"player_tag": "#X", "is_attack": False, "trophies": 10},
    ]
    agg, tags = _aggregate_legends_day_battles(battles, [])
    assert tags == {"#X"}
    assert agg["#X"]["attack_total"] == 50
    assert agg["#X"]["attack_battle_count"] == 2
    assert agg["#X"]["defense_total"] == 10
    assert agg["#X"]["defense_battle_count"] == 1


def test_aggregate_adds_roster_placeholder_with_zero_counts():
    agg, tags = _aggregate_legends_day_battles([], ["#Y"])
    assert tags == set()
    assert agg["#Y"]["attack_total"] == 0
    assert agg["#Y"]["defense_total"] == 0
    assert agg["#Y"]["attack_battle_count"] == 0
    assert agg["#Y"]["defense_battle_count"] == 0
