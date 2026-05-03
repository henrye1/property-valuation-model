"""Audit-log response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from api.schemas.common import APIBase

AuditAction = Literal["create", "update", "soft_delete"]
AuditTargetTable = Literal["entity", "property", "valuation_snapshot", "app_user"]


class AuditEntry(APIBase):
    id: UUID
    actor_id: UUID
    actor_email: str | None
    action: AuditAction
    target_table: AuditTargetTable
    target_id: UUID
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    created_at: datetime


class AuditPage(APIBase):
    items: list[AuditEntry]
    total: int
    limit: int
    offset: int
