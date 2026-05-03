"""Unit tests for commit_worker — control flow + per-item failure handling."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.schemas.user import AppUser
from api.services import commit_worker
from api.services.commit_worker import CommitFailure


def _user() -> AppUser:
    return AppUser(
        id=uuid4(), email="reviewer@anchorpointrisk.co.za",
        display_name=None, role="valuer",
        created_at="2026-05-01T00:00:00Z", last_seen_at=None,
    )


def _item_record(**overrides: Any) -> dict[str, Any]:
    pid = uuid4()
    base: dict[str, Any] = {
        "id": uuid4(),
        "batch_id": uuid4(),
        "filename": "fixture.xlsx",
        "resolution": "accepted",
        "resolved_property_id": pid,
        "resolved_inputs_json": None,
        "parsed_inputs_json": {
            "valuation_date": "2026-03-15", "tenants": [], "cap_rate": "0.10",
            "monthly_operating_expenses": "100000", "vacancy_allowance_pct": "0.05",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_commit_one_no_inputs_raises_commit_failure() -> None:
    item = _item_record(parsed_inputs_json=None, resolved_inputs_json=None)
    pool = MagicMock()
    user = _user()
    with pytest.raises(CommitFailure) as ei:
        await commit_worker._commit_one(pool, item, user)
    assert ei.value.reason == "no_inputs"


@pytest.mark.asyncio
async def test_commit_one_no_property_link_raises() -> None:
    item = _item_record(resolved_property_id=None)
    pool = MagicMock()
    user = _user()
    with pytest.raises(CommitFailure) as ei:
        await commit_worker._commit_one(pool, item, user)
    assert ei.value.reason == "no_property_link"


@pytest.mark.asyncio
async def test_commit_batch_collects_failures_and_continues() -> None:
    """One failing item must not stop the loop; summary collects failures."""
    item_ok = _item_record(filename="ok.xlsx")
    item_bad = _item_record(filename="bad.xlsx", resolved_property_id=None)
    user = _user()
    pool = MagicMock()

    with patch("api.queries.import_item.list_for_commit",
               new_callable=AsyncMock, return_value=[item_ok, item_bad]), \
         patch("api.queries.import_item.count_already_committed",
               new_callable=AsyncMock, return_value=0), \
         patch("api.queries.import_item.all_items_terminal",
               new_callable=AsyncMock, return_value=False), \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock), \
         patch("api.services.commit_worker._commit_one",
               new_callable=AsyncMock) as mock_co, \
         patch("api.audit.audit", new_callable=AsyncMock):
        # ok succeeds, bad raises CommitFailure.
        async def side(_pool: Any, item: dict[str, Any], _user: Any) -> None:
            if item["filename"] == "bad.xlsx":
                raise CommitFailure(item["id"], item["filename"],
                                    "no_property_link", "...")
        mock_co.side_effect = side

        summary = await commit_worker.commit_batch(pool, item_ok["batch_id"], user)

    assert summary.committed == 1
    assert summary.failed == 1
    assert len(summary.failures) == 1
    assert summary.failures[0].reason == "no_property_link"


@pytest.mark.asyncio
async def test_commit_batch_terminal_flips_status_and_cleans_storage() -> None:
    user = _user()
    pool = MagicMock()
    storage = MagicMock()
    batch_id = uuid4()

    with patch("api.queries.import_item.list_for_commit",
               new_callable=AsyncMock, return_value=[]), \
         patch("api.queries.import_item.count_already_committed",
               new_callable=AsyncMock, return_value=3), \
         patch("api.queries.import_item.all_items_terminal",
               new_callable=AsyncMock, return_value=True), \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock) as mock_set, \
         patch("api.audit.audit", new_callable=AsyncMock):
        summary = await commit_worker.commit_batch(
            pool, batch_id, user, storage=storage,
        )

    mock_set.assert_called_once()
    assert mock_set.call_args.args[2] == "committed"
    storage.delete_prefix.assert_called_once_with(batch_id)
    assert summary.batch_status == "committed"
    assert summary.skipped == 3
