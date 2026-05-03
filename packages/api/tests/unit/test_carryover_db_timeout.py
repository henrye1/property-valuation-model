"""Verify pool.acquire() is called with an acquisition timeout, and that
asyncio.TimeoutError is mapped to HTTP 503."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.db import get_db
from api.errors import install_exception_handlers


@pytest.mark.asyncio
async def test_get_db_passes_acquire_timeout() -> None:
    """The get_db dependency must call pool.acquire(timeout=...) — never bare."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    # Configure the context manager protocol on whatever acquire() returns.
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value="conn-sentinel")
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm

    request = MagicMock()
    request.app.state.pool = pool
    # get_db reads settings.DB_ACQUIRE_TIMEOUT_S off app.state — give it a real number
    # so the kwargs comparison below is meaningful (MagicMock > int raises TypeError).
    request.app.state.settings.DB_ACQUIRE_TIMEOUT_S = 10.0

    gen = get_db(request)
    conn = await gen.__anext__()
    try:
        assert conn == "conn-sentinel"
    finally:
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    # The crux: timeout kwarg was passed.
    call = pool.acquire.call_args
    assert "timeout" in call.kwargs, "pool.acquire() must be called with a timeout kwarg"
    assert call.kwargs["timeout"] > 0


def test_timeout_error_maps_to_503() -> None:
    """asyncio.TimeoutError raised in a route maps to envelope 503."""
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom")
    async def _boom() -> Any:
        # asyncio.TimeoutError is an alias for builtin TimeoutError in Python 3.11+,
        # so the @app.exception_handler(asyncio.TimeoutError) registration catches both.
        # Use the builtin form to satisfy ruff UP041.
        raise TimeoutError("pool exhausted")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {
        "error": {
            "code": "service_unavailable",
            "message": "Database connection unavailable; please retry shortly.",
            "details": {},
        }
    }
