from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

import jwt
from fastapi import FastAPI

from ephoros_api.adapters.health import ping_postgres, ping_redis
from ephoros_api.api.problems import install_problem_handlers
from ephoros_api.api.v1 import health, me
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
    settings = settings or Settings()  # fields come from env
    app.state.settings = settings
    # keys cached; an unknown kid triggers one refetch (spec §16)
    # shortcut: cached keys are never evicted, add eviction when Better Auth key rotation is enabled
    app.state.jwk_client = jwt.PyJWKClient(
        settings.jwks_url,
        cache_keys=True,
        lifespan=300,
        timeout=settings.readiness_timeout_s,  # default 30 s would stall threads under one lock
    )
    install_problem_handlers(app)
    app.include_router(health.router)
    app.include_router(me.router)
    return app
