"""Invalid input and dependency failures return actionable responses."""

from __future__ import annotations

import pytest

from tests.test_admin import AUTH_HEADER
from postgrest.exceptions import APIError


def test_invalid_pagination_returns_422_with_request_id(client):
    r = client.get("/api/players?page=0")
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body
    assert "request_id" in body
    assert "hint" in body


def test_get_db_without_credentials_raises_clear_error(monkeypatch):
    # `database` binds config at import; patch the module globals `get_db` reads.
    import api.database as dbmod

    monkeypatch.setattr(dbmod, "SUPABASE_KEY", "")
    with pytest.raises(RuntimeError, match="database.unconfigured"):
        dbmod.get_db()


def test_player_not_found_maps_pgrst116_to_404(client, monkeypatch):
    class _Chain:
        def table(self, _n):
            return self

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def single(self):
            return self

        def execute(self):
            raise APIError(
                {
                    "code": "PGRST116",
                    "message": "JSON object requested, multiple (or no) rows returned",
                }
            )

    monkeypatch.setattr("api.routers.players.get_db", lambda: _Chain())

    r = client.get("/api/players/%23NOTFOUND")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["error"] == "not_found"
    assert detail["resource"] == "player"


def test_tracked_clan_duplicate_returns_structured_409(client, monkeypatch):
    class _Ins:
        def table(self, _n):
            return self

        def insert(self, _row):
            return self

        def execute(self):
            raise Exception('duplicate key value violates unique constraint "tracked_clans_clan_tag_key"')

    monkeypatch.setattr("api.routers.tracked_clans.get_db", lambda: _Ins())

    r = client.post("/api/tracked-clans", headers=AUTH_HEADER, json={"clan_tag": "#DUPE"})
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "already_tracked"
