"""Tests for matcher's pure logic + SQL parameter composition.
Real DB queries are exercised in integration tests."""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from api.services import matcher


def _record(d: dict[str, Any]) -> Any:
    """Mimic asyncpg.Record's dict-style access."""
    class R(dict[str, Any]):
        def __getitem__(self, key: str) -> Any:
            return dict.__getitem__(self, key)
    return R(d)


@pytest.mark.asyncio
async def test_no_building_name_returns_empty_match() -> None:
    conn = AsyncMock()
    result = await matcher.suggest(conn, None)
    assert result.property_id is None
    assert result.score is None
    assert result.auto_linked is False
    assert result.suggestions == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_blank_building_name_returns_empty_match() -> None:
    conn = AsyncMock()
    result = await matcher.suggest(conn, "   ")
    assert result.property_id is None
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_single_exact_match_auto_links() -> None:
    pid = uuid4()
    eid = uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        # First fetch: exact match query, returns 1 row
        [_record({"id": pid, "entity_id": eid, "name": "55 Empire Road"})],
    ]
    result = await matcher.suggest(conn, "  55 EMPIRE ROAD  ")  # case + whitespace
    assert result.property_id == pid
    assert result.auto_linked is True
    assert result.score == Decimal("1.0") or result.score == 1.0
    assert result.suggestions == []
    # Only the exact-match query ran, not the fuzzy fallback.
    assert conn.fetch.call_count == 1


@pytest.mark.asyncio
async def test_multiple_exact_matches_no_auto_link() -> None:
    """When two properties share a name, reviewer must disambiguate."""
    p1, p2 = uuid4(), uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [_record({"id": p1, "entity_id": uuid4(), "name": "Empire Road"}),
         _record({"id": p2, "entity_id": uuid4(), "name": "Empire Road"})],
    ]
    result = await matcher.suggest(conn, "Empire Road")
    assert result.property_id is None
    assert result.auto_linked is False
    assert len(result.suggestions) == 2
    assert {s.id for s in result.suggestions} == {p1, p2}


@pytest.mark.asyncio
async def test_fuzzy_match_returns_suggestions() -> None:
    pid = uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [],  # exact returns nothing
        [_record({"id": pid, "entity_id": uuid4(),
                  "name": "55 Empire Road", "score": 0.78})],
    ]
    result = await matcher.suggest(conn, "55 Empire Rd")
    assert result.property_id is None
    assert result.auto_linked is False
    assert len(result.suggestions) == 1
    assert result.suggestions[0].id == pid
    assert pytest.approx(float(result.suggestions[0].score), abs=0.01) == 0.78


@pytest.mark.asyncio
async def test_fuzzy_below_threshold_returns_nothing() -> None:
    conn = AsyncMock()
    conn.fetch.side_effect = [[], []]  # exact none, fuzzy none
    result = await matcher.suggest(conn, "wildly different name")
    assert result.suggestions == []


def test_threshold_constant_is_documented() -> None:
    assert matcher.SIMILARITY_THRESHOLD == 0.5
    assert matcher.MAX_SUGGESTIONS == 5
