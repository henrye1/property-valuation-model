"""Query functions for valuation_snapshot."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = (
    "id, property_id, valuation_date, created_by, created_at, status, "
    "inputs_json, result_json, market_value, cap_rate, engine_version, "
    "source, source_file"
)


async def list_for_property(
    conn: asyncpg.Connection, property_id: UUID
) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.valuation_snapshot
         where property_id = $1
         order by valuation_date desc, created_at desc
        """,
        property_id,
    )
    return list(rows)


async def get_snapshot(
    conn: asyncpg.Connection, snapshot_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.valuation_snapshot where id = $1",
        snapshot_id,
    )


async def supersede_active(
    tx: asyncpg.Connection, property_id: UUID
) -> int:
    """Flip all currently-active snapshots for a property to superseded."""
    result = await tx.execute(
        """
        update public.valuation_snapshot
           set status = 'superseded'
         where property_id = $1 and status = 'active'
        """,
        property_id,
    )
    # `UPDATE N` → last token is row count
    return int(result.rsplit(maxsplit=1)[-1])


async def insert_snapshot(
    tx: asyncpg.Connection,
    *,
    property_id: UUID,
    valuation_date: date,
    created_by: UUID,
    inputs_json: dict[str, Any],
    result_json: dict[str, Any],
    market_value: Decimal,
    cap_rate: Decimal,
    engine_version: str,
    source: str,
    source_file: str | None,
) -> asyncpg.Record:
    row = await tx.fetchrow(
        f"""
        insert into public.valuation_snapshot
            (property_id, valuation_date, created_by, status,
             inputs_json, result_json, market_value, cap_rate,
             engine_version, source, source_file)
        values ($1, $2, $3, 'active', $4::jsonb, $5::jsonb, $6, $7,
                $8, $9::public.snapshot_source, $10)
        returning {_COLS}
        """,
        property_id,
        valuation_date,
        created_by,
        json.dumps(inputs_json, default=_json_default),
        json.dumps(result_json, default=_json_default),
        market_value,
        cap_rate,
        engine_version,
        source,
        source_file,
    )
    return cast("asyncpg.Record", row)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON-serializable: {type(value).__name__}")
