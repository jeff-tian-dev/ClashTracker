"""Unit tests for legends leaderboard battle aggregation + API validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.routers.legends import (
    _LEGENDS_BATTLES_PAGE,
    _aggregate_legends_day_battles,
    _fetch_legends_battles_for_day,
    _is_stale_left_roster,
)


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

        def lt(self, *_a, **_k):
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def range(self, *_a, **_k):
            return self

        @property
        def not_(self):
            class _Not:
                def in_(_self, *_a, **_k):
                    return self

                def is_(_self, *_a, **_k):
                    return self

            return _Not()

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


class _PagingChain:
    """Fake DB chain for `_fetch_legends_battles_for_day` that simulates PostgREST paging.

    Supports `.not_.in_(col, values)` to verify stale-tag exclusion pushes down to the query.
    """

    def __init__(self, all_rows: list[dict]):
        self._all = all_rows
        self._range: tuple[int, int] | None = None
        self._not_in: tuple[str, list[str]] | None = None

    def table(self, _name):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    @property
    def not_(self):
        parent = self

        class _Not:
            def in_(self, col: str, values):
                parent._not_in = (col, list(values))
                return parent

        return _Not()

    def range(self, lo: int, hi: int):
        self._range = (lo, hi)
        return self

    def execute(self):
        assert self._range is not None, "pagination helper must call .range()"
        lo, hi = self._range
        self._range = None
        rows = self._all
        if self._not_in is not None:
            col, values = self._not_in
            excluded = set(values)
            rows = [r for r in rows if r.get(col) not in excluded]
        return _Resp(rows[lo : hi + 1])


def test_fetch_legends_battles_pages_past_1000_row_cap():
    """Legends days over PostgREST's 1000-row cap must page to completion, not truncate silently."""

    total = _LEGENDS_BATTLES_PAGE + 250
    all_rows = [
        {"player_tag": f"#P{i:04d}", "is_attack": (i % 2 == 0), "trophies": 10}
        for i in range(total)
    ]

    rows = _fetch_legends_battles_for_day(_PagingChain(all_rows), "2026-04-19")
    assert len(rows) == total, "paginated fetch must return every row across pages"
    assert rows[0]["player_tag"] == "#P0000"
    assert rows[-1]["player_tag"] == f"#P{total - 1:04d}"


def test_fetch_legends_battles_excludes_stale_tags_at_db_layer():
    """exclude_tags must push to a WHERE NOT IN on the fetch, not post-filter in Python."""

    all_rows = [
        {"player_tag": "#ACTIVE", "is_attack": True, "trophies": 20},
        {"player_tag": "#STALE", "is_attack": True, "trophies": 30},
        {"player_tag": "#ACTIVE", "is_attack": False, "trophies": 15},
        {"player_tag": "#STALE", "is_attack": False, "trophies": 25},
    ]

    chain = _PagingChain(all_rows)
    rows = _fetch_legends_battles_for_day(chain, "2026-04-19", exclude_tags={"#STALE"})

    assert chain._not_in == ("player_tag", ["#STALE"]), "exclusion must reach .not_.in_() on the query"
    assert {r["player_tag"] for r in rows} == {"#ACTIVE"}
    assert len(rows) == 2


def test_is_stale_left_roster_threshold_boundary():
    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    assert _is_stale_left_roster(None, now=now) is False
    assert _is_stale_left_roster("", now=now) is False
    assert _is_stale_left_roster("not-a-date", now=now) is False
    assert (
        _is_stale_left_roster((now - timedelta(days=2, hours=23)).isoformat(), now=now) is False
    )
    assert _is_stale_left_roster((now - timedelta(days=3, hours=1)).isoformat(), now=now) is True


