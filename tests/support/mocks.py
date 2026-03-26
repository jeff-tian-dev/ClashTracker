"""Reusable Supabase mock classes for API router tests.

These reduce the boilerplate of hand-rolling chain-style mocks in every
individual test function.  Each mock records its calls so tests can assert
on what the router sent to Supabase without hitting a real database.
"""

from __future__ import annotations

from typing import Any


class InsertMock:
    """Mock for ``db.table(name).insert(row).execute()``."""

    def __init__(self) -> None:
        self.inserted: dict | None = None

    def table(self, _name: str):
        return self

    def insert(self, row: dict):
        self.inserted = row
        return self

    def execute(self):
        row = self.inserted or {}
        return type("R", (), {"data": [row]})()


class DeleteChainMock:
    """Mock for ``db.table(name).delete().eq(col, val).execute()``."""

    def __init__(self) -> None:
        self.eq_calls: list[tuple[str, Any]] = []
        self.deleted_table: str | None = None

    def table(self, name: str):
        self.deleted_table = name
        return self

    def delete(self):
        return self

    def eq(self, col: str, val: Any):
        self.eq_calls.append((col, val))
        return self

    def execute(self):
        return type("R", (), {"data": []})()


class PlayersLookupMock:
    """Mock for ``db.table("players").select("name").eq("tag", t).limit(1).execute()``."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rows})()


class MultiTableMock:
    """Route ``db.table(name)`` to different mocks per table name."""

    def __init__(self, table_mocks: dict[str, Any]) -> None:
        self._table_mocks = table_mocks

    def table(self, name: str):
        if name in self._table_mocks:
            return self._table_mocks[name]
        raise AssertionError(f"unexpected table {name!r}")
