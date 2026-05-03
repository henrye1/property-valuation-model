"""CRUD + soft-delete endpoints for property."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.audit import audit, record_to_json
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import entity as q_entity
from api.queries import property as q_property
from api.schemas.property import Property, PropertyCreate, PropertyType, PropertyUpdate
from api.schemas.user import AppUser

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[Property])
async def list_properties(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    entity_id: Annotated[UUID | None, Query()] = None,
    property_type: Annotated[PropertyType | None, Query()] = None,
    include_deleted: Annotated[bool, Query()] = False,
) -> list[Property]:
    rows = await q_property.list_properties(
        conn,
        entity_id=entity_id,
        property_type=property_type,
        include_deleted=include_deleted,
    )
    return [Property.model_validate(dict(r)) for r in rows]


@router.get("/{property_id}", response_model=Property)
async def get_property(
    property_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: Annotated[bool, Query()] = False,
) -> Property:
    row = await q_property.get_property(conn, property_id, include_deleted=include_deleted)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    return Property.model_validate(dict(row))


@router.post("", response_model=Property, status_code=201)
async def create_property(
    body: PropertyCreate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    parent = await q_entity.get_entity(conn, body.entity_id)
    if parent is None:
        raise APIError(
            status_code=422,
            code="invalid_input",
            message="entity_id does not reference a live entity.",
        )
    async with conn.transaction():
        row = await q_property.insert_property(
            conn,
            entity_id=body.entity_id,
            name=body.name,
            address=body.address,
            property_type=body.property_type,
            notes=body.notes,
        )
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="create",
            target_table="property",
            target_id=row["id"],
            before=None,
            after=record_to_json(row),
        )
    return Property.model_validate(dict(row))


@router.patch("/{property_id}", response_model=Property)
async def update_property(
    property_id: UUID,
    body: PropertyUpdate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    before = await q_property.get_property(conn, property_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    patch = body.model_dump(exclude_unset=True)
    async with conn.transaction():
        after_row = await q_property.update_property(conn, property_id, patch)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="update",
            target_table="property",
            target_id=property_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Property.model_validate(dict(after_row))


@router.delete("/{property_id}", response_model=Property)
async def delete_property(
    property_id: UUID,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    before = await q_property.get_property(conn, property_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    live = await q_property.count_active_snapshots(conn, property_id)
    if live > 0:
        raise APIError(
            status_code=409,
            code="has_live_children",
            message="Property has active valuation snapshots.",
            details={"blocking_count": live},
        )
    async with conn.transaction():
        after_row = await q_property.soft_delete_property(conn, property_id)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="soft_delete",
            target_table="property",
            target_id=property_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Property.model_validate(dict(after_row))
