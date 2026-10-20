from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ephoros_api.api.v1 import health
from ephoros_api.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Ephoros API",
        version="0.1.0",
        lifespan=lifespan,
        # operation IDs = function names, so the generated client exposes healthz(), readyz()
        generate_unique_id_function=lambda route: route.name,
    )
    app.state.settings = settings or Settings()  # fields come from env
    app.include_router(health.router)
    return app
