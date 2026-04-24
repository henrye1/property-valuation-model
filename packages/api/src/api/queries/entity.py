"""Query functions for entity."""
from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = "id, name, registration_number, notes, created_at, updated_at, deleted_at"

_UPDATABLE = ("name", "registration_number", "notes")


async def list_entities(
    conn: asyncpg.Connection, *, include_deleted: bool = False
) -> list[asyncpg.Record]:
    where = "" if include_deleted else "where deleted_at is null"
    rows = await conn.fetch(
        f"select {_COLS} from public.entity {where} order by name asc"
    )
    return list(rows)


async def get_entity(
    conn: asyncpg.Connection, entity_id: UUID, *, include_deleted: bool = False
) -> asyncpg.Record | None:
    extra = "" if include_deleted else "and deleted_at is null"
    return await conn.fetchrow(
        f"select {_COLS} from public.entity where id = $1 {extra}",
        entity_id,
    )


async def insert_entity(
    conn: asyncpg.Connection,
    *,
    name: str,
    registration_number: str | None,
    notes: str | None,
) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"""
        insert into public.entity (name, registration_number, notes)
        values ($1, $2, $3)
        returning {_COLS}
        """,
        name, registration_number, notes,
    )
    return cast("asyncpg.Record", row)


async def update_entity(
    conn: asyncpg.Connection, entity_id: UUID, patch: dict[str, Any]
) -> asyncpg.Record | None:
    patch = {k: v for k, v in patch.items() if k in _UPDATABLE}
    if not patch:
        return await get_entity(conn, entity_id)

    set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(patch))
    values = list(patch.values())
    return await conn.fetchrow(
        f"""
        update public.entity
           set {set_clauses}, updated_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        entity_id, *values,
    )


async def soft_delete_entity(
    conn: asyncpg.Connection, entity_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"""
        update public.entity set deleted_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        entity_id,
    )


async def count_live_properties(conn: asyncpg.Connection, entity_id: UUID) -> int:
    row = await conn.fetchrow(
        "select count(*)::int as c from public.property "
        "where entity_id = $1 and deleted_at is null",
        entity_id,
    )
    assert row is not None
    return int(row["c"])
