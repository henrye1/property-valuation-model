"""Background task: parse uploaded workbooks, recompute, write import_item rows.

Outer broad-except per item is the ONLY place in the codebase where catching
bare Exception is permitted: a single bad workbook must not poison the batch.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.services import matcher
from api.services.storage import StorageClient, downloaded_to_tempfile

try:
    from valuation_engine import calculate as _engine_calculate
    from valuation_engine.excel import parse_workbook
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

log = logging.getLogger(__name__)

RECOMPUTE_TOLERANCE_PCT = Decimal("0.001")


def _parse_bytes(storage: StorageClient, storage_path: str) -> Any:
    """Adapter: bytes from Storage -> tempfile -> engine.parse_workbook(path).
    See plan header adaptation #2."""
    with downloaded_to_tempfile(storage, storage_path) as path:
        return parse_workbook(path)


def _calc(inputs: Any) -> Any:
    """Indirection so tests can patch it without monkey-patching the engine."""
    return _engine_calculate(inputs)


def _compute_diff(
    sheet_value: Decimal | None, recomputed: Decimal,
) -> tuple[Decimal | None, dict[str, Any] | None]:
    if sheet_value is None or sheet_value == 0:
        return None, {
            "code": "formula_missing_value",
            "message": "Sheet's market value cell had no cached value; "
                       "diff_pct unavailable.",
            "field_path": None,
        }
    diff = (abs(recomputed - sheet_value) / sheet_value)
    if diff > RECOMPUTE_TOLERANCE_PCT:
        return diff, {
            "code": "recompute_mismatch",
            "message": (f"Engine recomputed {recomputed}; sheet stored "
                        f"{sheet_value} (diff {diff:.4%})."),
            "field_path": None,
        }
    return diff, None


async def _process_one(
    conn: asyncpg.Connection,
    storage: StorageClient,
    item: Any,
) -> None:
    """Per-item processing. Errors raised here are caught by the outer
    broad-except in run() and logged + persisted as unrecoverable."""
    parsed = _parse_bytes(storage, item["storage_path"])

    if parsed.inputs is None:
        # Engine surfaces hard parse errors via parse_errors (see plan adaptation #1).
        await q_item.mark_parse_error(
            conn, item["id"],
            building_name=parsed.building_name,
            errors=[w.model_dump() if hasattr(w, "model_dump") else dict(w)
                    for w in parsed.parse_errors],
        )
        return

    inputs_json = parsed.inputs.model_dump(mode="json")

    try:
        result = _calc(parsed.inputs)
    except ValueError as exc:
        await q_item.mark_parse_error(
            conn, item["id"],
            building_name=parsed.building_name,
            parsed_inputs_json=inputs_json,
            errors=[{"code": "engine_validation_error",
                     "message": str(exc), "field_path": None}],
        )
        return

    diff_pct, diff_warning = _compute_diff(
        parsed.sheet_market_value, result.market_value,
    )

    warnings: list[dict[str, Any]] = []
    for w in result.warnings:
        warnings.append(w.model_dump() if hasattr(w, "model_dump") else dict(w))
    for w in parsed.parse_warnings:
        warnings.append(w.model_dump() if hasattr(w, "model_dump") else dict(w))
    if diff_warning is not None:
        warnings.append(diff_warning)

    match = await matcher.suggest(conn, parsed.building_name)

    parse_status = "warning" if warnings else "ok"
    resolution = "accepted" if match.auto_linked else "pending"

    await q_item.mark_parsed(
        conn, item["id"],
        building_name=parsed.building_name,
        parsed_inputs_json=inputs_json,
        computed_result_json=result.model_dump(mode="json"),
        spreadsheet_market_value=parsed.sheet_market_value,
        recomputed_market_value=result.market_value,
        diff_pct=diff_pct,
        warnings_json=warnings,
        parse_status=parse_status,
        suggested_property_id=match.property_id,
        suggested_score=match.score,
        auto_linked=match.auto_linked,
        resolution=resolution,
        resolved_property_id=(match.property_id if match.auto_linked else None),
    )


async def run(
    pool: asyncpg.Pool,
    storage: StorageClient,
    batch_id: UUID,
) -> None:
    """Idempotent batch parse. Re-callable: list_for_parsing skips
    already-parsed rows."""
    async with pool.acquire(timeout=10) as conn:
        items = await q_item.list_for_parsing(conn, batch_id)
        for item in items:
            try:
                await _process_one(conn, storage, item)
            except Exception as exc:  # noqa: BLE001 — last-resort guard, see module docstring
                log.exception(
                    "parse_worker_item_failed",
                    extra={"item_id": str(item["id"]),
                           "item_filename": item["filename"],
                           "batch_id": str(batch_id)},
                )
                await q_item.mark_unrecoverable_error(conn, item["id"], repr(exc))
        await q_batch.set_status(conn, batch_id, "review")
