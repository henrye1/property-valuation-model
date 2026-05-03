"""HTTP layer for /imports endpoints.

Owns: multipart parsing, request validation, dispatch to background tasks
and services. No SQL, no Storage SDK, no parsing logic.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel

from api.audit import audit
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import entity as q_entity
from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.queries import property as q_property
from api.schemas.imports import (
    ImportBatch,
    ImportBatchCounts,
    ImportBatchList,
    ImportBatchListItem,
    ImportCreated,
    ImportItem,
    ImportItemPatch,
    ImportItemSuggestion,
    ImportItemWarning,
)
from api.schemas.user import AppUser
from api.services import parse_worker
from api.services.engine_call import run_engine
from api.services.storage import safe_filename

try:
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportCreated, status_code=202)
async def create_import(
    background: BackgroundTasks,
    request: Request,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    files: Annotated[list[UploadFile], File(default_factory=list)],
) -> ImportCreated:
    if not files:
        raise APIError(
            status_code=400,
            code="no_files",
            message="At least one file is required.",
        )

    settings = request.app.state.settings
    storage = request.app.state.storage
    max_bytes = int(settings.IMPORT_MAX_FILE_BYTES)

    # Validate every file before any side effect.
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        if not (f.filename or "").lower().endswith(".xlsx"):
            raise APIError(
                status_code=400,
                code="unsupported_file_type",
                message=f"Only .xlsx files are accepted. Got: {f.filename!r}",
            )
        data = await f.read()
        if len(data) > max_bytes:
            raise APIError(
                status_code=413,
                code="file_too_large",
                message=f"{f.filename!r} exceeds {max_bytes} bytes.",
            )
        payloads.append((f.filename or "upload.xlsx", data))

    # Insert the batch.
    batch = await q_batch.insert(
        conn,
        uploaded_by=user.id,
        file_count=len(payloads),
        status="parsing",
    )
    batch_id: UUID = batch["id"]

    # Suffix collisions, upload to storage, insert items.
    seen: dict[str, int] = defaultdict(int)
    for orig_name, data in payloads:
        safe = safe_filename(orig_name)
        seen[safe] += 1
        if seen[safe] > 1:
            stem, _, ext = safe.rpartition(".")
            suffix = seen[safe] - 1
            safe = f"{stem}__{suffix}.{ext}" if stem else f"{safe}__{suffix}"
        path = storage.upload(batch_id, safe, data)
        await q_item.insert_placeholder(
            conn,
            batch_id=batch_id,
            filename=orig_name,
            storage_path=path,
        )

    pool: asyncpg.Pool = request.app.state.pool
    background.add_task(parse_worker.run, pool, storage, batch_id)

    return ImportCreated(
        batch_id=batch_id,
        file_count=len(payloads),
        status="parsing",
    )


def _decode_jsonb(d: dict[str, Any], *fields: str) -> None:
    """Defensive: asyncpg's jsonb codec doesn't decode table-sourced columns
    in 0.31. Same pattern as routers/snapshots._row_to_schema and
    routers/audit._row_to_entry."""
    for k in fields:
        v = d.get(k)
        if isinstance(v, str):
            d[k] = json.loads(v)


def _row_to_warning_list(
    json_field: list[dict[str, Any]] | None | str,
) -> list[ImportItemWarning]:
    """Accept jsonb-as-list, jsonb-as-str (asyncpg 0.31 quirk), or None."""
    decoded: list[dict[str, Any]] | None = (
        json.loads(json_field) if isinstance(json_field, str) else json_field
    )
    return [ImportItemWarning(**w) for w in (decoded or [])]


async def _row_to_item(
    conn: asyncpg.Connection, row: asyncpg.Record,
) -> ImportItem:
    suggestion: ImportItemSuggestion | None = None
    if row["suggested_property_id"] is not None:
        prop = await q_property.get_property(
            conn, row["suggested_property_id"], include_deleted=True,
        )
        if prop is not None:
            ent = await q_entity.get_entity(
                conn, prop["entity_id"], include_deleted=True,
            )
            suggestion = ImportItemSuggestion(
                property_id=prop["id"],
                property_name=prop["name"],
                entity_id=prop["entity_id"],
                entity_name=ent["name"] if ent else "",
                score=row["suggested_score"] or 0,
                auto_linked=bool(row["auto_linked"]),
            )
    # Defensive jsonb decode for the fields we forward to ImportItem.
    d: dict[str, Any] = {
        "parsed_inputs_json": row["parsed_inputs_json"],
        "computed_result_json": row["computed_result_json"],
        "resolved_inputs_json": row["resolved_inputs_json"],
    }
    _decode_jsonb(
        d,
        "parsed_inputs_json",
        "computed_result_json",
        "resolved_inputs_json",
    )
    return ImportItem(
        id=row["id"],
        filename=row["filename"],
        parse_status=row["parse_status"],
        building_name=row["building_name"],
        spreadsheet_market_value=row["spreadsheet_market_value"],
        recomputed_market_value=row["recomputed_market_value"],
        diff_pct=row["diff_pct"],
        warnings=_row_to_warning_list(row["warnings_json"]),
        errors=_row_to_warning_list(row["errors_json"]),
        suggestion=suggestion,
        resolution=row["resolution"],
        resolved_property_id=row["resolved_property_id"],
        parsed_inputs=d["parsed_inputs_json"],
        computed_result=d["computed_result_json"],
        resolved_inputs=d["resolved_inputs_json"],
    )


@router.get("", response_model=ImportBatchList)
async def list_imports(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    status: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ImportBatchList:
    rows, total = await q_batch.list_with_counts(
        conn, statuses=status, limit=limit, offset=offset,
    )
    items: list[ImportBatchListItem] = []
    for r in rows:
        # Look up uploader email for the response shape.
        u = await conn.fetchrow(
            "select id, email from public.app_user where id = $1",
            r["uploaded_by"],
        )
        items.append(ImportBatchListItem(
            id=r["id"],
            uploaded_by={
                "id": str(r["uploaded_by"]),
                "email": (u["email"] if u else None),
            },
            uploaded_at=r["uploaded_at"].isoformat(),
            file_count=r["file_count"],
            status=r["status"],
            counts=ImportBatchCounts(
                pending=r["pending"],
                accepted=r["accepted"],
                rejected=r["rejected"],
                edited=r["edited"],
                committed=r["committed_count"],
            ),
        ))
    return ImportBatchList(items=items, total=total)


@router.get("/{batch_id}", response_model=ImportBatch)
async def get_import(
    batch_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> ImportBatch:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(
            status_code=404,
            code="not_found",
            message="Import batch not found.",
        )
    rows = await q_item.list_for_batch(conn, batch_id)
    items = [await _row_to_item(conn, r) for r in rows]
    u = await conn.fetchrow(
        "select id, email from public.app_user where id = $1",
        batch["uploaded_by"],
    )
    return ImportBatch(
        id=batch["id"],
        uploaded_by={
            "id": str(batch["uploaded_by"]),
            "email": (u["email"] if u else None),
        },
        uploaded_at=batch["uploaded_at"].isoformat(),
        file_count=batch["file_count"],
        status=batch["status"],
        notes=batch["notes"],
        items=items,
    )


@router.patch("/{batch_id}/items/{item_id}", response_model=ImportItem)
async def patch_import_item(
    batch_id: UUID,
    item_id: UUID,
    body: ImportItemPatch,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> ImportItem:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(
            status_code=404,
            code="not_found",
            message="Import batch not found.",
        )
    if batch["status"] != "review":
        raise APIError(
            status_code=409,
            code="batch_not_in_review",
            message=(
                f"Batch status is {batch['status']!r}; "
                "only 'review' batches accept patches."
            ),
        )

    item = await q_item.get_by_id(conn, item_id)
    if item is None or item["batch_id"] != batch_id:
        raise APIError(
            status_code=404,
            code="not_found",
            message="Import item not found.",
        )

    # parse_status='error' items can only be 'edited' or 'rejected'.
    if item["parse_status"] == "error" and body.resolution == "accepted":
        raise APIError(
            status_code=422,
            code="error_item_must_be_edited_or_rejected",
            message=(
                "Items with parse_status='error' cannot be 'accepted'; "
                "use 'edited' or 'rejected'."
            ),
        )

    # Per-resolution computed-result re-runs.
    computed_result_json: dict[str, Any] | None = None
    if body.resolution == "edited":
        vi = ValuationInput.model_validate(body.resolved_inputs or {})
        result = run_engine(vi)
        computed_result_json = result.model_dump(mode="json")

    before = {
        "resolution": item["resolution"],
        "resolved_property_id": (
            str(item["resolved_property_id"])
            if item["resolved_property_id"] else None
        ),
    }

    updated = await q_item.patch_resolution(
        conn, item_id,
        resolution=body.resolution,
        resolved_property_id=body.resolved_property_id,
        resolved_inputs_json=body.resolved_inputs,
        computed_result_json=computed_result_json,
        resolution_notes=body.resolution_notes,
        resolved_by=user.id,
    )

    after = {
        "resolution": updated["resolution"],
        "resolved_property_id": (
            str(updated["resolved_property_id"])
            if updated["resolved_property_id"] else None
        ),
    }
    await audit(
        conn,
        actor_id=user.id, actor_email=user.email,
        action="update", target_table="import_item", target_id=item_id,
        before=before, after=after,
    )

    return await _row_to_item(conn, updated)


class _BatchStatusResponse(BaseModel):
    id: UUID
    status: str


@router.post("/{batch_id}/cancel", response_model=_BatchStatusResponse)
async def cancel_import(
    batch_id: UUID,
    request: Request,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> _BatchStatusResponse:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(status_code=404, code="not_found",
                       message="Import batch not found.")
    if batch["status"] not in ("parsing", "review"):
        raise APIError(status_code=409, code="batch_not_cancellable",
                       message=f"Batch status is {batch['status']!r}; "
                               f"only 'parsing' or 'review' batches can be cancelled.")

    n = await q_batch.set_status(conn, batch_id, "cancelled")
    if n != 1:
        raise APIError(status_code=409, code="batch_state_changed",
                       message="Batch state changed during cancel; please retry.")

    storage = request.app.state.storage
    storage.delete_prefix(batch_id)

    await audit(
        conn, actor_id=user.id, actor_email=user.email,
        action="cancel", target_table="import_batch", target_id=batch_id,
        before={"status": batch["status"]},
        after={"status": "cancelled"},
    )
    return _BatchStatusResponse(id=batch_id, status="cancelled")
