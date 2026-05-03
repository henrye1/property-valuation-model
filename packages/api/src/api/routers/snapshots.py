"""Snapshot endpoints: list per property, get one, create (runs engine + persists)."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from api.audit import audit, record_to_json
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import property as q_property
from api.queries import snapshot as q_snapshot
from api.queries.snapshot import _json_default
from api.schemas.snapshot import Snapshot
from api.schemas.user import AppUser

try:
    from valuation_engine import __version__ as engine_version
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc


snapshots_router = APIRouter(tags=["snapshots"])
properties_snapshots_router = APIRouter(prefix="/properties", tags=["snapshots"])


@properties_snapshots_router.get(
    "/{property_id}/snapshots", response_model=list[Snapshot]
)
async def list_property_snapshots(
    property_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> list[Snapshot]:
    prop = await q_property.get_property(conn, property_id, include_deleted=True)
    if prop is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    rows = await q_snapshot.list_for_property(conn, property_id)
    return [_row_to_schema(r) for r in rows]


@snapshots_router.get("/snapshots/{snapshot_id}", response_model=Snapshot)
async def get_snapshot(
    snapshot_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Snapshot:
    row = await q_snapshot.get_snapshot(conn, snapshot_id)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Snapshot not found.")
    return _row_to_schema(row)


@properties_snapshots_router.post(
    "/{property_id}/snapshots", response_model=Snapshot, status_code=201
)
async def create_snapshot(
    property_id: UUID,
    body: ValuationInput,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Snapshot:
    prop = await q_property.get_property(conn, property_id)
    if prop is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")

    result = calculate(body)
    inputs_json = body.model_dump(mode="json")
    result_json = result.model_dump(mode="json")

    async with conn.transaction():
        await q_snapshot.supersede_active(conn, property_id)
        row = await q_snapshot.insert_snapshot(
            conn,
            property_id=property_id,
            valuation_date=body.valuation_date,
            created_by=user.id,
            inputs_json=inputs_json,
            result_json=result_json,
            market_value=result.market_value,
            cap_rate=body.cap_rate,
            engine_version=engine_version,
            source="manual",
            source_file=None,
        )
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="create",
            target_table="valuation_snapshot",
            target_id=row["id"],
            before=None,
            after=record_to_json(row),
        )
    return _row_to_schema(row)


def _row_to_schema(row: asyncpg.Record) -> Snapshot:
    d = dict(row)
    # jsonb columns come back as dicts already, but be defensive with str fallback.
    for k in ("inputs_json", "result_json"):
        val = d[k]
        if isinstance(val, str):
            d[k] = json.loads(val)
    return Snapshot.model_validate(d)


# Suppress unused import warning — _json_default is imported for side-effect
# awareness (callers may need it), keep it available in module namespace.
__all__ = [
    "snapshots_router",
    "properties_snapshots_router",
    "_row_to_schema",
    "_json_default",
]
