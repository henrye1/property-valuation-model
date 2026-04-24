"""Portfolio analytical queries. Latest-snapshot-per-property is the key CTE."""
from __future__ import annotations

import asyncpg

_LATEST_CTE = """
with latest as (
    select distinct on (s.property_id)
        s.property_id, s.market_value, s.valuation_date
    from public.valuation_snapshot s
    join public.property p on p.id = s.property_id and p.deleted_at is null
    join public.entity e on e.id = p.entity_id and e.deleted_at is null
    where s.status = 'active'
    order by s.property_id, s.valuation_date desc, s.created_at desc
)
"""


async def summary(
    conn: asyncpg.Connection, *, top_limit: int = 10
) -> dict[str, object]:
    totals = await conn.fetchrow(
        _LATEST_CTE
        + """
        select
            coalesce(sum(latest.market_value), 0) as total_market_value,
            count(*)::int as property_count,
            (select count(*)::int from public.entity where deleted_at is null) as entity_count,
            max(latest.valuation_date) as last_snapshot_date
        from latest
        """
    )

    by_type = await conn.fetch(
        _LATEST_CTE
        + """
        select p.property_type as type,
               coalesce(sum(latest.market_value), 0) as value,
               count(*)::int as count
        from latest
        join public.property p on p.id = latest.property_id
        group by p.property_type
        order by value desc
        """
    )

    by_entity = await conn.fetch(
        _LATEST_CTE
        + """
        select e.id as entity_id,
               e.name as name,
               coalesce(sum(latest.market_value), 0) as value,
               count(*)::int as count
        from latest
        join public.property p on p.id = latest.property_id
        join public.entity e on e.id = p.entity_id
        group by e.id, e.name
        order by value desc
        """
    )

    top_props = await conn.fetch(
        _LATEST_CTE
        + """
        select p.id as property_id, p.name as name, latest.market_value as value
        from latest
        join public.property p on p.id = latest.property_id
        order by latest.market_value desc
        limit $1
        """,
        top_limit,
    )

    assert totals is not None
    return {
        "total_market_value": totals["total_market_value"],
        "property_count": totals["property_count"],
        "entity_count": totals["entity_count"],
        "last_snapshot_date": totals["last_snapshot_date"],
        "value_by_type": [dict(r) for r in by_type],
        "value_by_entity": [dict(r) for r in by_entity],
        "top_properties": [dict(r) for r in top_props],
    }


async def timeseries_year(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        """
        with active as (
            select distinct on (s.property_id, date_trunc('year', s.valuation_date))
                s.property_id,
                date_trunc('year', s.valuation_date)::date as bucket_date,
                s.market_value
            from public.valuation_snapshot s
            join public.property p on p.id = s.property_id and p.deleted_at is null
            order by s.property_id, date_trunc('year', s.valuation_date),
                     s.valuation_date desc, s.created_at desc
        )
        select bucket_date,
               coalesce(sum(market_value), 0) as total_market_value,
               count(*)::int as property_count
        from active
        group by bucket_date
        order by bucket_date asc
        """
    )
    return list(rows)
