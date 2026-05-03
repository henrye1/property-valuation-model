"""Verify RLS policies enforce viewer-cannot-mutate / valuer-can-mutate
when accessed via a real JWT (not the service-role-bypass path)."""
from __future__ import annotations

import io

import asyncpg
import jwt
import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _connect_as_role(dsn: str, role_jwt: str) -> asyncpg.Connection:
    """Connect as the 'authenticated' Postgres role using a Supabase JWT.

    Uses the Postgres connection string with `set role authenticated` and
    sets request-context JWT claims so RLS policies see auth.uid().

    The dsn must be the live integration DSN (passed via the `settings`
    fixture, NOT read from os.environ — the unit test conftest monkey-patches
    DATABASE_URL to "postgresql://unused" via an autouse fixture).
    """
    conn = await asyncpg.connect(dsn=dsn)
    await conn.execute("set role authenticated")
    payload = jwt.decode(role_jwt, options={"verify_signature": False})
    sub = payload["sub"]
    # set_config(name, value, is_local=true) — is_local=true scopes to the txn,
    # but we're outside a txn so use is_local=false to keep it for the connection.
    await conn.execute(
        "select set_config('request.jwt.claims', $1, false)",
        f'{{"sub":"{sub}"}}',
    )
    return conn


@pytest.mark.asyncio
async def test_viewer_cannot_insert_import_batch(
    valuer_client, viewer, settings,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202

    viewer_uid, viewer_headers = viewer
    viewer_token = viewer_headers["Authorization"].split(" ", 1)[1]
    conn = await _connect_as_role(settings.DATABASE_URL, viewer_token)
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(
                """
                insert into public.import_batch (uploaded_by, file_count, status)
                values ($1, 1, 'parsing')
                """,
                viewer_uid,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_viewer_can_select_import_batch(
    valuer_client, viewer, settings,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202

    _, viewer_headers = viewer
    viewer_token = viewer_headers["Authorization"].split(" ", 1)[1]
    conn = await _connect_as_role(settings.DATABASE_URL, viewer_token)
    try:
        rows = await conn.fetch("select id from public.import_batch")
        assert len(rows) >= 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_valuer_can_insert_import_batch(valuer, settings) -> None:
    valuer_uid, valuer_headers = valuer
    valuer_token = valuer_headers["Authorization"].split(" ", 1)[1]
    conn = await _connect_as_role(settings.DATABASE_URL, valuer_token)
    try:
        row = await conn.fetchrow(
            """
            insert into public.import_batch (uploaded_by, file_count, status)
            values ($1, 1, 'parsing')
            returning id
            """,
            valuer_uid,
        )
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_uploaded_by_must_match_auth_uid(valuer, viewer, settings) -> None:
    """Even valuers can't insert a row claiming someone else uploaded it."""
    _, valuer_headers = valuer
    viewer_uid, _ = viewer
    valuer_token = valuer_headers["Authorization"].split(" ", 1)[1]
    conn = await _connect_as_role(settings.DATABASE_URL, valuer_token)
    try:
        # The RLS policy's WITH CHECK fires; some Postgres versions surface
        # this as a generic InsufficientPrivilegeError or CheckViolation.
        with pytest.raises(
            (asyncpg.exceptions.InsufficientPrivilegeError,
             asyncpg.exceptions.CheckViolationError),
        ):
            await conn.execute(
                """
                insert into public.import_batch (uploaded_by, file_count, status)
                values ($1, 1, 'parsing')
                """,
                viewer_uid,  # someone else's id
            )
    finally:
        await conn.close()
