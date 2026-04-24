"""Shared pytest fixtures for the API test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]


@pytest.fixture(scope="session")
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee deterministic env vars for unit tests.

    Integration tests override these in their own conftest.
    """
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("SUPABASE_URL", "http://unused")
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        "test-secret-minimum-32-chars-long-for-hs256-signing",
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
