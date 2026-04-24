# packages/api/tests/integration/test_audit.py
from __future__ import annotations

from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_audit_contains_entity_create(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    await client.post("/entities", headers=headers, json={"name": "A"})
    r = await client.get("/audit", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(
        e["target_table"] == "entity" and e["action"] == "create"
        for e in body["items"]
    )


async def test_audit_filter_by_target_table(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    e = (await client.post("/entities", headers=headers, json={"name": "A"})).json()
    await client.post(
        "/properties", headers=headers,
        json={"entity_id": e["id"], "name": "P"},
    )
    r = await client.get("/audit?target_table=property", headers=headers)
    assert r.status_code == 200
    assert all(item["target_table"] == "property" for item in r.json()["items"])


async def test_audit_pagination(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    for i in range(5):
        await client.post("/entities", headers=headers, json={"name": f"E{i}"})
    r = await client.get("/audit?limit=2&offset=0", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
