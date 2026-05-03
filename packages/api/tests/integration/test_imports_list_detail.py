"""Integration tests for GET /imports + GET /imports/{id}."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_get_imports_returns_empty_list_initially(viewer_client) -> None:
    resp = await viewer_client.get("/imports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_get_imports_lists_after_upload(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get("/imports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["id"] == batch_id for item in body["items"])
    found = next(item for item in body["items"] if item["id"] == batch_id)
    assert found["file_count"] == 1
    assert "counts" in found
    assert "pending" in found["counts"]


@pytest.mark.asyncio
async def test_get_imports_filter_by_status(valuer_client) -> None:
    resp = await valuer_client.get("/imports?status=parsing&status=review")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] in ("parsing", "review")


@pytest.mark.asyncio
async def test_get_import_detail_returns_items_inline(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get(f"/imports/{batch_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == batch_id
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 1
    assert body["items"][0]["filename"] == "a.xlsx"


@pytest.mark.asyncio
async def test_get_import_detail_404_for_unknown(valuer_client) -> None:
    resp = await valuer_client.get(
        "/imports/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
