# packages/api/tests/integration/test_snapshots.py
from __future__ import annotations

from datetime import date
from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _make_property(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    r = await client.post("/entities", headers=headers, json={"name": "E"})
    eid = r.json()["id"]
    r = await client.post(
        "/properties",
        headers=headers,
        json={"entity_id": eid, "name": "P", "property_type": "office"},
    )
    return str(r.json()["id"])


def _inputs() -> dict[str, object]:
    return {
        "valuation_date": date(2026, 1, 1).isoformat(),
        "tenants": [
            {
                "description": "Office",
                "rentable_area_m2": "100",
                "rent_per_m2_pm": "85",
                "annual_escalation_pct": "0",
            }
        ],
        "monthly_operating_expenses": "0",
        "vacancy_allowance_pct": "0",
        "cap_rate": "0.10",
    }


async def test_create_snapshot_and_get(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    r = await client.post(
        f"/properties/{pid}/snapshots", headers=headers, json=_inputs()
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "active"
    sid = body["id"]

    r = await client.get(f"/snapshots/{sid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == sid


async def test_second_snapshot_supersedes_first(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    r1 = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    s1 = r1.json()["id"]
    r2 = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    s2 = r2.json()["id"]
    assert s1 != s2

    r = await client.get(f"/snapshots/{s1}", headers=headers)
    assert r.json()["status"] == "superseded"
    r = await client.get(f"/snapshots/{s2}", headers=headers)
    assert r.json()["status"] == "active"


async def test_list_snapshots_for_property(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    r = await client.get(f"/properties/{pid}/snapshots", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_viewer_cannot_create_snapshot(
    client: httpx.AsyncClient, viewer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = viewer
    r = await client.post(
        "/properties/00000000-0000-0000-0000-000000000000/snapshots",
        headers=headers,
        json=_inputs(),
    )
    assert r.status_code == 403


async def test_snapshot_records_engine_version(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    from valuation_engine import __version__ as ev

    _, headers = valuer
    pid = await _make_property(client, headers)
    r = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    assert r.json()["engine_version"] == ev


async def test_snapshot_property_not_found_404(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    r = await client.post(
        "/properties/00000000-0000-0000-0000-000000000000/snapshots",
        headers=headers,
        json=_inputs(),
    )
    assert r.status_code == 404


async def test_snapshot_engine_error_422(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    bad = _inputs()
    bad["cap_rate"] = "0"  # engine rejects
    r = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=bad)
    assert r.status_code == 422
