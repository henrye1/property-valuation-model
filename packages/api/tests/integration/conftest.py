"""Integration test fixtures.

Require a live Supabase CLI stack:
    supabase start

Env vars (set in CI via the workflow; locally via .env.test or shell):
    DATABASE_URL, SUPABASE_URL, SUPABASE_JWT_SECRET
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from api.config import Settings

pytestmark = pytest.mark.integration


def _int_settings() -> Settings:
    return Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        SUPABASE_URL=os.environ["SUPABASE_URL"],
        SUPABASE_JWT_SECRET=os.environ["SUPABASE_JWT_SECRET"],
        ALLOWED_ORIGINS="",
        LOG_LEVEL="WARNING",
        ENV="ci",
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return _int_settings()


@pytest_asyncio.fixture()
async def pool(settings: Settings) -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=1, max_size=4)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture(autouse=True)
async def _truncate(pool: asyncpg.Pool) -> AsyncIterator[None]:
    async with pool.acquire() as conn:
        await conn.execute(
            "truncate public.audit_log, public.valuation_snapshot, "
            "public.property, public.entity, public.app_user cascade"
        )
    yield


@pytest_asyncio.fixture()
async def app(settings: Settings) -> AsyncIterator[Any]:
    # Delayed import: top-level import triggers module-level Settings() construction,
    # which breaks unit test collection when env vars are absent.
    from api.main import create_app
    application = create_app(settings=settings)
    # Trigger lifespan
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture()
async def client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mint_token(settings: Settings, *, sub: UUID, email: str) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
        },
        settings.SUPABASE_JWT_SECRET.get_secret_value(),
        algorithm="HS256",
    )  # type: ignore[return-value]


@pytest_asyncio.fixture()
async def make_user(pool: asyncpg.Pool, settings: Settings) -> Any:
    """Factory: ``(email, role='valuer')`` → (user_id, Authorization header)."""

    async def _make(
        email: str = "alice@example.com", role: str = "valuer"
    ) -> tuple[UUID, dict[str, str]]:
        uid = uuid4()
        async with pool.acquire() as conn:
            await conn.execute(
                "insert into public.app_user (id, email, role, last_seen_at) "
                "values ($1, $2, $3, now())",
                uid,
                email,
                role,
            )
        token = _mint_token(settings, sub=uid, email=email)
        return uid, {"Authorization": f"Bearer {token}"}

    return _make


@pytest_asyncio.fixture()
async def valuer(make_user: Any) -> tuple[UUID, dict[str, str]]:
    return await make_user("valuer@example.com", "valuer")  # type: ignore[no-any-return]


@pytest_asyncio.fixture()
async def viewer(make_user: Any) -> tuple[UUID, dict[str, str]]:
    return await make_user("viewer@example.com", "viewer")  # type: ignore[no-any-return]
