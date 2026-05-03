# packages/api/tests/integration/test_users.py
from __future__ import annotations

from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_users_list_contains_self(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.get("/users", headers=headers)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert "valuer@example.com" in emails
