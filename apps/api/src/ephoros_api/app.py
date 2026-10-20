from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from ephoros_api.adapters.health import ping_postgres, ping_redis
from ephoros_api.api.problems import install_problem_handlers
from ephoros_api.api.v1 import health
from ephoros_api.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.checks = {
        "postgres": partial(ping_postgres, settings.database_url),
        "redis": partial(ping_redis, settings.redis_url),
    }
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
    install_problem_handlers(app)
    app.include_router(health.router)
    return app
