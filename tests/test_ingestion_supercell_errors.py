"""Supercell HTTP failures: structured log event + exception propagation."""

from __future__ import annotations

import logging

import httpx
import pytest

from ingestion.supercell_client import get_clan


def test_get_clan_503_emits_coc_http_error_event(monkeypatch, caplog):
    monkeypatch.setenv("COC_API_TOKEN", "dummy-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream maintenance")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(
        base_url="https://api.clashofclans.com/v1",
        headers={"Authorization": "Bearer dummy-token", "Accept": "application/json"},
        transport=transport,
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(httpx.HTTPStatusError):
            get_clan(client, "#ANY")

    assert any(getattr(rec, "event", None) == "coc.http.error" for rec in caplog.records)
