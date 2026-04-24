"""GET /audit — paginated audit log."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.auth import current_user
from api.db import get_db
from api.queries import audit as q_audit
from api.schemas.audit import AuditEntry, AuditPage, AuditTargetTable
from api.schemas.user import AppUser

router = APIRouter(prefix="/audit", tags=["audit"])


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
        items=[AuditEntry.model_validate(dict(r)) for r in rows],
        total=total, limit=limit, offset=offset,
    )
