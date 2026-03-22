"""Admin auth guard and delete endpoint tests."""

from __future__ import annotations

ADMIN_KEY = "test-admin-secret"
AUTH_HEADER = {"Authorization": f"Bearer {ADMIN_KEY}"}


# -- Auth guard tests ----------------------------------------------------------


def test_delete_without_auth_returns_401(client):
    r = client.delete("/api/players/%23TEST")
    assert r.status_code == 401


def test_delete_with_wrong_key_returns_403(client):
    r = client.delete("/api/players/%23TEST", headers={"Authorization": "Bearer wrong-key"})
    assert r.status_code == 403


def test_admin_verify_with_correct_key_returns_200(client):
    r = client.post("/api/admin/verify", headers=AUTH_HEADER)
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_admin_verify_without_key_returns_401(client):
    r = client.post("/api/admin/verify")
    assert r.status_code == 401


def test_admin_not_configured_returns_503(client, monkeypatch):
    import api.auth as auth_mod

    monkeypatch.setattr(auth_mod, "ADMIN_API_KEY", "")
    r = client.delete("/api/players/%23TEST", headers=AUTH_HEADER)
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "admin_not_configured"


# -- Delete endpoint tests -----------------------------------------------------


class _DeleteChain:
    """Mock Supabase client that records .delete().eq().execute() calls."""

    def __init__(self):
        self.deleted_table = None
        self.deleted_eq = None

    def table(self, name):
        self.deleted_table = name
        return self

    def delete(self):
        return self

    def eq(self, col, val):
        self.deleted_eq = (col, val)
        return self

    def execute(self):
        class _Resp:
            data = [{"id": 1}]
        return _Resp()


def test_delete_player_success(client, monkeypatch):
    mock = _DeleteChain()
    monkeypatch.setattr("api.routers.players.get_db", lambda: mock)

    r = client.delete("/api/players/%23PLAYER123", headers=AUTH_HEADER)
    assert r.status_code == 204
    assert mock.deleted_table == "players"
    assert mock.deleted_eq == ("tag", "#PLAYER123")


def test_delete_war_success(client, monkeypatch):
    mock = _DeleteChain()
    monkeypatch.setattr("api.routers.wars.get_db", lambda: mock)

    r = client.delete("/api/wars/42", headers=AUTH_HEADER)
    assert r.status_code == 204
    assert mock.deleted_table == "wars"
    assert mock.deleted_eq == ("id", 42)


def test_delete_raid_success(client, monkeypatch):
    mock = _DeleteChain()
    monkeypatch.setattr("api.routers.raids.get_db", lambda: mock)

    r = client.delete("/api/raids/99", headers=AUTH_HEADER)
    assert r.status_code == 204
    assert mock.deleted_table == "capital_raids"
    assert mock.deleted_eq == ("id", 99)
