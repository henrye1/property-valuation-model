"""Portfolio summary and timeseries response shapes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from api.schemas.common import APIBase
from api.schemas.property import PropertyType


class ValueByType(APIBase):
    type: PropertyType
    value: Decimal
    count: int


class ValueByEntity(APIBase):
    entity_id: UUID
    name: str
    value: Decimal
    count: int


class TopProperty(APIBase):
    property_id: UUID
    name: str
    value: Decimal


class PortfolioSummary(APIBase):
    total_market_value: Decimal
    property_count: int
    entity_count: int
    last_snapshot_date: date | None
    value_by_type: list[ValueByType]
    value_by_entity: list[ValueByEntity]
    top_properties: list[TopProperty]


class TimeseriesPoint(APIBase):
    bucket_date: date
    total_market_value: Decimal
    property_count: int


class PortfolioTimeseries(APIBase):
    bucket: str
    points: list[TimeseriesPoint]
