"""Portfolio endpoints."""
from __future__ import annotations

from typing import Annotated, Literal, cast

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.auth import current_user
from api.db import get_db
from api.queries import portfolio as q_portfolio
from api.schemas.portfolio import (
    PortfolioSummary,
    PortfolioTimeseries,
    TimeseriesPoint,
    TopProperty,
    ValueByEntity,
    ValueByType,
)
from api.schemas.user import AppUser

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_summary(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PortfolioSummary:
    raw = await q_portfolio.summary(conn, top_limit=limit)
    return PortfolioSummary(
        total_market_value=raw["total_market_value"],
        property_count=raw["property_count"],
        entity_count=raw["entity_count"],
        last_snapshot_date=raw["last_snapshot_date"],
        value_by_type=[
            ValueByType(**r) for r in cast(list[dict[str, object]], raw["value_by_type"])
        ],
        value_by_entity=[
            ValueByEntity(**r) for r in cast(list[dict[str, object]], raw["value_by_entity"])
        ],
        top_properties=[
            TopProperty(**r) for r in cast(list[dict[str, object]], raw["top_properties"])
        ],
    )


@router.get("/timeseries", response_model=PortfolioTimeseries)
async def get_timeseries(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    bucket: Annotated[Literal["year"], Query()] = "year",
) -> PortfolioTimeseries:
    rows = await q_portfolio.timeseries_year(conn)
    points = [TimeseriesPoint(**dict(r)) for r in rows]
    return PortfolioTimeseries(bucket=bucket, points=points)
