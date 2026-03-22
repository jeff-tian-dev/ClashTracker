"""Minimal smoke: app boots and core routes respond."""

from __future__ import annotations


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_schema_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "Clash Tracker API"
    assert "/api/dashboard" in spec["paths"]
