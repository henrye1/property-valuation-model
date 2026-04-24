"""Entity request/response shapes."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from api.schemas.common import APIBase


class EntityCreate(APIBase):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class EntityUpdate(APIBase):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> EntityUpdate:
        if all(v is None for v in (self.name, self.registration_number, self.notes)):
            raise ValueError("PATCH body must contain at least one field")
        return self


class Entity(APIBase):
    id: UUID
    name: str
    registration_number: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
