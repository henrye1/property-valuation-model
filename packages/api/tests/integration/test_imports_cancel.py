"""Integration tests for POST /imports/{batch_id}/cancel."""
from __future__ import annotations

import asyncio
import io

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _wait_for_review(client, batch_id: str, *, max_wait_s: float = 5.0) -> None:
    """Poll until batch.status flips from 'parsing' to 'review' (parse_worker done)."""
    deadline = asyncio.get_event_loop().time() + max_wait_s
    while asyncio.get_event_loop().time() < deadline:
        detail = await client.get(f"/imports/{batch_id}")
        if detail.json().get("status") == "review":
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"batch {batch_id} did not reach 'review' in {max_wait_s}s")


@pytest.mark.asyncio
async def test_cancel_review_batch_succeeds(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    await _wait_for_review(valuer_client, batch_id)

    resp = await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    after = await valuer_client.get(f"/imports/{batch_id}")
    assert after.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_committed_returns_409(valuer_client, db_pool) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    from uuid import UUID
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'committed' where id = $1",
            UUID(batch_id),  # asyncpg strict UUID typing — see Task 19 note.
        )
    resp = await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cancel_viewer_forbidden(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    resp = await viewer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 403
