# packages/api/tests/unit/test_schemas.py
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schemas.common import nonempty_update
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
