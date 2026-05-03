from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from api.auth import JWTClaims, verify_jwt
from api.errors import APIError

SECRET = "test-secret-minimum-32-chars-long-for-hs256-signing"


def _mint(**claims_override: object) -> str:
    now = datetime.now(tz=UTC)
    claims: dict[str, object] = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "alice@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    claims.update(claims_override)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_verify_jwt_happy_path() -> None:
    token = _mint()
    c = verify_jwt(token, secret=SECRET)
    assert c.sub == "11111111-1111-1111-1111-111111111111"
    assert c.email == "alice@example.com"


def test_verify_jwt_expired_token_rejected() -> None:
    token = _mint(exp=int(time.time()) - 60)
    with pytest.raises(APIError) as ei:
        verify_jwt(token, secret=SECRET)
    assert ei.value.status_code == 401
    assert ei.value.code == "unauthorized"


def test_verify_jwt_wrong_signature_rejected() -> None:
    token = _mint()
    with pytest.raises(APIError):
        verify_jwt(token, secret="wrong-secret-" + "x" * 40)


def test_verify_jwt_wrong_audience_rejected() -> None:
    token = _mint(aud="anon")
    with pytest.raises(APIError):
        verify_jwt(token, secret=SECRET)


def test_verify_jwt_missing_sub_rejected() -> None:
    # Re-sign without sub
    token2 = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60, "email": "e@x.com"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(APIError):
        verify_jwt(token2, secret=SECRET)


def test_jwt_claims_is_dataclass() -> None:
    c = JWTClaims(sub="s", email="e@x.com", aud="authenticated", raw={})
    assert c.email == "e@x.com"


def test_verify_jwt_accepts_small_clock_skew_past_expiry() -> None:
    """A token expired ~5 seconds ago still verifies due to leeway."""
    token = _mint(exp=int(time.time()) - 5)
    # Within the 10-second leeway window — should succeed
    c = verify_jwt(token, secret=SECRET)
    assert c.sub == "11111111-1111-1111-1111-111111111111"
