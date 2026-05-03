# packages/api/tests/unit/test_schemas.py
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from api.schemas.audit import AuditEntry, AuditPage
from api.schemas.common import nonempty_update
from api.schemas.entity import EntityCreate, EntityUpdate
from api.schemas.portfolio import (
    PortfolioSummary,
    TimeseriesPoint,
    TopProperty,
    ValueByEntity,
    ValueByType,
)
from api.schemas.property import PropertyCreate, PropertyUpdate
from api.schemas.snapshot import Snapshot
from api.schemas.user import AppUser


def test_nonempty_update_strips_none() -> None:
    assert nonempty_update({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_app_user_minimum_fields() -> None:
    u = AppUser(
        id=uuid4(),
        email="alice@example.com",
        display_name=None,
        role="viewer",
        created_at=datetime.now(tz=UTC),
        last_seen_at=None,
    )
    assert u.role == "viewer"


def test_app_user_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AppUser(
            id=uuid4(),
            email="a@b.com",
            display_name=None,
            role="viewer",
            created_at=datetime.now(tz=UTC),
            last_seen_at=None,
            extra_unknown_field=True,  # type: ignore[call-arg]
        )


def test_app_user_invalid_role_rejected() -> None:
    with pytest.raises(ValidationError):
        AppUser(
            id=uuid4(),
            email="a@b.com",
            display_name=None,
            role="admin",  # type: ignore[arg-type]
            created_at=datetime.now(tz=UTC),
            last_seen_at=None,
        )


# ---------------------------------------------------------------------------
# Entity schemas
# ---------------------------------------------------------------------------


def test_entity_create_happy() -> None:
    e = EntityCreate(name="Acme Pty", registration_number="2020/123456/07")
    assert e.name == "Acme Pty"


def test_entity_update_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        EntityUpdate()


def test_entity_update_name_only_accepted() -> None:
    e = EntityUpdate(name="Acme (renamed)")
    assert e.name == "Acme (renamed)"


# ---------------------------------------------------------------------------
# Property schemas
# ---------------------------------------------------------------------------


def test_property_create_defaults_to_other_type() -> None:
    p = PropertyCreate(entity_id=UUID(int=1), name="Building A")
    assert p.property_type == "other"


def test_property_update_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyUpdate()


# ---------------------------------------------------------------------------
# Snapshot, Portfolio, Audit schemas
# ---------------------------------------------------------------------------


def test_snapshot_round_trip_json() -> None:
    s = Snapshot(
        id=UUID(int=1),
        property_id=UUID(int=2),
        valuation_date=date(2026, 1, 1),
        created_by=UUID(int=3),
        created_at=datetime.now(tz=UTC),
        status="active",
        inputs_json={},
        result_json={},
        market_value=Decimal("1000000"),
        cap_rate=Decimal("0.11"),
        engine_version="0.1.0",
        source="manual",
        source_file=None,
    )
    again = Snapshot.model_validate_json(s.model_dump_json())
    assert again == s


def test_portfolio_summary_construction() -> None:
    summary = PortfolioSummary(
        total_market_value=Decimal("5000000"),
        property_count=3,
        entity_count=2,
        last_snapshot_date=date(2026, 4, 1),
        value_by_type=[ValueByType(type="office", value=Decimal("3000000"), count=2)],
        value_by_entity=[
            ValueByEntity(entity_id=UUID(int=1), name="E", value=Decimal("5000000"), count=3)
        ],
        top_properties=[TopProperty(property_id=UUID(int=2), name="P", value=Decimal("2000000"))],
    )
    assert summary.property_count == 3


def test_audit_page_construction() -> None:
    p = AuditPage(
        items=[
            AuditEntry(
                id=UUID(int=1),
                actor_id=UUID(int=2),
                actor_email="a@b.com",
                action="create",
                target_table="entity",
                target_id=UUID(int=3),
                before_json=None,
                after_json={"name": "Acme"},
                created_at=datetime.now(tz=UTC),
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )
    assert p.total == 1


def test_timeseries_point_dates() -> None:
    tp = TimeseriesPoint(
        bucket_date=date(2025, 1, 1),
        total_market_value=Decimal("1000"),
        property_count=1,
    )
    assert tp.bucket_date.year == 2025
