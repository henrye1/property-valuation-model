"""Integration tests for PATCH /imports/{batch_id}/items/{item_id}."""
from __future__ import annotations

import asyncio
import io
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _wait_for_review(client, batch_id, *, max_wait_s: float = 5.0) -> None:
    """Poll GET /imports/{id} until batch.status == 'review'.

    parse_worker runs as a BackgroundTask after the POST response; in the test
    client this may not have completed by the time we issue the next request.
    PATCH requires batch.status == 'review', so we block until the worker has
    finished (an empty xlsx still triggers mark_parse_error → set_status='review').
    """
    deadline = asyncio.get_event_loop().time() + max_wait_s
    while asyncio.get_event_loop().time() < deadline:
        detail = await client.get(f"/imports/{batch_id}")
        if detail.json()["status"] == "review":
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(
        f"batch {batch_id} did not reach 'review' within {max_wait_s}s"
    )


async def _seed_batch_with_one_item(client) -> tuple[str, str]:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    await _wait_for_review(client, batch_id)
    detail = await client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]
    return batch_id, item_id


@pytest.mark.asyncio
async def test_patch_rejected_records_resolution(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected", "resolution_notes": "bad sheet"},
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "rejected"


@pytest.mark.asyncio
async def test_patch_accepted_without_property_id_returns_422(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "accepted"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_edited_requires_inputs_and_property_id(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "edited"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_viewer_forbidden(viewer_client, valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await viewer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_unknown_item_returns_404(valuer_client) -> None:
    batch_id, _ = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{uuid4()}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_batch_not_in_review_returns_409(
    valuer_client, db_pool,
) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    # Force batch.status = 'committed' to simulate post-commit lockout.
    from uuid import UUID
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'committed' where id = $1",
            UUID(batch_id),
        )
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "batch_not_in_review"
