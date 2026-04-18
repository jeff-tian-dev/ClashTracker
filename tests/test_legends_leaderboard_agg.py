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


def test_past_day_uses_snapshot_for_final_trophies(client, monkeypatch):
    """For past legends_day, final_trophies comes from legends_day_snapshots (not live)."""

    # Past day within the current Legends season (2026-03-23 season start per shared helper).
    past_day = "2026-03-25"

    # Live trophies diverge from the snapshot (simulates a day having passed).
    live_trophies = 5500
    snapshot_trophies = 5200
    attack_total = 80
    defense_total = 30
    expected_net = attack_total - defense_total
    expected_initial = snapshot_trophies - expected_net

    class _Chain:
        def __init__(self):
            self._table: str | None = None
            self._filters: dict = {}

        def table(self, name: str):
            self._table = name
            self._filters = {}
            return self

        def select(self, *_a, **_k):
            return self

        def eq(self, col: str, val):
            self._filters[col] = val
            return self

        def in_(self, col: str, vals):
            self._filters[col] = list(vals)
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def range(self, *_a, **_k):
            return self

        def execute(self):
            t = self._table
            if t == "legends_battles":
                return _Resp([
                    {"player_tag": "#P1", "is_attack": True, "trophies": attack_total},
                    {"player_tag": "#P1", "is_attack": False, "trophies": defense_total},
                ])
            if t == "tracked_players":
                return _Resp([
                    {"player_tag": "#P1", "tracking_group": "clan_july", "legends_bracket": 1},
                ])
            if t == "players":
                return _Resp([
                    {"tag": "#P1", "name": "TestPlayer", "trophies": live_trophies, "left_tracked_roster_at": None},
                ])
            if t == "legends_day_snapshots":
                return _Resp([{"player_tag": "#P1", "trophies": snapshot_trophies}])
            return _Resp([])

    class _Resp:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr("api.routers.legends.get_db", lambda: _Chain())

    r = client.get(f"/api/legends?legends_day={past_day}")
    assert r.status_code == 200
    body = r.json()
    assert body["legends_day"] == past_day
    rows = body["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["player_tag"] == "#P1"
    assert row["final_trophies"] == snapshot_trophies, "past-day final_trophies must come from snapshot, not live"
    assert row["initial_trophies"] == expected_initial
    assert row["net"] == expected_net
