"""Contract validation against committed JSON fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from api.schemas.contract import DashboardResponse


def test_dashboard_fixture_matches_pydantic_contract(repo_root):
    path = Path(repo_root) / "fixtures" / "api_dashboard_sample.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    model = DashboardResponse.model_validate(raw)
    assert model.total_clans == 2
    assert model.recent_wars[0].id == 1  # type: ignore[union-attr]
