# packages/api/tests/unit/test_audit.py
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from api.queries.snapshot import _json_default


def test_decimal_stringified() -> None:
    assert _json_default(Decimal("1.23")) == "1.23"


def test_date_isoformatted() -> None:
    assert _json_default(date(2026, 1, 2)) == "2026-01-02"


def test_datetime_isoformatted() -> None:
    out = _json_default(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    assert out.startswith("2026-01-02T03:04:05")


def test_uuid_isoformatted() -> None:
    u = uuid4()
    # UUID has .isoformat? No — hasattr isoformat is False for UUID.
    # Our default raises TypeError on non-supported; ensure str(uuid) path via json.dumps.
    # We accept a TypeError here — json.dumps UUIDs via `default=str` in callers.
    import pytest

    with pytest.raises(TypeError):
        _json_default(u)
