# packages/api/tests/integration/test_portfolio.py
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _seed(client: httpx.AsyncClient, headers: dict[str, str]) -> list[str]:
    """Two entities, four properties, snapshots at varying values."""
    ids: list[str] = []
    e1 = (await client.post("/entities", headers=headers, json={"name": "E1"})).json()["id"]
    e2 = (await client.post("/entities", headers=headers, json={"name": "E2"})).json()["id"]
    for eid, name, ptype, rent, cap, dt in (
        (e1, "P1", "office", "85", "0.10", "2025-06-01"),
        (e1, "P2", "retail", "120", "0.09", "2025-06-01"),
        (e2, "P3", "industrial", "50", "0.12", "2025-06-01"),
        (e2, "P4", "office", "100", "0.11", "2026-01-01"),
    ):
        p = (
            await client.post(
                "/properties",
                headers=headers,
                json={"entity_id": eid, "name": name, "property_type": ptype},
            )
        ).json()["id"]
        ids.append(p)
        await client.post(
            f"/properties/{p}/snapshots",
            headers=headers,
            json={
                "valuation_date": dt,
                "tenants": [
                    {
                        "description": "T",
                        "rentable_area_m2": "100",
                        "rent_per_m2_pm": rent,
                        "annual_escalation_pct": "0",
                    }
                ],
                "monthly_operating_expenses": "500",
                "vacancy_allowance_pct": "0.05",
                "cap_rate": cap,
            },
        )
    return ids


async def test_portfolio_summary_structure(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/summary", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["property_count"] == 4
    assert body["entity_count"] == 2
    assert Decimal(body["total_market_value"]) > 0
    types = {row["type"] for row in body["value_by_type"]}
    assert {"office", "retail", "industrial"} <= types
    assert 0 < len(body["top_properties"]) <= 10


async def test_portfolio_top_limit(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/summary?limit=2", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["top_properties"]) == 2


async def test_portfolio_timeseries_year(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/timeseries", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["bucket"] == "year"
    years = {p["bucket_date"][:4] for p in body["points"]}
    assert {"2025", "2026"} <= years


async def test_portfolio_empty_returns_zero_totals(
    client: httpx.AsyncClient, valuer: tuple[UUID, dict[str, str]]
) -> None:
    _, headers = valuer
    r = await client.get("/portfolio/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["property_count"] == 0
    assert Decimal(r.json()["total_market_value"]) == Decimal("0")
