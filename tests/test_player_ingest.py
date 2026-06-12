"""Tests for player ingest change detection and ingestion DB caches."""

from __future__ import annotations

from shared.player_ingest import (
    player_ingest_fingerprint,
    player_row_from_coc,
    player_rows_unchanged,
)

from ingestion import db_cache


def test_player_rows_unchanged_ignores_updated_at():
    coc = {
        "tag": "#ABC",
        "name": "Player",
        "clan": {"tag": "#CLAN"},
        "townHallLevel": 16,
        "expLevel": 200,
        "trophies": 5000,
        "bestTrophies": 5100,
        "warStars": 100,
        "attackWins": 10,
        "defenseWins": 5,
        "role": "member",
        "warPreference": "in",
        "clanCapitalContributions": 1000,
        "leagueTier": {"id": 105000036, "name": "Legend League"},
    }
    row = player_row_from_coc(coc)
    existing = {**row, "updated_at": "2026-01-01T00:00:00+00:00"}
    assert player_rows_unchanged(existing, row)
    assert not player_rows_unchanged(existing, {**row, "trophies": 4999})


def test_player_fingerprint_stable():
    row = {
        "tag": "#X",
        "name": "A",
        "clan_tag": None,
        "town_hall_level": 1,
        "exp_level": 1,
        "trophies": 0,
        "best_trophies": 0,
        "war_stars": 0,
        "attack_wins": 0,
        "defense_wins": 0,
        "role": None,
        "war_preference": None,
        "clan_capital_contributions": 0,
        "league_name": None,
        "league_tier_id": None,
    }
    assert player_ingest_fingerprint(row) == player_ingest_fingerprint(dict(row))


class _Resp:
    def __init__(self, data):
        self.data = data


class _Chain:
    def __init__(self, pages: list[list[dict]]):
        self._pages = pages
        self._start = 0
        self._page_size = 1000

    def table(self, _name: str):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def in_(self, *_a, **_k):
        return self

    def range(self, start: int, end: int):
        self._start = start
        self._page_size = end - start + 1
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        page_num = self._start // self._page_size
        if page_num < len(self._pages):
            return _Resp(self._pages[page_num])
        return _Resp([])


def test_legends_snapshot_unchanged_after_warm():
    db_cache.reset_ingestion_caches()
    db = _Chain([[{"player_tag": "#P1", "trophies": 5000}]])
    db_cache.warm_legends_snapshot_cache(db, ["#P1", "#P2"], "2026-04-26")
    assert db_cache.legends_snapshot_unchanged("#P1", "2026-04-26", 5000)
    assert not db_cache.legends_snapshot_unchanged("#P1", "2026-04-26", 5001)
    assert not db_cache.legends_snapshot_unchanged("#P2", "2026-04-26", 5000)
