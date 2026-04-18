"""Unit tests for legends leaderboard battle aggregation + API validation."""

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


def test_legends_leaderboard_rejects_out_of_season_day(client):
    r = client.get("/api/legends?legends_day=2020-01-01")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "out_of_season"


def test_legends_leaderboard_rejects_invalid_day_format(client):
    r = client.get("/api/legends?legends_day=not-a-date")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_legends_day"
