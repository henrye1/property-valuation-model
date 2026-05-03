"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import jwt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api._version import __version__
from api.config import Settings, get_settings
from api.db import lifespan_pool
from api.errors import install_exception_handlers
from api.logging import configure_logging
from api.routers import audit as audit_router
from api.routers import calculate as calculate_router
from api.routers import entities as entities_router
from api.routers import health as health_router
from api.routers import me as me_router
from api.routers import portfolio as portfolio_router
from api.routers import properties as properties_router
from api.routers import snapshots as snapshots_router
from api.routers import users as users_router

# Routes that should NOT show the lock icon in Swagger UI (no auth required).
_PUBLIC_PATHS: frozenset[str] = frozenset({"/", "/healthz"})


def _build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """Inject a global bearerAuth security scheme so Swagger shows 'Authorize'."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste a Supabase-issued JWT (without the 'Bearer ' prefix).",
    }
    # Apply globally then strip from public paths.
    schema["security"] = [{"bearerAuth": []}]
    for path, methods in schema.get("paths", {}).items():
        if path in _PUBLIC_PATHS:
            for method_obj in methods.values():
                if isinstance(method_obj, dict):
                    method_obj["security"] = []
    app.openapi_schema = schema
    return schema


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.LOG_LEVEL, env=settings.ENV)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Initialise the JWKS client when no static HS256 secret is configured.
        # PyJWKClient.__init__ is non-blocking — the actual JWKS document is
        # fetched lazily on the first verify_jwt() call and cached for 1h.
        if settings.SUPABASE_JWT_SECRET is None:
            # types-pyjwt 2.x stubs lag — PyJWKClient exists at runtime.
            app.state.jwks_client = jwt.PyJWKClient(  # type: ignore[attr-defined]
                settings.jwks_url, cache_jwk_set=True
            )
        async with lifespan_pool(app, settings.DATABASE_URL):
            yield

    app = FastAPI(
        title="property-valuations-model API",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.allowed_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_exception_handlers(app)
    app.dependency_overrides[get_settings] = lambda: settings
    app.openapi = lambda: _build_openapi_schema(app)  # type: ignore[method-assign]

    app.include_router(health_router.router)
    app.include_router(me_router.router)
    app.include_router(entities_router.router)
    app.include_router(properties_router.router)
    app.include_router(calculate_router.router)
    app.include_router(snapshots_router.snapshots_router)
    app.include_router(snapshots_router.properties_snapshots_router)
    app.include_router(portfolio_router.router)
    app.include_router(users_router.router)
    app.include_router(audit_router.router)
    return app


app = create_app()
