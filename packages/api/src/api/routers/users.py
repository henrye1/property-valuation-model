"""GET /users — list app_user rows."""
from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from api.auth import current_user
from api.db import get_db
from api.queries import app_user as q_app_user
from api.schemas.user import AppUser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[AppUser])
async def list_users(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> list[AppUser]:
    rows = await q_app_user.list_users(conn)
    return [AppUser.model_validate(dict(r)) for r in rows]
