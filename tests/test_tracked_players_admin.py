"""Always-tracked players: admin-only writes."""

from __future__ import annotations

from tests.test_admin import ADMIN_KEY, AUTH_HEADER


def test_post_tracked_players_without_auth_returns_401(client):
    r = client.post("/api/tracked-players", json={"player_tag": "#ABC", "name": "Player"})
    assert r.status_code == 401


def test_delete_tracked_players_without_auth_returns_401(client):
    r = client.delete("/api/tracked-players/%23ABC")
    assert r.status_code == 401


def test_patch_tracked_players_without_auth_returns_401(client):
    r = client.patch("/api/tracked-players/%23ABC", json={"display_name": "X"})
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
        json={"player_tag": "xyz99", "name": "Scout One", "note": "scout"},
    )
    assert r.status_code == 201
    assert mock.inserted is not None
    assert mock.inserted["player_tag"] == "#XYZ99"
    assert mock.inserted["display_name"] == "Scout One"
    assert mock.inserted["note"] == "scout"
    assert mock.inserted["tracking_group"] == "clan_july"


def test_add_tracked_player_accepts_legacy_name_json_key(client, monkeypatch):
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
        json={"player_tag": "#LEG", "name": "Legacy Key", "note": None},
    )
    assert r.status_code == 201
    assert mock.inserted is not None
    assert mock.inserted["display_name"] == "Legacy Key"
    assert mock.inserted["tracking_group"] == "clan_july"


def test_add_tracked_player_external_group(client, monkeypatch):
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
        json={"player_tag": "#EXT", "display_name": "Outsider", "tracking_group": "external"},
    )
    assert r.status_code == 201
    assert mock.inserted is not None
    assert mock.inserted["tracking_group"] == "external"


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


def test_add_tracked_player_resolves_name_from_players_when_omitted(client, monkeypatch):
    class PlayersChain:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [{"name": "  FromDb  "}]})()

    class TrackedInsert:
        def __init__(self):
            self.inserted: dict | None = None

        def insert(self, row):
            self.inserted = row
            return self

        def execute(self):
            return type("R", (), {"data": [self.inserted]})()

    class DB:
        def __init__(self):
            self.tracked = TrackedInsert()

        def table(self, name):
            if name == "players":
                return PlayersChain()
            if name == "tracked_players":
                return self.tracked
            raise AssertionError(name)

    db = DB()
    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: db)

    r = client.post(
        "/api/tracked-players",
        headers=AUTH_HEADER,
        json={"player_tag": "#abc", "note": "n1"},
    )
    assert r.status_code == 201
    assert db.tracked.inserted is not None
    assert db.tracked.inserted["player_tag"] == "#ABC"
    assert db.tracked.inserted["display_name"] == "FromDb"
    assert db.tracked.inserted["note"] == "n1"
    assert db.tracked.inserted["tracking_group"] == "clan_july"


def test_add_tracked_player_unknown_when_not_in_players_table(client, monkeypatch):
    class PlayersChain:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class TrackedInsert:
        def __init__(self):
            self.inserted: dict | None = None

        def insert(self, row):
            self.inserted = row
            return self

        def execute(self):
            return type("R", (), {"data": [self.inserted]})()

    class DB:
        def __init__(self):
            self.tracked = TrackedInsert()

        def table(self, name):
            if name == "players":
                return PlayersChain()
            if name == "tracked_players":
                return self.tracked
            raise AssertionError(name)

    db = DB()
    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: db)

    r = client.post(
        "/api/tracked-players",
        headers=AUTH_HEADER,
        json={"player_tag": "ghost"},
    )
    assert r.status_code == 201
    assert db.tracked.inserted is not None
    assert db.tracked.inserted["display_name"] == "Unknown player"
    assert db.tracked.inserted["tracking_group"] == "clan_july"


def test_list_tracked_players_invalid_tracking_group(client):
    r = client.get("/api/tracked-players?tracking_group=not_a_group")
    assert r.status_code == 422


def test_list_tracked_players_filter_external(client, monkeypatch):
    class ListMock:
        def __init__(self):
            self.eq_calls: list[tuple[str, str]] = []

        def table(self, _n):
            return self

        def select(self, *_a, **_k):
            return self

        def eq(self, col, val):
            self.eq_calls.append((col, val))
            return self

        def order(self, *_a, **_k):
            return self

        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "player_tag": "#E",
                            "display_name": "Ex",
                            "note": None,
                            "added_at": "2026-01-01",
                            "tracking_group": "external",
                        }
                    ]
                },
            )()

    mock = ListMock()
    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: mock)

    r = client.get("/api/tracked-players?tracking_group=external")
    assert r.status_code == 200
    assert mock.eq_calls == [("tracking_group", "external")]
    assert r.json()["data"][0]["tracking_group"] == "external"


def test_patch_tracked_player_display_name(client, monkeypatch):
    class UpdateChain:
        def __init__(self):
            self.updated: dict | None = None

        def update(self, row):
            self.updated = row
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "player_tag": "#X",
                            "display_name": self.updated["display_name"],
                            "note": None,
                            "added_at": "2026-01-01",
                            "tracking_group": "clan_july",
                        }
                    ]
                },
            )()

    mock = UpdateChain()

    class _FakeDb:
        def table(self, _name):
            return mock

    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: _FakeDb())

    r = client.patch(
        "/api/tracked-players/%23X",
        headers=AUTH_HEADER,
        json={"display_name": "New Label"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "New Label"
    assert mock.updated == {"display_name": "New Label"}


def test_patch_tracked_player_not_found(client, monkeypatch):
    class UpdateChain:
        def update(self, row):
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    mock = UpdateChain()

    class _FakeDb2:
        def table(self, _name):
            return mock

    monkeypatch.setattr("api.routers.tracked_players.get_db", lambda: _FakeDb2())

    r = client.patch(
        "/api/tracked-players/%23MISSING",
        headers=AUTH_HEADER,
        json={"display_name": "Nope"},
    )
    assert r.status_code == 404
