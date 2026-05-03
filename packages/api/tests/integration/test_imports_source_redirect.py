"""Integration tests for GET /imports/{batch_id}/items/{item_id}/source."""
from __future__ import annotations

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


@pytest.mark.asyncio
async def test_source_returns_307_with_signed_url(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "/storage/v1/object/sign/imports/" in location
    assert "token=" in location


@pytest.mark.asyncio
async def test_source_after_cancel_returns_410(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    await valuer_client.post(f"/imports/{batch_id}/cancel")

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "source_unavailable"


@pytest.mark.asyncio
async def test_source_unknown_item_returns_404(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{uuid4()}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_source_viewer_can_download(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    resp = await viewer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 307
