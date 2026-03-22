"""Ingestion boundary: CoC-shaped JSON fixtures stay self-consistent."""

from __future__ import annotations

import json
from pathlib import Path


def test_coc_clan_minimal_fixture(repo_root):
    path = Path(repo_root) / "fixtures" / "coc_clan_minimal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tag"].startswith("#")
    assert "name" in data
    assert isinstance(data.get("memberList"), list)
