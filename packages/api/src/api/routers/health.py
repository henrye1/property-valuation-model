"""Liveness endpoint. No auth, no DB."""
from __future__ import annotations

from fastapi import APIRouter

from api._version import __version__ as api_version

try:
    from valuation_engine import __version__ as engine_version
except ImportError:  # pragma: no cover
    engine_version = "unknown"


router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "api_version": api_version,
        "engine_version": engine_version,
    }
