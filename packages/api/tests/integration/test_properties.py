# packages/api/tests/integration/test_properties.py
from __future__ import annotations

from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_create_property(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "E"})
    eid = r.json()["id"]
    r = await client.post(
        "/properties",
        headers=headers,
        json={"entity_id": eid, "name": "Tower A", "property_type": "office"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Tower A"
    assert r.json()["property_type"] == "office"


async def test_filter_by_entity_id(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "E1"})
    e1 = r.json()["id"]
    r = await client.post("/entities", headers=headers, json={"name": "E2"})
    e2 = r.json()["id"]
    for eid, name in ((e1, "P1"), (e1, "P2"), (e2, "P3")):
        await client.post(
            "/properties", headers=headers, json={"entity_id": eid, "name": name},
        )
    r = await client.get(f"/properties?entity_id={e1}", headers=headers)
    assert r.status_code == 200
    assert sorted(p["name"] for p in r.json()) == ["P1", "P2"]


async def test_create_property_unknown_entity_422(
    client: httpx.AsyncClient,
    valuer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = valuer
    r = await client.post(
        "/properties",
        headers=headers,
        json={"entity_id": "00000000-0000-0000-0000-000000000000", "name": "X"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


async def test_viewer_cannot_create_property(
    client: httpx.AsyncClient,
    viewer: tuple[UUID, dict[str, str]],
) -> None:
    _, headers = viewer
    r = await client.post(
        "/properties",
        headers=headers,
        json={"entity_id": "00000000-0000-0000-0000-000000000000", "name": "X"},
    )
    assert r.status_code == 403
