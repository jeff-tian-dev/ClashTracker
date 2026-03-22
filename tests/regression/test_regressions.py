"""
Regression tests: add a focused case each time a production bug is fixed.

Keep names descriptive (what broke + expected behavior) so logs and failures read clearly.
"""

from __future__ import annotations


def test_x_request_id_header_is_always_present_for_tracing(client):
    """Regression: every response should carry a correlation id for log lookup."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")


def test_client_supplied_x_request_id_is_preserved(client):
    r = client.get("/health", headers={"X-Request-Id": "client-fixed-trace-id"})
    assert r.headers.get("x-request-id") == "client-fixed-trace-id"
