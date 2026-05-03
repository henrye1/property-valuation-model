"""JWT verification + auth dependencies.

Two verification paths are supported:

* HS256 with a shared secret — legacy Supabase + tests. Pass `secret=...`.
* JWKS (RS256/ES256) — modern Supabase projects with rotatable signing keys.
  Pass `jwks_client=PyJWKClient(jwks_url)`.

Exactly one of `secret` / `jwks_client` must be provided.
"""
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
_JWKS_ALGORITHMS = ["RS256", "ES256"]


@dataclass(frozen=True, slots=True)
class JWTClaims:
    sub: str
    email: str | None
    aud: str
    raw: dict[str, Any]


def verify_jwt(
    token: str,
    *,
    secret: str | None = None,
    # types-pyjwt 2.x stubs lag the runtime API for PyJWKClient.
    jwks_client: jwt.PyJWKClient | None = None,  # type: ignore[name-defined]
) -> JWTClaims:
    """Decode and validate a Supabase-issued JWT.

    Pick exactly one verification mode:

    * `secret` → HS256 (legacy Supabase + tests).
    * `jwks_client` → public-key verification via JWKS (modern Supabase ES256/RS256).

    Raises APIError(401) on any failure. Raises APIError(500) if neither / both modes
    are supplied (programmer error).
    """
    if (secret is None) == (jwks_client is None):
        raise APIError(
            status_code=500,
            code="auth_misconfigured",
            message="Provide exactly one of secret or jwks_client to verify_jwt().",
        )

    try:
        if jwks_client is not None:
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                key=signing_key,
                algorithms=_JWKS_ALGORITHMS,
                audience="authenticated",
                leeway=_LEEWAY_SECONDS,
                options={"require": ["sub", "exp"]},
            )
        else:
            assert secret is not None  # narrowing for mypy
            payload = jwt.decode(
                token,
                key=secret,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=_LEEWAY_SECONDS,
                options={"require": ["sub", "exp"]},
            )
    except jwt.PyJWKClientError as exc:  # type: ignore[attr-defined]
        raise APIError(
            status_code=401,
            code="unauthorized",
            message=f"JWKS lookup failed: {exc!s}",
        ) from exc
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
    if settings.SUPABASE_JWT_SECRET is not None:
        claims = verify_jwt(token, secret=settings.SUPABASE_JWT_SECRET.get_secret_value())
    else:
        jwks_client: jwt.PyJWKClient | None = getattr(  # type: ignore[name-defined]
            request.app.state, "jwks_client", None
        )
        if jwks_client is None:
            raise APIError(
                status_code=500,
                code="auth_misconfigured",
                message="No JWT secret and no JWKS client; auth cannot proceed.",
            )
        claims = verify_jwt(token, jwks_client=jwks_client)
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
