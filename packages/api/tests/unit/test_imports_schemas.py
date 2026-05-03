"""DTO validation tests for imports endpoints."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schemas.imports import (
    CommitFailure,
    CommitSummary,
    ImportBatch,
    ImportBatchCounts,
    ImportBatchListItem,
    ImportItemPatch,
    ImportItemSuggestion,
    ImportItemWarning,
)


def test_import_item_patch_accepted_requires_property_id_when_no_auto_link() -> None:
    """resolution=accepted with auto_linked=false on the row must carry resolved_property_id."""
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="accepted", resolved_property_id=None,
                        resolved_inputs=None, resolution_notes=None)


def test_import_item_patch_edited_requires_inputs_and_property_id() -> None:
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="edited", resolved_property_id=uuid4(),
                        resolved_inputs=None, resolution_notes=None)
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="edited", resolved_property_id=None,
                        resolved_inputs={"valuation_date": "2026-03-15"},
                        resolution_notes=None)


def test_import_item_patch_rejected_ignores_other_fields() -> None:
    """resolution=rejected accepts a body with property_id/inputs but they're permitted."""
    obj = ImportItemPatch(resolution="rejected", resolved_property_id=uuid4(),
                          resolved_inputs={"x": 1}, resolution_notes="bad data")
    assert obj.resolution == "rejected"


def test_import_item_patch_accepted_with_property_id_passes() -> None:
    obj = ImportItemPatch(resolution="accepted", resolved_property_id=uuid4(),
                          resolved_inputs=None, resolution_notes=None)
    assert obj.resolution == "accepted"


def test_import_batch_counts_zero_default_for_missing_keys() -> None:
    counts = ImportBatchCounts()
    assert counts.pending == 0
    assert counts.accepted == 0
    assert counts.rejected == 0
    assert counts.committed == 0


def test_commit_summary_validates_minimal() -> None:
    s = CommitSummary(
        batch_id=uuid4(),
        summary={"committed": 8, "failed": 1, "skipped": 3},
        failures=[CommitFailure(item_id=uuid4(), filename="x.xlsx",
                                reason="no_inputs", message="...")],
        batch_status="review",
    )
    assert s.summary["failed"] == 1
    assert s.batch_status == "review"


def test_import_item_warning_round_trips() -> None:
    w = ImportItemWarning(code="lease_expired", message="...", field_path="tenants[2]")
    assert w.model_dump()["field_path"] == "tenants[2]"


def test_import_item_suggestion_score_bounded() -> None:
    """score must be in [0, 1] (pg_trgm similarity range)."""
    with pytest.raises(ValidationError):
        ImportItemSuggestion(property_id=uuid4(), property_name="x",
                             entity_id=uuid4(), entity_name="y",
                             score=Decimal("1.5"), auto_linked=False)


def test_import_batch_list_item_includes_counts() -> None:
    """List item shape carries per-status counts (no separate fetch)."""
    item = ImportBatchListItem(
        id=uuid4(),
        uploaded_by={"id": str(uuid4()), "email": "a@b"},
        uploaded_at="2026-05-03T12:00:00Z",
        file_count=3,
        status="review",
        counts=ImportBatchCounts(pending=1, accepted=2),
    )
    assert item.counts.accepted == 2


def test_import_batch_detail_includes_items_inline() -> None:
    """Detail shape inlines items (no N+1 pagination in v1)."""
    batch = ImportBatch(
        id=uuid4(),
        uploaded_by={"id": str(uuid4()), "email": "a@b"},
        uploaded_at="2026-05-03T12:00:00Z",
        file_count=1,
        status="review",
        notes=None,
        items=[],
    )
    assert batch.items == []
