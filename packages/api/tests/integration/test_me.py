# packages/api/tests/integration/test_me.py
from __future__ import annotations

from uuid import UUID

import asyncpg
import httpx
import pytest

from api.config import Settings

pytestmark = pytest.mark.integration


async def test_me_requires_bearer_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "missing_token"


async def test_me_returns_user_for_existing_app_user(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.get("/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "valuer"


async def test_me_auto_provisions_new_user_as_viewer(
    client: httpx.AsyncClient,
    settings: Settings,
    pool: asyncpg.Pool,
) -> None:
    # Mint a token for a sub with no app_user row yet.
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    import jwt as jwtlib

    sub = uuid4()
    now = datetime.now(tz=UTC)
    token: str = jwtlib.encode(  # type: ignore[assignment]
        {
            "sub": str(sub),
            "email": "new@example.com",
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.SUPABASE_JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select role from public.app_user where id = $1", sub
        )
        assert row is not None
        assert row["role"] == "viewer"
