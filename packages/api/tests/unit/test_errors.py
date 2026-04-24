from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from api.errors import (
    APIError,
    install_exception_handlers,
)


class _Body(BaseModel):
    name: str = Field(min_length=1)


def _app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.post("/echo")
    def echo(body: _Body) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/boom")
    def boom() -> None:
        raise APIError(status_code=409, code="has_live_children",
                       message="blocked", details={"blocking_count": 3})

    @app.get("/unexpected")
    def unexpected() -> None:
        raise RuntimeError("kaboom")

    @app.get("/not_found")
    def not_found() -> None:
        raise HTTPException(status_code=404)

    return app


def test_pydantic_validation_error_returns_422_envelope() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.post("/echo", json={"name": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "invalid_input"
    assert isinstance(body["error"]["details"]["errors"], list)


def test_api_error_propagates_code_and_details() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "has_live_children",
            "message": "blocked",
            "details": {"blocking_count": 3},
        }
    }


def test_unhandled_exception_returns_500_internal_error() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/unexpected")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"


def test_http_exception_404_maps_to_not_found() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/not_found")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
