"""Liveness + root redirect. No auth, no DB."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from api._version import __version__ as api_version

try:
    from valuation_engine import __version__ as engine_version
except ImportError:  # pragma: no cover
    engine_version = "unknown"


router = APIRouter(tags=["health"])


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Browser convenience — bare root redirects to the Swagger UI."""
    return RedirectResponse(url="/docs", status_code=307)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "api_version": api_version,
        "engine_version": engine_version,
    }
