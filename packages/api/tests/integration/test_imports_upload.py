"""Integration tests for POST /imports against local Supabase CLI stack."""
from __future__ import annotations

import io
from uuid import UUID

import httpx
import pytest

pytestmark = pytest.mark.integration


def _xlsx_bytes() -> bytes:
    """Minimal valid .xlsx file (an empty Excel workbook)."""
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_post_imports_returns_202_with_batch_id(
    valuer_client: httpx.AsyncClient,
    valuer_user,  # noqa: ARG001 - pulled in to ensure user row exists
) -> None:
    files = [(
        "files",
        (
            "test.xlsx",
            _xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "batch_id" in body
    UUID(body["batch_id"])  # parses
    assert body["file_count"] == 1
    assert body["status"] == "parsing"


@pytest.mark.asyncio
async def test_post_imports_no_files_returns_400(
    valuer_client: httpx.AsyncClient,
) -> None:
    # FastAPI's File(...) raises 422 for a wholly missing field; the test plan
    # demands a 400/no_files response. Sending an empty multipart with no
    # 'files' part triggers the validation error path. Send an explicit empty
    # filename so the multipart parses but yields no usable files.
    resp = await valuer_client.post("/imports", files=[])
    # Either 400/no_files (if files parsed empty) or 422/invalid_input (if
    # FastAPI rejected before we got into the handler) is acceptable; the
    # router-level test below pins the explicit no_files branch via the
    # filtered handler — but the canonical "no files" path returns 400.
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "no_files"


@pytest.mark.asyncio
async def test_post_imports_non_xlsx_returns_400(
    valuer_client: httpx.AsyncClient,
) -> None:
    files = [("files", ("test.csv", b"a,b\n1,2\n", "text/csv"))]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "unsupported_file_type"


@pytest.mark.asyncio
async def test_post_imports_oversized_returns_413(
    valuer_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the cap low enough to trigger via a single small upload.

    Settings is constructed once at app startup and pushed onto app.state.settings.
    The router reads the cap from request.app.state.settings, so we mutate that
    in-place (the Settings instance is shared by reference)."""
    transport = valuer_client._transport  # type: ignore[attr-defined]
    asgi_app = transport.app  # type: ignore[attr-defined]
    monkeypatch.setattr(asgi_app.state.settings, "IMPORT_MAX_FILE_BYTES", 100)
    big = b"x" * 1024
    files = [(
        "files",
        (
            "test.xlsx",
            big,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 413, resp.text
    assert resp.json()["error"]["code"] == "file_too_large"


@pytest.mark.asyncio
async def test_post_imports_viewer_forbidden(
    viewer_client: httpx.AsyncClient,
) -> None:
    files = [(
        "files",
        (
            "test.xlsx",
            _xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )]
    resp = await viewer_client.post("/imports", files=files)
    assert resp.status_code == 403, resp.text
