"""Unit tests for parse_worker._process_one with mocked storage + engine."""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.services import parse_worker
from api.services.matcher import MatchResult


def _item_record(**overrides: Any) -> Any:
    """Mimic an asyncpg.Record for an import_item row."""
    base = {
        "id": uuid4(),
        "batch_id": uuid4(),
        "filename": "fixture.xlsx",
        "storage_path": f"{uuid4()}/fixture.xlsx",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_one_parse_returns_no_inputs_marks_error() -> None:
    """When parse_workbook returns inputs=None, item is marked as parse error
    with the engine's parse_errors attached."""
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = None
    parse_result.building_name = "55 Empire Road"
    parse_result.parse_errors = [
        MagicMock(model_dump=lambda: {"code": "missing_required_section",
                                      "message": "...", "field_path": "tenants"}),
    ]

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch("api.queries.import_item.mark_parse_error",
               new_callable=AsyncMock) as mock_mark_err:
        await parse_worker._process_one(conn, storage, item)

    mock_mark_err.assert_called_once()
    kwargs = mock_mark_err.call_args.kwargs
    assert kwargs["building_name"] == "55 Empire Road"
    assert kwargs["errors"][0]["code"] == "missing_required_section"


@pytest.mark.asyncio
async def test_process_one_engine_value_error_marks_error() -> None:
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {"valuation_date": "2026-03-15"}
    parse_result.building_name = "x"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc",
                      side_effect=ValueError("cap_rate must be > 0")), \
         patch("api.queries.import_item.mark_parse_error",
               new_callable=AsyncMock) as mock_mark_err:
        await parse_worker._process_one(conn, storage, item)

    mock_mark_err.assert_called_once()
    err = mock_mark_err.call_args.kwargs["errors"][0]
    assert err["code"] == "engine_validation_error"
    assert "cap_rate" in err["message"]


@pytest.mark.asyncio
async def test_process_one_happy_path_marks_parsed_with_match() -> None:
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()
    pid = uuid4()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {"valuation_date": "2026-03-15"}
    parse_result.building_name = "55 Empire Road"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    calc_result = MagicMock()
    calc_result.market_value = Decimal("12500000")
    calc_result.warnings = []
    calc_result.model_dump = lambda mode="json": {"market_value": "12500000"}

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc", return_value=calc_result), \
         patch("api.services.matcher.suggest",
               new_callable=AsyncMock) as mock_suggest, \
         patch("api.queries.import_item.mark_parsed",
               new_callable=AsyncMock) as mock_mark:
        mock_suggest.return_value = MatchResult(
            property_id=pid, score=Decimal("1.0"), auto_linked=True,
            suggestions=[],
        )
        await parse_worker._process_one(conn, storage, item)

    mock_mark.assert_called_once()
    kwargs = mock_mark.call_args.kwargs
    assert kwargs["parse_status"] == "ok"
    assert kwargs["auto_linked"] is True
    assert kwargs["resolution"] == "accepted"
    assert kwargs["resolved_property_id"] == pid


@pytest.mark.asyncio
async def test_process_one_recompute_mismatch_adds_warning() -> None:
    """diff > tolerance produces a recompute_mismatch warning + parse_status=warning."""
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {}
    parse_result.building_name = "x"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    calc_result = MagicMock()
    calc_result.market_value = Decimal("13000000")  # 4% diff > 0.1% tolerance
    calc_result.warnings = []
    calc_result.model_dump = lambda mode="json": {}

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc", return_value=calc_result), \
         patch("api.services.matcher.suggest",
               new_callable=AsyncMock) as mock_suggest, \
         patch("api.queries.import_item.mark_parsed",
               new_callable=AsyncMock) as mock_mark:
        mock_suggest.return_value = MatchResult(None, None, False, [])
        await parse_worker._process_one(conn, storage, item)

    kwargs = mock_mark.call_args.kwargs
    assert kwargs["parse_status"] == "warning"
    codes = [w["code"] for w in kwargs["warnings_json"]]
    assert "recompute_mismatch" in codes


@pytest.mark.asyncio
async def test_run_outer_exception_marks_unrecoverable() -> None:
    """The outer broad-except per item must catch any exception type, log it,
    and mark the item with code='unrecoverable_parse_error'."""
    item = _item_record()
    pool_acquire_cm = AsyncMock()
    conn = AsyncMock()
    pool_acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    pool_acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=pool_acquire_cm)

    storage = MagicMock()

    with patch("api.queries.import_item.list_for_parsing",
               new_callable=AsyncMock, return_value=[item]), \
         patch.object(parse_worker, "_process_one",
                      side_effect=RuntimeError("boom")), \
         patch("api.queries.import_item.mark_unrecoverable_error",
               new_callable=AsyncMock) as mock_mark, \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock):
        await parse_worker.run(pool, storage, item["batch_id"])

    mock_mark.assert_called_once()
    args = mock_mark.call_args.args
    assert args[1] == item["id"]
    assert "boom" in args[2]
