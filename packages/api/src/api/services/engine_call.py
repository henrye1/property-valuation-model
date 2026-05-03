"""Wrapper for valuation_engine.calculate that maps ValueError to APIError(422).

Three (now four) callers: routers/calculate.py, routers/snapshots.py,
routers/imports.py (PATCH edit path), services/commit_worker.py.

The pattern is identical at all sites; this module exists to avoid a
fourth copy of the same try/except.
"""
from __future__ import annotations

from api.errors import APIError

try:
    from valuation_engine import calculate as _calculate
    from valuation_engine.models import ValuationInput, ValuationResult
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc


def run_engine(inputs: ValuationInput) -> ValuationResult:
    """calculate(inputs); ValueError -> APIError(422, engine_validation_error)."""
    try:
        return _calculate(inputs)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            code="engine_validation_error",
            message=str(exc),
        ) from exc
