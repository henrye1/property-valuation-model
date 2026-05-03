"""DTOs for /imports endpoints + commit summary.

Mirrors the column shape of import_batch + import_item. Validation enforces
the resolution-state matrix from spec §7.5.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParseStatus = Literal["ok", "warning", "error"]
Resolution = Literal["pending", "accepted", "rejected", "edited", "committed"]
BatchStatus = Literal["parsing", "review", "committed", "cancelled"]


class ImportItemWarning(BaseModel):
    code: str
    message: str
    field_path: str | None = None


class ImportItemSuggestion(BaseModel):
    property_id: UUID
    property_name: str
    entity_id: UUID
    entity_name: str
    score: Annotated[Decimal, Field(ge=0, le=1)]
    auto_linked: bool


class ImportItem(BaseModel):
    """Full row shape returned by GET /imports/{id} and PATCH responses."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    filename: str
    parse_status: ParseStatus
    building_name: str | None
    spreadsheet_market_value: Decimal | None
    recomputed_market_value: Decimal | None
    diff_pct: Decimal | None
    warnings: list[ImportItemWarning] = []
    errors: list[ImportItemWarning] = []
    suggestion: ImportItemSuggestion | None = None
    resolution: Resolution
    resolved_property_id: UUID | None
    parsed_inputs: dict[str, Any] | None
    computed_result: dict[str, Any] | None
    resolved_inputs: dict[str, Any] | None


class ImportItemPatch(BaseModel):
    """PATCH /imports/{id}/items/{iid} body. Per-field-conditional validation."""
    resolution: Literal["accepted", "rejected", "edited"]
    resolved_property_id: UUID | None = None
    resolved_inputs: dict[str, Any] | None = None
    resolution_notes: str | None = None

    @model_validator(mode="after")
    def _validate_state(self) -> ImportItemPatch:
        if self.resolution == "edited":
            if self.resolved_inputs is None:
                raise ValueError("resolution='edited' requires resolved_inputs")
            if self.resolved_property_id is None:
                raise ValueError("resolution='edited' requires resolved_property_id")
        elif self.resolution == "accepted":
            # Server-side handler must verify auto_linked OR resolved_property_id.
            # Schema-level: if no auto-link is in play, the body must carry an id.
            # We can't see the row from here, so the router enforces the auto-link
            # branch; schema only catches the "no id at all" case.
            if self.resolved_property_id is None:
                raise ValueError(
                    "resolution='accepted' requires resolved_property_id "
                    "unless the row is already auto_linked"
                )
        # 'rejected' allows any payload; resolved_* fields are simply ignored downstream.
        return self


class ImportBatchCounts(BaseModel):
    pending:   int = 0
    accepted:  int = 0
    rejected:  int = 0
    edited:    int = 0
    committed: int = 0


class _ActorRef(BaseModel):
    id: str
    email: str | None = None


class ImportBatchListItem(BaseModel):
    id: UUID
    uploaded_by: _ActorRef
    uploaded_at: str
    file_count: int
    status: BatchStatus
    counts: ImportBatchCounts


class ImportBatchList(BaseModel):
    items: list[ImportBatchListItem]
    total: int


class ImportBatch(BaseModel):
    """Full batch detail with inline items (GET /imports/{id})."""
    id: UUID
    uploaded_by: _ActorRef
    uploaded_at: str
    file_count: int
    status: BatchStatus
    notes: str | None
    items: list[ImportItem]


class ImportCreated(BaseModel):
    """Response for POST /imports (202)."""
    batch_id: UUID
    file_count: int
    status: Literal["parsing"]


class CommitFailure(BaseModel):
    item_id: UUID
    filename: str
    reason: str
    message: str


class CommitSummary(BaseModel):
    batch_id: UUID
    summary: dict[str, int]
    failures: list[CommitFailure]
    batch_status: Literal["committed", "review"]
