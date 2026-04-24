from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_healthz(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["api_version"]
    assert body["engine_version"]
