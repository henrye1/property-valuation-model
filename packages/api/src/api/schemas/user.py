"""AppUser request/response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from api.schemas.common import APIBase

Role = Literal["valuer", "viewer"]


class AppUser(APIBase):
    id: UUID
    email: str | None
    display_name: str | None
    role: Role
    created_at: datetime
    last_seen_at: datetime | None
