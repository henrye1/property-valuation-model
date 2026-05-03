"""Property fuzzy-match for Excel import auto-linking.

Pure SQL via pg_trgm. Threshold + max-suggestions are module-level constants
so they can be tuned from production data later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

import asyncpg

SIMILARITY_THRESHOLD: float = 0.5
MAX_SUGGESTIONS: int = 5


@dataclass(frozen=True)
class Suggestion:
    id: UUID
    entity_id: UUID
    name: str
    score: Decimal


@dataclass(frozen=True)
class MatchResult:
    property_id: UUID | None
    score: Decimal | None
    auto_linked: bool
    suggestions: list[Suggestion] = field(default_factory=list)


async def suggest(
    conn: asyncpg.Connection, building_name: str | None,
) -> MatchResult:
    """Match `building_name` against public.property.

    Logic:
    1. Exact (case + whitespace normalised) match → if exactly one, auto-link.
    2. Multiple exact matches → suggest all, no auto-link.
    3. No exact match → pg_trgm similarity ≥ SIMILARITY_THRESHOLD, top N suggestions.
    """
    if not building_name or not building_name.strip():
        return MatchResult(None, None, False, [])

    exact = await conn.fetch(
        """
        select id, entity_id, name
          from public.property
         where deleted_at is null
           and lower(trim(name)) = lower(trim($1))
        """,
        building_name,
    )

    if len(exact) == 1:
        row = exact[0]
        return MatchResult(
            property_id=row["id"],
            score=Decimal("1.0"),
            auto_linked=True,
            suggestions=[],
        )

    if len(exact) > 1:
        sugs = [
            Suggestion(id=r["id"], entity_id=r["entity_id"],
                       name=r["name"], score=Decimal("1.0"))
            for r in exact
        ]
        return MatchResult(None, None, False, sugs)

    fuzzy = await conn.fetch(
        """
        select id, entity_id, name, similarity(name, $1) as score
          from public.property
         where deleted_at is null
           and similarity(name, $1) >= $2
         order by score desc
         limit $3
        """,
        building_name, SIMILARITY_THRESHOLD, MAX_SUGGESTIONS,
    )
    sugs = [
        Suggestion(id=r["id"], entity_id=r["entity_id"],
                   name=r["name"], score=Decimal(str(r["score"])))
        for r in fuzzy
    ]
    return MatchResult(None, None, False, sugs)
