"""Sequential mock Supabase client matching `dashboard_summary` query order."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class _ExecResult:
    __slots__ = ("data", "count")

    def __init__(self, *, data: list[Any] | None = None, count: int | None = None) -> None:
        self.data = [] if data is None else data
        self.count = count


class _MockQuery:
    def __init__(self, results: Iterator[_ExecResult]) -> None:
        self._results = results

    def select(self, *args: Any, **kwargs: Any) -> _MockQuery:
        return self

    def order(self, *args: Any, **kwargs: Any) -> _MockQuery:
        return self

    def limit(self, *args: Any, **kwargs: Any) -> _MockQuery:
        return self

    def in_(self, *args: Any, **kwargs: Any) -> _MockQuery:
        return self

    def execute(self) -> _ExecResult:
        return next(self._results)


class MockDashboardDb:
    """Yields execute() results in the same order as `api.routers.dashboard.dashboard_summary`."""

    def __init__(self, sequence: list[_ExecResult]) -> None:
        self._iter = iter(sequence)

    def table(self, _name: str) -> _MockQuery:
        return _MockQuery(self._iter)


def default_dashboard_sequence(
    *,
    recent_wars: list[dict[str, Any]] | None = None,
    recent_raids: list[dict[str, Any]] | None = None,
    counts: tuple[int, int, int, int, int] = (2, 40, 120, 1, 45),
) -> list[_ExecResult]:
    c0, c1, c2, c3, c4 = counts
    rw = recent_wars or [
        {
            "id": 1,
            "clan_tag": "#ABC",
            "opponent_name": "Opponent",
            "state": "warEnded",
            "result": "win",
            "start_time": "2025-01-01T00:00:00+00:00",
            "clan_stars": 15,
            "opponent_stars": 12,
        }
    ]
    rr = recent_raids or [
        {
            "id": 10,
            "clan_tag": "#ABC",
            "state": "ended",
            "start_time": "2025-01-02T00:00:00+00:00",
            "capital_total_loot": 1000,
            "raids_completed": 6,
        }
    ]
    return [
        _ExecResult(data=[], count=c0),
        _ExecResult(data=[], count=c1),
        _ExecResult(data=[], count=c2),
        _ExecResult(data=[], count=c3),
        _ExecResult(data=[], count=c4),
        _ExecResult(data=rw, count=None),
        _ExecResult(data=rr, count=None),
    ]
