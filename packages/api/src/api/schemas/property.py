"""Property request/response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from api.schemas.common import APIBase

PropertyType = Literal["office", "retail", "industrial", "mixed", "residential", "other"]


class PropertyCreate(APIBase):
    entity_id: UUID
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    property_type: PropertyType = "other"
    notes: str | None = None


class PropertyUpdate(APIBase):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    property_type: PropertyType | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> PropertyUpdate:
        values = (self.name, self.address, self.property_type, self.notes)
        if all(v is None for v in values):
            raise ValueError("PATCH body must contain at least one field")
        return self


class Property(APIBase):
    id: UUID
    entity_id: UUID
    name: str
    address: str | None
    property_type: PropertyType
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
