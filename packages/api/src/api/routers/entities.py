"""CRUD + soft-delete endpoints for entity."""
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
from api.schemas.entity import Entity, EntityCreate, EntityUpdate
from api.schemas.user import AppUser

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[Entity])
async def list_entities(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: bool = Query(default=False),
) -> list[Entity]:
    rows = await q_entity.list_entities(conn, include_deleted=include_deleted)
    return [Entity.model_validate(dict(r)) for r in rows]


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(
    entity_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: bool = Query(default=False),
) -> Entity:
    row = await q_entity.get_entity(conn, entity_id, include_deleted=include_deleted)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    return Entity.model_validate(dict(row))


@router.post("", response_model=Entity, status_code=201)
async def create_entity(
    body: EntityCreate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    async with conn.transaction():
        row = await q_entity.insert_entity(
            conn,
            name=body.name,
            registration_number=body.registration_number,
            notes=body.notes,
        )
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="create",
            target_table="entity",
            target_id=row["id"],
            before=None,
            after=record_to_json(row),
        )
    return Entity.model_validate(dict(row))


@router.patch("/{entity_id}", response_model=Entity)
async def update_entity(
    entity_id: UUID,
    body: EntityUpdate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    before = await q_entity.get_entity(conn, entity_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    patch = body.model_dump(exclude_unset=True)
    async with conn.transaction():
        after_row = await q_entity.update_entity(conn, entity_id, patch)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="update",
            target_table="entity",
            target_id=entity_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Entity.model_validate(dict(after_row))


@router.delete("/{entity_id}", response_model=Entity)
async def delete_entity(
    entity_id: UUID,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    before = await q_entity.get_entity(conn, entity_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    live_children = await q_entity.count_live_properties(conn, entity_id)
    if live_children > 0:
        raise APIError(
            status_code=409,
            code="has_live_children",
            message="Entity has live properties and cannot be deleted.",
            details={"blocking_count": live_children},
        )
    async with conn.transaction():
        after_row = await q_entity.soft_delete_entity(conn, entity_id)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="soft_delete",
            target_table="entity",
            target_id=entity_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Entity.model_validate(dict(after_row))
