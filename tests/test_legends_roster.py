"""Unit tests for tracked Legends roster scope."""

from __future__ import annotations

from shared.legends_roster import (
    fetch_legends_roster_tags,
    player_in_tracked_legends_scope,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _Chain:
    def __init__(self, pages: list[list[dict]]):
        self._pages = pages
        self._page_idx = 0

    def table(self, _name: str):
        return self

    def select(self, *_a, **_k):
        return self

    def ilike(self, *_a, **_k):
        return self

    def or_(self, *_a, **_k):
        return self

    def range(self, start: int, end: int):
        page_size = end - start + 1
        self._start = start
        self._page_size = page_size
        return self

    def execute(self):
        page_num = self._start // self._page_size
        if page_num < len(self._pages):
            return _Resp(self._pages[page_num])
        return _Resp([])


def test_player_in_tracked_scope_active_tags():
    row = {"tag": "#A", "clan_tag": "#CLAN", "left_tracked_roster_at": "2026-01-01T00:00:00+00:00"}
    assert player_in_tracked_legends_scope(row, set(), set(), active_tags={"#A"})
    assert not player_in_tracked_legends_scope(row, set(), set(), active_tags=set())


def test_player_in_tracked_scope_always_tracked_pin():
    row = {"tag": "#PIN", "clan_tag": None, "left_tracked_roster_at": "2026-01-01T00:00:00+00:00"}
    assert player_in_tracked_legends_scope(row, set(), {"#PIN"})


def test_player_in_tracked_scope_clan_member_on_roster():
    row = {"tag": "#MEM", "clan_tag": "#JULY", "left_tracked_roster_at": None}
    assert player_in_tracked_legends_scope(row, {"#JULY"}, set())


def test_player_in_tracked_scope_ex_member_not_pinned():
    row = {"tag": "#GONE", "clan_tag": "#JULY", "left_tracked_roster_at": "2026-01-01T00:00:00+00:00"}
    assert not player_in_tracked_legends_scope(row, {"#JULY"}, set())


def test_fetch_legends_roster_tags_excludes_tier_2(monkeypatch):
    players_page = [
        {
            "tag": "#LL1",
            "league_name": "Legend League 1",
            "league_tier_id": 105000036,
            "clan_tag": "#JULY",
            "left_tracked_roster_at": None,
        },
        {
            "tag": "#LL2",
            "league_name": "Legend League 2",
            "league_tier_id": 105000035,
            "clan_tag": "#JULY",
            "left_tracked_roster_at": None,
        },
    ]
    db = _Chain([players_page])
    monkeypatch.setattr(
        "shared.legends_roster.fetch_tracked_clan_tags",
        lambda _db: {"#JULY"},
    )
    monkeypatch.setattr(
        "shared.legends_roster.fetch_tracked_player_tags",
        lambda _db: set(),
    )
    tags = fetch_legends_roster_tags(db)
    assert tags == ["#LL1"]


def test_fetch_legends_roster_tags_filters_untracked(monkeypatch):
    players_page = [
        {
            "tag": "#TRACKED",
            "league_name": "Legend League",
            "clan_tag": "#JULY",
            "left_tracked_roster_at": None,
        },
        {
            "tag": "#UNTRACKED",
            "league_name": "Legend League",
            "clan_tag": "#OTHER",
            "left_tracked_roster_at": None,
        },
    ]
    db = _Chain([players_page])

    monkeypatch.setattr(
        "shared.legends_roster.fetch_tracked_clan_tags",
        lambda _db: {"#JULY"},
    )
    monkeypatch.setattr(
        "shared.legends_roster.fetch_tracked_player_tags",
        lambda _db: set(),
    )

    tags = fetch_legends_roster_tags(db)
    assert tags == ["#TRACKED"]


def test_fetch_legends_roster_tags_with_active_tags():
    players_page = [
        {
            "tag": "#IN",
            "league_name": "Legend League",
            "clan_tag": "#JULY",
            "left_tracked_roster_at": None,
        },
        {
            "tag": "#OUT",
            "league_name": "Legend League",
            "clan_tag": "#OTHER",
            "left_tracked_roster_at": None,
        },
    ]
    db = _Chain([players_page])

    tags = fetch_legends_roster_tags(db, active_tags={"#IN"})
    assert tags == ["#IN"]
