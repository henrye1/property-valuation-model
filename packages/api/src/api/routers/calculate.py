"""POST /calculate — preview valuation from ValuationInput; no DB write.

Valuer-only per spec §7.1. Engine ValueError surfaces as 422.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.auth import require_valuer
from api.schemas.user import AppUser

try:
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc


router = APIRouter(tags=["calculate"])


@router.post("/calculate")
async def preview_calculate(
    body: ValuationInput,
    _user: Annotated[AppUser, Depends(require_valuer)],
) -> dict[str, Any]:
    result = calculate(body)
    dumped: dict[str, Any] = result.model_dump(mode="json")
    return dumped
