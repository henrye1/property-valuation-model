"""Shared base classes and helpers for API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIBase(BaseModel):
    """Base for all API request/response schemas.

    - extra='forbid' on requests catches typos early.
    - populate_by_name allows DB row -> schema construction by field name.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        arbitrary_types_allowed=False,
    )


class Timestamped(APIBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


def nonempty_update(data: dict[str, Any]) -> dict[str, Any]:
    """Strip keys whose value is None. Used to build partial UPDATEs."""
    return {k: v for k, v in data.items() if v is not None}
