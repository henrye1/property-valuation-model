"""GET /audit — paginated audit log."""
from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.auth import current_user
from api.db import get_db
from api.queries import audit as q_audit
from api.schemas.audit import AuditEntry, AuditPage, AuditTargetTable
from api.schemas.user import AppUser

router = APIRouter(prefix="/audit", tags=["audit"])


def _row_to_entry(row: asyncpg.Record) -> AuditEntry:
    """Same defensive jsonb pattern as routers/snapshots._row_to_schema:
    asyncpg's jsonb codec doesn't reliably decode table-sourced columns,
    so fall back to json.loads on str values."""
    d: dict[str, Any] = dict(row)
    for k in ("before_json", "after_json"):
        val = d.get(k)
        if isinstance(val, str):
            d[k] = json.loads(val)
    return AuditEntry.model_validate(d)


@router.get("", response_model=AuditPage)
async def list_audit(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    target_table: Annotated[AuditTargetTable | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
) -> AuditPage:
    rows, total = await q_audit.list_audit(
        conn, limit=limit, offset=offset,
        target_table=target_table, actor_id=actor_id,
    )
    return AuditPage(
        items=[_row_to_entry(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )
