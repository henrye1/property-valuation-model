"""asyncpg pool lifecycle + per-request connection dependency."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import asyncpg
from fastapi import Request

if TYPE_CHECKING:
    from fastapi import FastAPI


async def _create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
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
    """FastAPI dependency: check out a connection for this request."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        yield conn
