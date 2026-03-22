"""Pytest configuration: test env before any `api` imports."""

from __future__ import annotations

import os

os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("COC_API_TOKEN", "test-coc-token")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-secret")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]
