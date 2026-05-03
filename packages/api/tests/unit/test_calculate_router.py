"""Unit tests for POST /calculate router."""
from __future__ import annotations

import datetime as dt
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import current_user, require_valuer
from api.errors import install_exception_handlers
from api.schemas.user import AppUser


def _stub_valuer() -> AppUser:
    return AppUser(
        id=UUID(int=1),
        email="v@x.com",
        display_name=None,
        role="valuer",
        created_at=dt.datetime.now(tz=dt.UTC),
        last_seen_at=None,
    )


def _app_for_calc() -> FastAPI:
    from api.routers import calculate as calculate_router

    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(calculate_router.router)
    stub = _stub_valuer()
    app.dependency_overrides[current_user] = lambda: stub
    app.dependency_overrides[require_valuer] = lambda: stub
    return app


def _payload() -> dict:
    return {
        "valuation_date": dt.date(2026, 1, 1).isoformat(),
        "tenants": [
            {
                "description": "Office",
                "rentable_area_m2": "100",
                "rent_per_m2_pm": "85",
                "annual_escalation_pct": "0",
            }
        ],
        "monthly_operating_expenses": "0",
        "vacancy_allowance_pct": "0",
        "cap_rate": "0.10",
    }


def test_calculate_happy_path_returns_result() -> None:
    with TestClient(_app_for_calc()) as client:
        r = client.post("/calculate", json=_payload())
    assert r.status_code == 200
    assert "market_value" in r.json()
    assert "engine_version" in r.json()


def test_calculate_invalid_input_422() -> None:
    payload = _payload()
    payload["cap_rate"] = "0"
    with TestClient(_app_for_calc(), raise_server_exceptions=False) as client:
        r = client.post("/calculate", json=payload)
    assert r.status_code == 422
