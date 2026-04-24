"""GET /me — current user, auto-provisioned on first call."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import current_user
from api.schemas.user import AppUser

router = APIRouter(tags=["me"])


@router.get("/me", response_model=AppUser)
async def me(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
    return user
