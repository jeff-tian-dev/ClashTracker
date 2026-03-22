"""Response shapes at the API boundary (keep aligned with apps/web/src/lib/api.ts)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str


class WarSummary(BaseModel):
    model_config = {"extra": "allow"}

    id: int
    clan_tag: str
    opponent_name: str
    state: str
    result: str | None = None
    start_time: str | None = None
    clan_stars: int | None = None
    opponent_stars: int | None = None


class RaidSummary(BaseModel):
    model_config = {"extra": "allow"}

    id: int
    clan_tag: str
    state: str
    start_time: str | None = None
    capital_total_loot: int | None = None
    raids_completed: int | None = None


class DashboardResponse(BaseModel):
    total_clans: int = Field(ge=0)
    total_players: int = Field(ge=0)
    total_wars: int = Field(ge=0)
    active_wars: int = Field(ge=0)
    total_raids: int = Field(ge=0)
    recent_wars: list[WarSummary | dict[str, Any]]
    recent_raids: list[RaidSummary | dict[str, Any]]

    @field_validator("recent_wars", "recent_raids", mode="before")
    @classmethod
    def _must_be_list(cls, v: object) -> object:
        if v is None:
            raise ValueError("expected a list from database, got None (invariant violation)")
        if not isinstance(v, list):
            raise TypeError(f"expected list, got {type(v).__name__}")
        return v


class PaginatedPlayersResponse(BaseModel):
    data: list[dict[str, Any]]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
