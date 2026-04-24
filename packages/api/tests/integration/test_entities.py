# packages/api/tests/integration/test_entities.py
from __future__ import annotations

from uuid import UUID

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_create_and_list_entity(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "Acme"})
    assert r.status_code == 201
    assert r.json()["name"] == "Acme"

    r = await client.get("/entities", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_viewer_cannot_create_entity(
    client: httpx.AsyncClient,
    viewer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = viewer
    r = await client.post("/entities", headers=headers, json={"name": "Acme"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_patch_entity_name_only(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.patch(f"/entities/{eid}", headers=headers, json={"name": "B"})
    assert r.status_code == 200
    assert r.json()["name"] == "B"


async def test_patch_empty_body_422(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.patch(f"/entities/{eid}", headers=headers, json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


async def test_delete_entity_soft(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.delete(f"/entities/{eid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["deleted_at"] is not None

    # Default list hides soft-deleted
    r = await client.get("/entities", headers=headers)
    assert r.json() == []

    # include_deleted shows it
    r = await client.get("/entities?include_deleted=true", headers=headers)
    assert len(r.json()) == 1


async def test_delete_entity_with_live_property_409(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
    pool: asyncpg.Pool,
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "insert into public.property (entity_id, name) values ($1, $2)",
            eid,
            "P",
        )
    r = await client.delete(f"/entities/{eid}", headers=headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "has_live_children"
    assert r.json()["error"]["details"]["blocking_count"] == 1


async def test_entity_audit_trail_written(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
    pool: asyncpg.Pool,
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select action from public.audit_log where target_id = $1 order by created_at asc",
            eid,
        )
    assert [dict(r)["action"] for r in rows] == ["create"]
