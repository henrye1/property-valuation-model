"""JWT verification + auth dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import asyncpg
import jwt
from fastapi import Depends, Request

from api.config import Settings, get_settings
from api.db import get_db
from api.errors import APIError
from api.queries import app_user as q_app_user
from api.schemas.user import AppUser

_LEEWAY_SECONDS = 10  # clock-skew tolerance; not a security boundary


@dataclass(frozen=True, slots=True)
class JWTClaims:
    sub: str
    email: str | None
    aud: str
    raw: dict[str, Any]


def verify_jwt(token: str, *, secret: str) -> JWTClaims:
    """Decode and validate a Supabase-issued HS256 JWT.

    Raises APIError(401) on any failure.
    """
    try:
        payload = jwt.decode(
            token,
            key=secret,
            algorithms=["HS256"],
            audience="authenticated",
            leeway=_LEEWAY_SECONDS,
            options={"require": ["sub", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise APIError(
            status_code=401,
            code="unauthorized",
            message=f"Invalid token: {exc!s}",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise APIError(status_code=401, code="unauthorized", message="Missing sub.")
    return JWTClaims(
        sub=str(sub),
        email=payload.get("email"),
        aud=str(payload.get("aud", "")),
        raw=payload,
    )


def _extract_bearer(request: Request) -> str:
    authz = request.headers.get("Authorization") or request.headers.get("authorization")
    if not authz or not authz.lower().startswith("bearer "):
        raise APIError(
            status_code=401,
            code="missing_token",
            message="Missing or malformed Authorization header.",
        )
    return authz.split(" ", 1)[1].strip()


async def current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> AppUser:
    token = _extract_bearer(request)
    claims = verify_jwt(token, secret=settings.SUPABASE_JWT_SECRET.get_secret_value())
    row = await q_app_user.upsert_from_claims(
        conn,
        auth_uid=UUID(claims.sub),
        email=claims.email,
    )
    user = AppUser.model_validate(dict(row))
    request.state.user = user
    return user


async def require_valuer(
    user: Annotated[AppUser, Depends(current_user)],
) -> AppUser:
    if user.role != "valuer":
        raise APIError(
            status_code=403,
            code="forbidden",
            message="Valuer role required.",
        )
    return user
