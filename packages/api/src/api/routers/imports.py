"""HTTP layer for /imports endpoints.

Owns: multipart parsing, request validation, dispatch to background tasks
and services. No SQL, no Storage SDK, no parsing logic.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    UploadFile,
)

from api.auth import require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.schemas.imports import ImportCreated
from api.schemas.user import AppUser
from api.services import parse_worker
from api.services.storage import safe_filename

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
