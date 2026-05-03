"""Audit-log helper. Called inside the same transaction as every mutation."""
from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

import asyncpg

from api.queries.snapshot import _json_default as _json_default  # reuse


async def audit(
    tx: asyncpg.Connection,
    *,
    actor_id: UUID,
    actor_email: str | None,
    action: Literal["create", "update", "soft_delete"],
    target_table: Literal["entity", "property", "valuation_snapshot", "app_user"],
    target_id: UUID,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    await tx.execute(
        """
        insert into public.audit_log
            (actor_id, actor_email, action, target_table, target_id,
             before_json, after_json)
        values ($1, $2, $3::public.audit_action,
                $4::public.audit_target_table, $5, $6::jsonb, $7::jsonb)
        """,
        actor_id,
        actor_email,
        action,
        target_table,
        target_id,
        json.dumps(before, default=_json_default) if before is not None else None,
        json.dumps(after, default=_json_default) if after is not None else None,
    )


def record_to_json(record: asyncpg.Record) -> dict[str, Any]:
    """Convert a Record to a plain dict suitable for audit before/after."""
    return dict(record)
