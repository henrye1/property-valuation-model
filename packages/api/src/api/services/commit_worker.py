"""Idempotent per-item commit loop for an import batch.

One transaction per item. Re-callable — items already at
resolved_snapshot_id IS NOT NULL are counted as 'skipped' and not re-processed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg

from api.audit import audit
from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.queries import property as q_property
from api.queries import snapshot as q_snapshot
from api.schemas.user import AppUser

try:
    from valuation_engine import __version__ as engine_version
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

log = logging.getLogger(__name__)


class CommitFailure(Exception):
    """Raised by _commit_one for any per-item failure. Caller (commit_batch)
    catches this to collect failures into the summary; other exception types
    propagate as 500."""

    def __init__(self, item_id: UUID, filename: str, reason: str, message: str) -> None:
        self.item_id = item_id
        self.filename = filename
        self.reason = reason
        self.message = message
        super().__init__(message)


@dataclass
class CommitSummary:
    batch_id: UUID
    committed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[CommitFailure] = field(default_factory=list)
    batch_status: str = "review"  # 'committed' or 'review'


async def _commit_one(
    pool: asyncpg.Pool,
    item: Any,
    actor: AppUser,
) -> None:
    inputs = item["resolved_inputs_json"] or item["parsed_inputs_json"]
    if not inputs:
        raise CommitFailure(item["id"], item["filename"],
                            "no_inputs", "No inputs to commit.")
    if not item["resolved_property_id"]:
        raise CommitFailure(item["id"], item["filename"], "no_property_link",
                            "Reviewer did not link a property.")

    try:
        valuation_input = ValuationInput.model_validate(inputs)
        result = calculate(valuation_input)
    except ValueError as exc:
        raise CommitFailure(item["id"], item["filename"],
                            "engine_validation_error", str(exc)) from exc

    async with pool.acquire(timeout=10) as conn, conn.transaction():
        prop = await q_property.get_property(conn, item["resolved_property_id"])
        if prop is None:
            raise CommitFailure(item["id"], item["filename"], "property_missing",
                                "Linked property no longer exists.")

        await q_snapshot.supersede_active(conn, item["resolved_property_id"])
        snap = await q_snapshot.insert_snapshot(
            conn,
            property_id=item["resolved_property_id"],
            valuation_date=valuation_input.valuation_date,
            created_by=actor.id,
            inputs_json=valuation_input.model_dump(mode="json"),
            result_json=result.model_dump(mode="json"),
            market_value=result.market_value,
            cap_rate=valuation_input.cap_rate,
            engine_version=engine_version,
            source="excel_import",
            source_file=item["filename"],
        )

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="create",
            target_table="valuation_snapshot",
            target_id=snap["id"],
            before=None,
            after={
                "property_id": str(item["resolved_property_id"]),
                "valuation_date": str(valuation_input.valuation_date),
                "market_value": str(result.market_value),
                "source": "excel_import",
                "source_file": item["filename"],
                "import_item_id": str(item["id"]),
            },
        )

        await q_item.mark_committed(
            conn, item["id"], snapshot_id=snap["id"], actor_id=actor.id,
        )

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="update",
            target_table="import_item",
            target_id=item["id"],
            before={"resolution": item["resolution"], "resolved_snapshot_id": None},
            after={"resolution": "committed",
                   "resolved_snapshot_id": str(snap["id"])},
        )


async def commit_batch(
    pool: asyncpg.Pool,
    batch_id: UUID,
    actor: AppUser,
    *,
    storage: Any = None,
) -> CommitSummary:
    summary = CommitSummary(batch_id=batch_id)

    async with pool.acquire(timeout=10) as conn:
        items = await q_item.list_for_commit(conn, batch_id)

    for item in items:
        try:
            await _commit_one(pool, item, actor)
            summary.committed += 1
        except CommitFailure as f:
            summary.failed += 1
            summary.failures.append(f)
        except Exception as exc:  # noqa: BLE001 — surface as failure, not 500
            log.exception("commit_worker_unexpected",
                          extra={"item_id": str(item["id"])})
            summary.failed += 1
            summary.failures.append(
                CommitFailure(item["id"], item["filename"],
                              "unexpected_error", repr(exc))
            )

    async with pool.acquire(timeout=10) as conn:
        summary.skipped = await q_item.count_already_committed(conn, batch_id)
        if await q_item.all_items_terminal(conn, batch_id):
            await q_batch.set_status(conn, batch_id, "committed")
            if storage is not None:
                storage.delete_prefix(batch_id)
            summary.batch_status = "committed"

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="commit",
            target_table="import_batch",
            target_id=batch_id,
            before=None,
            after={"committed": summary.committed,
                   "failed": summary.failed,
                   "skipped": summary.skipped,
                   "batch_status": summary.batch_status},
        )

    return summary
