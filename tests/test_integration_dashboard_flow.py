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

    class _Q:
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

    class _Db:
        def table(self, _n):
            return _Q()

    monkeypatch.setattr("api.routers.players.get_db", lambda: _Db())

    r = client.get("/api/players?page=1&page_size=20")
    assert r.status_code == 200
    PaginatedPlayersResponse.model_validate(r.json())
