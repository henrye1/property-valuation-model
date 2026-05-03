"""Integration tests for POST /imports/{batch_id}/commit.

Tests the happy path (one item, accepted with auto-link) plus failure
collection and idempotency."""
from __future__ import annotations

import asyncio
import io
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _wait_for_review(client, batch_id: str, *, max_wait_s: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + max_wait_s
    while asyncio.get_event_loop().time() < deadline:
        detail = await client.get(f"/imports/{batch_id}")
        if detail.json().get("status") == "review":
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"batch {batch_id} did not reach 'review' in {max_wait_s}s")


async def _seed_property(client, name: str = "55 Empire Road") -> str:
    ent = await client.post("/entities",
                            json={"name": "Empire Road Trust",
                                  "registration_number": None,
                                  "notes": None})
    assert ent.status_code == 201, ent.text
    eid = ent.json()["id"]
    prop = await client.post("/properties",
                             json={"entity_id": eid, "name": name,
                                   "address": "55 Empire Rd, Sandton",
                                   "property_type": "office", "notes": None})
    assert prop.status_code == 201, prop.text
    return prop.json()["id"]


@pytest.mark.asyncio
async def test_commit_with_no_items_to_commit_marks_terminal_when_empty(
    valuer_client,
) -> None:
    """An empty batch (all items rejected) flips to committed."""
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    await _wait_for_review(valuer_client, batch_id)
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # Reject the only item so the batch becomes terminal.
    await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )

    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch_status"] == "committed"
    assert body["summary"]["committed"] == 0


@pytest.mark.asyncio
async def test_commit_no_property_link_returns_failure(
    valuer_client, db_pool,
) -> None:
    """An accepted item with no property link surfaces in failures, not 500.

    Bypasses the PATCH validator by going direct-to-DB to set up a
    'broken' row state — defence-in-depth check on commit_worker."""
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    await _wait_for_review(valuer_client, batch_id)
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # Force resolution='accepted' with NULL resolved_property_id by
    # going around the PATCH validator (defence-in-depth on commit_worker).
    parsed_inputs = (
        '{"valuation_date": "2026-03-15", '
        '"tenants": [{"description":"T1","rentable_area_m2":"100",'
        '"rent_per_m2_pm":"150","annual_escalation_pct":"0"}], '
        '"parking": [], "monthly_operating_expenses":"10000", '
        '"vacancy_allowance_pct":"0.05", "cap_rate":"0.10"}'
    )
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_item set resolution = 'accepted', "
            "resolved_property_id = null, "
            "parsed_inputs_json = $2::jsonb where id = $1",
            UUID(item_id),
            parsed_inputs,
        )

    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["failed"] == 1
    assert body["failures"][0]["reason"] == "no_property_link"


@pytest.mark.asyncio
async def test_commit_happy_path_creates_snapshot(valuer_client) -> None:
    """Accepted item with valid inputs + property link → committed snapshot."""
    pid = await _seed_property(valuer_client, name=f"Test Prop {uuid4()}")
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    await _wait_for_review(valuer_client, batch_id)
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # PATCH to edited with valid inputs + property link.
    edit_resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={
            "resolution": "edited",
            "resolved_property_id": pid,
            "resolved_inputs": {
                "valuation_date": "2026-03-15",
                "tenants": [{
                    "description": "T1",
                    "rentable_area_m2": "100",
                    "rent_per_m2_pm": "150",
                    "annual_escalation_pct": "0.08",
                    "next_escalation_date": None,
                    "lease_period_text": None,
                    "lease_expiry_date": None,
                }],
                "parking": [],
                "monthly_operating_expenses": "10000",
                "vacancy_allowance_pct": "0.05",
                "cap_rate": "0.10",
            },
        },
    )
    assert edit_resp.status_code == 200, edit_resp.text

    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["committed"] == 1
    assert body["summary"]["failed"] == 0
    assert body["batch_status"] == "committed"


@pytest.mark.asyncio
async def test_commit_batch_not_in_review_returns_409(
    valuer_client, db_pool,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'cancelled' where id = $1",
            UUID(batch_id),
        )
    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_commit_viewer_forbidden(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    resp = await viewer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 403
