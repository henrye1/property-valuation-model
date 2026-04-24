"""JWT verification + auth dependencies.

Dependencies that talk to the DB (current_user, require_valuer) are added in
Task 11 once the `app_user` queries exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from api.errors import APIError


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
