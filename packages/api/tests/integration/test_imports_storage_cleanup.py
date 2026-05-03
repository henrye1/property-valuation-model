"""Verify storage prefix is empty after cancel + after committed transition."""
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
    deadline = asyncio.get_event_loop().time() + max_wait_s
    while asyncio.get_event_loop().time() < deadline:
        detail = await client.get(f"/imports/{batch_id}")
        if detail.json().get("status") == "review":
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"batch {batch_id} did not reach 'review' in {max_wait_s}s")


def _list_prefix(app, batch_id: str) -> list[str]:
    storage = app.state.storage
    listing = storage._client.storage.from_("imports").list(batch_id)  # type: ignore[attr-defined]
    return [obj["name"] for obj in listing]


@pytest.mark.asyncio
async def test_storage_empty_after_cancel(valuer_client, app) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    assert _list_prefix(app, batch_id), "files should exist before cancel"

    await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert _list_prefix(app, batch_id) == [], "files should be cleared on cancel"


@pytest.mark.asyncio
async def test_storage_empty_after_committed(valuer_client, app) -> None:
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
    assert resp.json()["batch_status"] == "committed"
    assert _list_prefix(app, batch_id) == [], \
        "files should be cleared when batch flips to committed"
