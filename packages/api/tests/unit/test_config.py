# packages/api/tests/unit/test_config.py
from __future__ import annotations

import pytest

from api.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "a" * 40)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.test,http://b.test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENV", "prod")

    s = Settings()

    assert s.DATABASE_URL == "postgresql://u:p@h/d"
    assert s.SUPABASE_URL == "http://localhost:54321"
    assert s.SUPABASE_JWT_SECRET == "a" * 40
    assert s.allowed_origins_list == ["http://a.test", "http://b.test"]
    assert s.LOG_LEVEL == "DEBUG"
    assert s.ENV == "prod"


def test_settings_allowed_origins_empty_string_yields_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    s = Settings()
    assert s.allowed_origins_list == []


def test_settings_short_jwt_secret_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "short")
    with pytest.raises(ValueError):
        Settings()
