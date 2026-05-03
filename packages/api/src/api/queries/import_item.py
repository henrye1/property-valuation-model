"""asyncpg query helpers for the import_item table."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

_COLS = (
    "id, batch_id, filename, storage_path, parse_status, building_name, "
    "parsed_inputs_json, computed_result_json, spreadsheet_market_value, "
    "recomputed_market_value, diff_pct, warnings_json, errors_json, "
    "suggested_property_id, suggested_score, auto_linked, "
    "resolution, resolved_property_id, resolved_snapshot_id, "
    "resolved_inputs_json, resolution_notes, resolved_at, resolved_by, "
    "created_at"
)


def _jdef(value: Any) -> Any:
    """JSON encoder for Decimal + UUID + date/datetime in our row payloads."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON-serializable: {type(value).__name__}")


async def insert_placeholder(
    conn: asyncpg.Connection,
    *,
    batch_id: UUID,
    filename: str,
    storage_path: str,
) -> asyncpg.Record:
    """Insert a row in 'parsing' state. parse_worker mutates it later."""
    return await conn.fetchrow(
        f"""
        insert into public.import_item
            (batch_id, filename, storage_path, parse_status)
        values ($1, $2, $3, 'ok')
        returning {_COLS}
        """,
        batch_id, filename, storage_path,
    )


async def get_by_id(
    conn: asyncpg.Connection, item_id: UUID,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.import_item where id = $1",
        item_id,
    )


async def list_for_batch(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def list_for_parsing(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    """Items the parse_worker still needs to process (idempotency-safe)."""
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
           and parsed_inputs_json is null
           and (errors_json = '[]'::jsonb or errors_json is null)
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def list_for_commit(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    """Items the commit_worker should process (resolution accepted|edited, not yet snapshot'd)."""
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
           and resolution in ('accepted', 'edited')
           and resolved_snapshot_id is null
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def count_already_committed(
    conn: asyncpg.Connection, batch_id: UUID,
) -> int:
    row = await conn.fetchrow(
        """
        select count(*)::int as n from public.import_item
         where batch_id = $1 and resolved_snapshot_id is not null
        """,
        batch_id,
    )
    return int(row["n"]) if row else 0


async def all_items_terminal(
    conn: asyncpg.Connection, batch_id: UUID,
) -> bool:
    """True iff every item is committed or rejected (batch can flip to committed)."""
    row = await conn.fetchrow(
        """
        select count(*)::int as n_open
          from public.import_item
         where batch_id = $1
           and resolution not in ('committed', 'rejected')
        """,
        batch_id,
    )
    return (int(row["n_open"]) if row else 0) == 0


async def mark_parsed(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    building_name: str | None,
    parsed_inputs_json: dict[str, Any] | None,
    computed_result_json: dict[str, Any] | None,
    spreadsheet_market_value: Decimal | None,
    recomputed_market_value: Decimal | None,
    diff_pct: Decimal | None,
    warnings_json: list[dict[str, Any]],
    parse_status: str,
    suggested_property_id: UUID | None,
    suggested_score: Decimal | None,
    auto_linked: bool,
    resolution: str,
    resolved_property_id: UUID | None,
) -> None:
    await conn.execute(
        """
        update public.import_item set
            building_name = $2,
            parsed_inputs_json = $3::jsonb,
            computed_result_json = $4::jsonb,
            spreadsheet_market_value = $5,
            recomputed_market_value = $6,
            diff_pct = $7,
            warnings_json = $8::jsonb,
            parse_status = $9,
            suggested_property_id = $10,
            suggested_score = $11,
            auto_linked = $12,
            resolution = $13,
            resolved_property_id = $14
         where id = $1
        """,
        item_id, building_name,
        json.dumps(parsed_inputs_json, default=_jdef) if parsed_inputs_json else None,
        json.dumps(computed_result_json, default=_jdef) if computed_result_json else None,
        spreadsheet_market_value, recomputed_market_value, diff_pct,
        json.dumps(warnings_json, default=_jdef),
        parse_status, suggested_property_id, suggested_score, auto_linked,
        resolution, resolved_property_id,
    )


async def mark_parse_error(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    building_name: str | None = None,
    parsed_inputs_json: dict[str, Any] | None = None,
    errors: list[dict[str, Any]],
) -> None:
    await conn.execute(
        """
        update public.import_item set
            parse_status = 'error',
            building_name = coalesce($2, building_name),
            parsed_inputs_json = coalesce($3::jsonb, parsed_inputs_json),
            errors_json = $4::jsonb
         where id = $1
        """,
        item_id, building_name,
        json.dumps(parsed_inputs_json, default=_jdef) if parsed_inputs_json else None,
        json.dumps(errors, default=_jdef),
    )


async def mark_unrecoverable_error(
    conn: asyncpg.Connection, item_id: UUID, exc_repr: str,
) -> None:
    await mark_parse_error(
        conn, item_id,
        errors=[{"code": "unrecoverable_parse_error", "message": exc_repr,
                 "field_path": None}],
    )


async def patch_resolution(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    resolution: str,
    resolved_property_id: UUID | None,
    resolved_inputs_json: dict[str, Any] | None,
    computed_result_json: dict[str, Any] | None,
    resolution_notes: str | None,
    resolved_by: UUID,
) -> asyncpg.Record:
    return await conn.fetchrow(
        f"""
        update public.import_item set
            resolution = $2,
            resolved_property_id = $3,
            resolved_inputs_json = coalesce($4::jsonb, resolved_inputs_json),
            computed_result_json = coalesce($5::jsonb, computed_result_json),
            resolution_notes = coalesce($6, resolution_notes),
            resolved_at = now(),
            resolved_by = $7
         where id = $1
        returning {_COLS}
        """,
        item_id, resolution, resolved_property_id,
        json.dumps(resolved_inputs_json, default=_jdef) if resolved_inputs_json else None,
        json.dumps(computed_result_json, default=_jdef) if computed_result_json else None,
        resolution_notes, resolved_by,
    )


async def mark_committed(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    snapshot_id: UUID,
    actor_id: UUID,
) -> None:
    await conn.execute(
        """
        update public.import_item set
            resolution = 'committed',
            resolved_snapshot_id = $2,
            resolved_at = now(),
            resolved_by = $3
         where id = $1
        """,
        item_id, snapshot_id, actor_id,
    )
