"""asyncpg pool lifecycle + per-request connection dependency."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import asyncpg
from fastapi import Request

if TYPE_CHECKING:
    from fastapi import FastAPI


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection setup: decode jsonb / json columns to Python dicts.

    Without this, asyncpg returns jsonb columns as raw JSON-encoded strings,
    which forces every router to remember to json.loads() before validating.
    """
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def _create_pool(database_url: str) -> asyncpg.Pool:
    # min_size=1 keeps the idle footprint low on Render + Supabase free tier
    # (vs. asyncpg's default of 10). command_timeout covers statement execution,
    # not connection-acquisition wait — see get_db for that gap.
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
        init=_init_connection,
    )


@asynccontextmanager
async def lifespan_pool(app: FastAPI, database_url: str) -> AsyncIterator[None]:
    pool = await _create_pool(database_url)
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


async def get_db(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: check out a connection for this request.

    Wraps pool.acquire() with an acquisition timeout sourced from settings.
    asyncio.TimeoutError surfaces as 503 via the global exception handler.
    """
    pool: asyncpg.Pool = request.app.state.pool
    settings = request.app.state.settings
    async with pool.acquire(timeout=settings.DB_ACQUIRE_TIMEOUT_S) as conn:
        yield conn
