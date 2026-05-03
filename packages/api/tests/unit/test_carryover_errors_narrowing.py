"""ValueError outside scoped engine wrappers must surface as 500, not 422.
Engine ValueErrors raised inside the routers' own scoped wrappers continue
to surface as 422 'engine_validation_error'."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import APIError, install_exception_handlers


@pytest.fixture
def app_with_handlers() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)
    return app


def test_unscoped_value_error_returns_500(app_with_handlers: FastAPI) -> None:
    """A bare ValueError from app code must NOT be masked as engine_validation_error."""

    @app_with_handlers.get("/oops")
    async def _oops() -> Any:
        raise ValueError("nothing to do with the engine")

    client = TestClient(app_with_handlers, raise_server_exceptions=False)
    resp = client.get("/oops")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"


def test_scoped_engine_value_error_returns_422(app_with_handlers: FastAPI) -> None:
    """Routers that call the engine wrap their own ValueError → APIError(422)."""

    @app_with_handlers.get("/calc")
    async def _calc() -> Any:
        try:
            raise ValueError("cap_rate must be > 0")
        except ValueError as exc:
            raise APIError(
                status_code=422,
                code="engine_validation_error",
                message=str(exc),
            ) from exc

    client = TestClient(app_with_handlers)
    resp = client.get("/calc")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "engine_validation_error"
    assert body["error"]["message"] == "cap_rate must be > 0"
