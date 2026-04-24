"""ValuationSnapshot response shape.

Inputs are validated by the engine's own ValuationInput; the API does not
redefine it. The Snapshot response includes the frozen inputs_json and
result_json as dicts (not re-validated on read).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from api.schemas.common import APIBase

SnapshotStatus = Literal["active", "superseded"]
SnapshotSource = Literal["manual", "excel_import"]


class Snapshot(APIBase):
    id: UUID
    property_id: UUID
    valuation_date: date
    created_by: UUID
    created_at: datetime
    status: SnapshotStatus
    inputs_json: dict[str, Any]
    result_json: dict[str, Any]
    market_value: Decimal
    cap_rate: Decimal
    engine_version: str
    source: SnapshotSource
    source_file: str | None
