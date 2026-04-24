"""Query functions for app_user."""
from __future__ import annotations

from typing import cast
from uuid import UUID

import asyncpg

_COLS = "id, email, display_name, role, created_at, last_seen_at"


async def upsert_from_claims(
    conn: asyncpg.Connection,
    *,
    auth_uid: UUID,
    email: str | None,
) -> asyncpg.Record:
    """Create the user row on first sight; always bump last_seen_at.

    Default role is 'viewer' on first insert. Returns the post-update row.
    """
    row = await conn.fetchrow(
        f"""
        insert into public.app_user (id, email, role, last_seen_at)
        values ($1, $2, 'viewer', now())
        on conflict (id) do update
            set last_seen_at = excluded.last_seen_at,
                email = coalesce(excluded.email, public.app_user.email)
        returning {_COLS}
        """,
        auth_uid,
        email,
    )
    return cast("asyncpg.Record", row)


async def list_users(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"select {_COLS} from public.app_user order by created_at asc"
    )
    return list(rows)


async def get_user(conn: asyncpg.Connection, user_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.app_user where id = $1",
        user_id,
    )
