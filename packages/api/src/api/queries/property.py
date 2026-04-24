"""Query functions for property."""
from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = (
    "id, entity_id, name, address, property_type, notes, "
    "created_at, updated_at, deleted_at"
)

_UPDATABLE = ("name", "address", "property_type", "notes")


async def list_properties(
    conn: asyncpg.Connection,
    *,
    entity_id: UUID | None = None,
    property_type: str | None = None,
    include_deleted: bool = False,
) -> list[asyncpg.Record]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at is null")
    if entity_id is not None:
        params.append(entity_id)
        clauses.append(f"entity_id = ${len(params)}")
    if property_type is not None:
        params.append(property_type)
        clauses.append(f"property_type = ${len(params)}")

    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(
        f"select {_COLS} from public.property {where} order by name asc",
        *params,
    )
    return list(rows)


async def get_property(
    conn: asyncpg.Connection, property_id: UUID, *, include_deleted: bool = False
) -> asyncpg.Record | None:
    extra = "" if include_deleted else "and deleted_at is null"
    return await conn.fetchrow(
        f"select {_COLS} from public.property where id = $1 {extra}",
        property_id,
    )


async def insert_property(
    conn: asyncpg.Connection,
    *,
    entity_id: UUID,
    name: str,
    address: str | None,
    property_type: str,
    notes: str | None,
) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"""
        insert into public.property
            (entity_id, name, address, property_type, notes)
        values ($1, $2, $3, $4::public.property_type, $5)
        returning {_COLS}
        """,
        entity_id, name, address, property_type, notes,
    )
    return cast("asyncpg.Record", row)


async def update_property(
    conn: asyncpg.Connection, property_id: UUID, patch: dict[str, Any]
) -> asyncpg.Record | None:
    patch = {k: v for k, v in patch.items() if k in _UPDATABLE}
    if not patch:
        return await get_property(conn, property_id)

    set_parts: list[str] = []
    values: list[Any] = []
    for k, v in patch.items():
        values.append(v)
        if k == "property_type":
            set_parts.append(f"{k} = ${len(values) + 1}::public.property_type")
        else:
            set_parts.append(f"{k} = ${len(values) + 1}")

    return await conn.fetchrow(
        f"""
        update public.property
           set {", ".join(set_parts)}, updated_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        property_id, *values,
    )


async def soft_delete_property(
    conn: asyncpg.Connection, property_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"""
        update public.property set deleted_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        property_id,
    )


async def count_active_snapshots(conn: asyncpg.Connection, property_id: UUID) -> int:
    row = await conn.fetchrow(
        "select count(*)::int as c from public.valuation_snapshot "
        "where property_id = $1 and status = 'active'",
        property_id,
    )
    assert row is not None
    return int(row["c"])
