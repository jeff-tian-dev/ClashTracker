"""Always-tracked players: admin-only writes."""

from __future__ import annotations

from tests.test_admin import ADMIN_KEY, AUTH_HEADER


def test_post_tracked_players_without_auth_returns_401(client):
    r = client.post("/api/tracked-players", json={"player_tag": "#ABC"})
    assert r.status_code == 401


def test_delete_tracked_players_without_auth_returns_401(client):
    r = client.delete("/api/tracked-players/%23ABC")
    assert r.status_code == 401


def test_add_tracked_player_normalizes_tag(client, monkeypatch):
    class _InsertMock:
        def __init__(self):
            self.inserted: dict | None = None

        def table(self, _name):
            return self

        def insert(self, row):
            self.inserted = row
            return self

        def execute(self):
            row = self.inserted or {}
            return type("R", (), {"data": [row]})()

    mock = _InsertMock()
    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: mock)

    r = client.post(
        "/api/tracked-players",
        headers=AUTH_HEADER,
        json={"player_tag": "xyz99", "note": "scout"},
    )
    assert r.status_code == 201
    assert mock.inserted is not None
    assert mock.inserted["player_tag"] == "#XYZ99"
    assert mock.inserted["note"] == "scout"


def test_remove_tracked_player_success(client, monkeypatch):
    class _Del:
        def __init__(self):
            self.eq_calls: list[tuple[str, str]] = []

        def table(self, _n):
            return self

        def delete(self):
            return self

        def eq(self, col, val):
            self.eq_calls.append((col, val))
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    mock = _Del()
    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: mock)

    r = client.delete("/api/tracked-players/%23PINNED", headers=AUTH_HEADER)
    assert r.status_code == 204
    assert mock.eq_calls == [("player_tag", "#PINNED")]
