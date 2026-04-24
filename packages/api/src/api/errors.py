"""Unified error envelope. All API errors emit:
    {"error": {"code": str, "message": str, "details": dict | None}}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class APIError(Exception):
    """Structured, user-facing API error."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


_STATUS_CODE_MAP: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Bad request."),
    401: ("unauthorized", "Unauthorized."),
    403: ("forbidden", "Forbidden."),
    404: ("not_found", "Not found."),
    409: ("conflict", "Conflict."),
    410: ("gone", "Gone."),
    422: ("invalid_input", "Invalid input."),
    429: ("rate_limited", "Too many requests."),
    500: ("internal_error", "Internal server error."),
    503: ("service_unavailable", "Service unavailable."),
}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_input", "Invalid input.", {"errors": exc.errors()}),
        )

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_input", "Invalid input.", {"errors": exc.errors()}),
        )

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        # Engine ValueErrors surface as 422.
        # TODO: narrow this to the /calculate call site once that router ships
        # (Task 25) — catching bare ValueError globally risks masking non-engine
        # bugs with a misleading "engine_validation_error" code.
        return JSONResponse(
            status_code=422,
            content=_envelope("engine_validation_error", str(exc), {}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, default_msg = _STATUS_CODE_MAP.get(
            exc.status_code, ("unexpected_error", "Unexpected error.")
        )
        message = exc.detail if isinstance(exc.detail, str) else default_msg
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            err = exc.detail.get("error")
            if isinstance(err, dict):
                code = str(err.get("code", code))
                message = str(err.get("message", message))
                raw_details = err.get("details") or {}
                if isinstance(raw_details, dict):
                    details = raw_details
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, message, details),
        )

    # FastAPI's HTTPException is a subclass of Starlette's. Both keys must
    # be registered: Starlette internals raise the base type; FastAPI routers
    # raise the subtype. The MRO lookup hits the subtype handler first and
    # delegates to the Starlette-typed handler.
    @app.exception_handler(HTTPException)
    async def _fastapi_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return await _http_exception(request, exc)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Internal server error.", {}),
        )