def _make_roster_chain(
    players_rows: list[dict],
    tracked_rows: list[dict],
    battles_rows: list[dict],
):
    """Fake DB chain that honors `.not_.in_` / `.lt` / `.in_` filters per table.

    The leaderboard endpoint now pushes the stale-leaver filter into the DB layer,
    so our fakes must actually apply the filters to validate end-to-end behavior.
    """

    class _Chain:
        def __init__(self):
            self._table: str | None = None
            self._filters: list[tuple] = []

        def table(self, name: str):
            self._table = name
            self._filters = []
            return self

        def select(self, *_a, **_k):
            return self

        def ilike(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def in_(self, col: str, values):
            self._filters.append(("in", col, list(values)))
            return self

        def lt(self, col: str, value):
            self._filters.append(("lt", col, value))
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def range(self, *_a, **_k):
            return self

        @property
        def not_(chain):  # noqa: N805
            class _Not:
                def in_(self, col: str, values):
                    chain._filters.append(("not_in", col, list(values)))
                    return chain

                def is_(self, col: str, value):
                    chain._filters.append(("not_is", col, value))
                    return chain

            return _Not()

        def _source(self) -> list[dict]:
            if self._table == "legends_battles":
                return list(battles_rows)
            if self._table == "tracked_players":
                return list(tracked_rows)
            if self._table == "players":
                return list(players_rows)
            if self._table == "legends_day_snapshots":
                return []
            return []

        def _apply_filters(self, rows: list[dict]) -> list[dict]:
            out = rows
            for f in self._filters:
                if f[0] == "in":
                    _, col, values = f
                    allow = set(values)
                    out = [r for r in out if r.get(col) in allow]
                elif f[0] == "not_in":
                    _, col, values = f
                    deny = set(values)
                    out = [r for r in out if r.get(col) not in deny]
                elif f[0] == "lt":
                    _, col, value = f
                    out = [r for r in out if r.get(col) is not None and r.get(col) < value]
                elif f[0] == "not_is":
                    _, col, value = f
                    if value is None:
                        out = [r for r in out if r.get(col) is not None]
            return out

        def execute(self):
            return _Resp(self._apply_filters(self._source()))

    return _Chain()


def test_leaderboard_hides_players_who_left_roster_over_3_days_ago(client, monkeypatch):
    """Non-pinned players whose left_tracked_roster_at is >3 days ago must not appear.

    Also verifies the filter pushes to the DB layer: `#STALE`'s battle rows must be
    excluded before aggregation, not just from the final response.
    """

    now = datetime.now(timezone.utc)
    stale_iso = (now - timedelta(days=4)).isoformat()
    fresh_iso = (now - timedelta(hours=12)).isoformat()
    long_gone_iso = (now - timedelta(days=10)).isoformat()

    players_rows = [
        {"tag": "#STALE", "name": "Stale", "trophies": 5000, "left_tracked_roster_at": stale_iso},
        {"tag": "#FRESH", "name": "Fresh", "trophies": 5100, "left_tracked_roster_at": fresh_iso},
        {
            "tag": "#PINNED_GONE",
            "name": "PinnedGone",
            "trophies": 5200,
            "left_tracked_roster_at": long_gone_iso,
        },
    ]
    tracked_rows = [
        {"player_tag": "#PINNED_GONE", "tracking_group": "external", "legends_bracket": 1},
    ]
    battles_rows = [
        {"player_tag": "#STALE", "is_attack": True, "trophies": 30},
        {"player_tag": "#STALE", "is_attack": False, "trophies": 10},
        {"player_tag": "#FRESH", "is_attack": True, "trophies": 25},
        {"player_tag": "#FRESH", "is_attack": False, "trophies": 15},
        {"player_tag": "#PINNED_GONE", "is_attack": True, "trophies": 40},
    ]

    monkeypatch.setattr(
        "api.routers.legends.fetch_legends_roster_tags",
        lambda _db: ["#STALE", "#FRESH", "#PINNED_GONE"],
    )
    monkeypatch.setattr(
        "api.routers.legends.get_db",
        lambda: _make_roster_chain(players_rows, tracked_rows, battles_rows),
    )

    r = client.get("/api/legends")
    assert r.status_code == 200
    rows = r.json()["data"]
    tags = {row["player_tag"] for row in rows}

    assert "#STALE" not in tags, "player who left >3 days ago and is not pinned must be hidden"
    assert "#FRESH" in tags, "recently-left player must still appear"
    assert "#PINNED_GONE" in tags, "always-tracked pins are exempt even when long gone"


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
