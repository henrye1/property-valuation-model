"""asyncpg query helpers for the import_batch table.

No business logic — pure SQL. Idempotency, status-machine guards, and
RLS-bypass are the routers' / services' responsibility.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

_COLS = "id, uploaded_by, uploaded_at, file_count, status, notes"


async def insert(
    conn: asyncpg.Connection,
    *,
    uploaded_by: UUID,
    file_count: int,
    status: str = "parsing",
    notes: str | None = None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        f"""
        insert into public.import_batch (uploaded_by, file_count, status, notes)
        values ($1, $2, $3, $4)
        returning {_COLS}
        """,
        uploaded_by, file_count, status, notes,
    )


async def get_by_id(
    conn: asyncpg.Connection, batch_id: UUID,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.import_batch where id = $1",
        batch_id,
    )


async def list_with_counts(
    conn: asyncpg.Connection,
    *,
    statuses: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """Returns (rows, total). Each row carries import_batch cols plus
    `pending`, `accepted`, `rejected`, `edited`, `committed_count` ints."""
    where = ""
    params: list[Any] = []
    if statuses:
        where = "where b.status = any($1::text[])"
        params.append(statuses)
    pl = len(params)
    rows = await conn.fetch(
        f"""
        with batch_counts as (
            select batch_id,
                   count(*) filter (where resolution = 'pending')   as pending,
                   count(*) filter (where resolution = 'accepted')  as accepted,
                   count(*) filter (where resolution = 'rejected')  as rejected,
                   count(*) filter (where resolution = 'edited')    as edited,
                   count(*) filter (where resolution = 'committed') as committed_count
              from public.import_item
             group by batch_id
        )
        select b.id, b.uploaded_by, b.uploaded_at, b.file_count, b.status, b.notes,
               coalesce(c.pending, 0)         as pending,
               coalesce(c.accepted, 0)        as accepted,
               coalesce(c.rejected, 0)        as rejected,
               coalesce(c.edited, 0)          as edited,
               coalesce(c.committed_count, 0) as committed_count
          from public.import_batch b
          left join batch_counts c on c.batch_id = b.id
        {where}
         order by b.uploaded_at desc
         limit ${pl + 1} offset ${pl + 2}
        """,
        *params, limit, offset,
    )
    total_row = await conn.fetchrow(
        f"select count(*)::int as n from public.import_batch b {where}",
        *params,
    )
    total = int(total_row["n"]) if total_row else 0
    return list(rows), total


async def set_status(
    conn: asyncpg.Connection,
    batch_id: UUID,
    new_status: str,
) -> int:
    """Returns affected row count (0 or 1)."""
    result = await conn.execute(
        "update public.import_batch set status = $1 where id = $2",
        new_status, batch_id,
    )
    return int(result.rsplit(maxsplit=1)[-1])
