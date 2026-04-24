"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api._version import __version__
from api.config import Settings, get_settings
from api.db import lifespan_pool
from api.errors import install_exception_handlers
from api.logging import configure_logging
from api.routers import calculate as calculate_router
from api.routers import entities as entities_router
from api.routers import health as health_router
from api.routers import me as me_router
from api.routers import properties as properties_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.LOG_LEVEL, env=settings.ENV)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    app.include_router(health_router.router)
    app.include_router(me_router.router)
    app.include_router(entities_router.router)
    app.include_router(properties_router.router)
    app.include_router(calculate_router.router)
    return app


app = create_app()
