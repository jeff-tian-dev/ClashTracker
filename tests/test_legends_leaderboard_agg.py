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


class _Resp:
    def __init__(self, data):
        self.data = data


def _make_chain(snapshot_rows: list[dict], *, attack_total: int, defense_total: int, live_trophies: int):
    """Fake DB chain for the leaderboard endpoint; returns one player '#P1'."""

    class _Chain:
        def __init__(self):
            self._table: str | None = None

        def table(self, name: str):
            self._table = name
            return self

        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def in_(self, *_a, **_k):
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
                return _Resp(list(snapshot_rows))
            return _Resp([])

    return _Chain()


def test_past_day_uses_snapshot_for_final_trophies(client, monkeypatch):
    """For past legends_day, final_trophies comes from legends_day_snapshots (not live)."""

    past_day = "2026-03-25"
    live_trophies = 5500
    snapshot_trophies = 5200
    attack_total = 80
    defense_total = 30
    expected_net = attack_total - defense_total
    expected_initial = snapshot_trophies - expected_net

    monkeypatch.setattr(
        "api.routers.legends.get_db",
        lambda: _make_chain(
            [{"player_tag": "#P1", "trophies": snapshot_trophies}],
            attack_total=attack_total,
            defense_total=defense_total,
            live_trophies=live_trophies,
        ),
    )

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


def test_past_day_without_snapshot_returns_unknown_trophies(client, monkeypatch):
    """Past legends_day with no snapshot returns null trophies (UI renders 'Unknown')."""

    past_day = "2026-03-25"

    monkeypatch.setattr(
        "api.routers.legends.get_db",
        lambda: _make_chain(
            [],
            attack_total=80,
            defense_total=30,
            live_trophies=5500,
        ),
    )

    r = client.get(f"/api/legends?legends_day={past_day}")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["final_trophies"] is None, "no snapshot → unknown (must not fall back to live)"
    assert row["initial_trophies"] is None
    assert row["net"] == 50
