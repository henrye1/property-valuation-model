"""Query functions for audit_log."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

_COLS = (
    "id, actor_id, actor_email, action, target_table, target_id, "
    "before_json, after_json, created_at"
)


async def list_audit(
    conn: asyncpg.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    target_table: str | None = None,
    actor_id: UUID | None = None,
) -> tuple[list[asyncpg.Record], int]:
    clauses: list[str] = []
    params: list[Any] = []
    if target_table is not None:
        params.append(target_table)
        clauses.append(f"target_table = ${len(params)}::public.audit_target_table")
    if actor_id is not None:
        params.append(actor_id)
        clauses.append(f"actor_id = ${len(params)}")

    where = f"where {' and '.join(clauses)}" if clauses else ""

    total_row = await conn.fetchrow(
        f"select count(*)::int as c from public.audit_log {where}",
        *params,
    )
    assert total_row is not None
    total = int(total_row["c"])

    params_with_paging = [*params, limit, offset]
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.audit_log {where}
         order by created_at desc
         limit ${len(params) + 1} offset ${len(params) + 2}
        """,
        *params_with_paging,
    )
    return list(rows), total
