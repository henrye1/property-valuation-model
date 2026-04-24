# packages/api/tests/unit/test_schemas.py
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from api.schemas.common import nonempty_update
from api.schemas.entity import EntityCreate, EntityUpdate
from api.schemas.property import PropertyCreate, PropertyUpdate
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
