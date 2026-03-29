"""Main read workflow: dashboard summary + list endpoints with mocked DB."""

from __future__ import annotations

from api.schemas.contract import DashboardResponse, PaginatedPlayersResponse
from tests.support.dashboard_db_mock import MockDashboardDb, default_dashboard_sequence


def test_dashboard_happy_path_validates_contract(client, monkeypatch):
    mock = MockDashboardDb(default_dashboard_sequence())
    monkeypatch.setattr("api.routers.dashboard.get_db", lambda: mock)

    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    parsed = DashboardResponse.model_validate(body)
    assert parsed.total_players == 40
    assert parsed.active_wars == 1
    assert len(parsed.recent_wars) == 1
    assert len(parsed.recent_raids) == 1


def test_players_first_page_shape(client, monkeypatch):
    class _R:
        data = [{"tag": "#ABC", "name": "Tester", "clan_tag": None}]
        count = 1

    class _QPlayers:
        def select(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def range(self, *a, **k):
            return self

        def ilike(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def execute(self):
            return _R()

    class _QAttackEvents:
        def select(self, *a, **k):
            return self

        def in_(self, *a, **k):
            return self

        def gte(self, *a, **k):
            return self

        def execute(self):
            class _E:
                data: list = []

            return _E()

    class _QTracked:
        def select(self, *a, **k):
            return self

        def execute(self):
            class _Tr:
                data: list = []

            return _Tr()

    class _Db:
        def table(self, name):
            if name == "players":
                return _QPlayers()
            if name == "tracked_players":
                return _QTracked()
            if name == "player_attack_events":
                return _QAttackEvents()
            raise AssertionError(f"unexpected table {name!r}")

    monkeypatch.setattr("api.routers.players.get_db", lambda: _Db())

    r = client.get("/api/players?page=1&page_size=20")
    assert r.status_code == 200
    body = r.json()
    PaginatedPlayersResponse.model_validate(body)
    assert body["data"][0].get("is_always_tracked") is False
    assert body["data"][0].get("tracking_group") is None
    assert body["data"][0].get("attacks_7d") == 0
