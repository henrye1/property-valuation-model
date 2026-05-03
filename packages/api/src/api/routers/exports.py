"""HTTP layer for /snapshots/{id}/export.{pdf,xlsx}.

Both endpoints are GETs cached via Cache-Control: immutable + ETag = snapshot.id.
Snapshots are immutable, so the cache is trivially correct.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from api.auth import current_user
from api.db import get_db
from api.errors import APIError
from api.queries import snapshot as q_snapshot
from api.schemas.user import AppUser
from api.services import exports as exports_svc

try:
    from valuation_engine.excel import render_workbook
    from valuation_engine.models import ValuationInput, ValuationResult
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

router = APIRouter(tags=["exports"])

_FS_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WS_RUN = re.compile(r"\s+")


def _slugify_for_disposition(s: str) -> str:
    cleaned = _FS_ILLEGAL.sub("", s)
    return _WS_RUN.sub("_", cleaned).strip("._-") or "untitled"


def _safe_filename(snapshot: object, ext: str) -> str:
    parts = [
        snapshot.entity_name,  # type: ignore[attr-defined]
        snapshot.property_name,  # type: ignore[attr-defined]
        snapshot.valuation_date.isoformat(),  # type: ignore[attr-defined]
    ]
    base = "_".join(_slugify_for_disposition(p) for p in parts)
    if len(base) > 200:
        base = base[:200]
    return f"{base}.{ext}"


def _decode_jsonb(d: dict[str, Any], *fields: str) -> None:
    """Defensive: asyncpg's jsonb codec doesn't reliably decode table-sourced
    columns in 0.31. Same pattern as routers/audit._row_to_entry and
    routers/imports._decode_jsonb."""
    for k in fields:
        v = d.get(k)
        if isinstance(v, str):
            d[k] = json.loads(v)


def _xlsx_bytes(snapshot_row: dict[str, Any]) -> bytes:
    """Engine renderer writes to a path; read back as bytes."""
    _decode_jsonb(snapshot_row, "inputs_json", "result_json")
    inputs = ValuationInput.model_validate(snapshot_row["inputs_json"])
    result = ValuationResult.model_validate(snapshot_row["result_json"])
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = Path(tf.name)
    try:
        render_workbook(
            path,
            building_name=snapshot_row["property_name"],
            inputs=inputs,
            result=result,
        )
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


@router.get("/snapshots/{snapshot_id}/export.xlsx")
async def get_snapshot_xlsx(
    snapshot_id: UUID,
    request: Request,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Response:
    row = await q_snapshot.get_with_property(conn, snapshot_id)
    if row is None:
        raise APIError(
            status_code=404, code="not_found", message="Snapshot not found.",
        )

    etag = f'"{row["id"]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    snapshot_row = dict(row)
    workbook_bytes = await run_in_threadpool(_xlsx_bytes, snapshot_row)
    snapshot_obj = type("S", (), snapshot_row)
    filename = _safe_filename(snapshot_obj, "xlsx")
    return Response(
        content=workbook_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )


@router.get("/snapshots/{snapshot_id}/export.pdf")
async def get_snapshot_pdf(
    snapshot_id: UUID,
    request: Request,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Response:
    row = await q_snapshot.get_with_property(conn, snapshot_id)
    if row is None:
        raise APIError(
            status_code=404, code="not_found", message="Snapshot not found.",
        )

    etag = f'"{row["id"]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    branding = request.app.state.branding
    snapshot_row = dict(row)
    pdf_bytes = await run_in_threadpool(
        exports_svc.render_snapshot_pdf, snapshot_row, branding,
    )
    snapshot_obj = type("S", (), snapshot_row)
    filename = _safe_filename(snapshot_obj, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )
