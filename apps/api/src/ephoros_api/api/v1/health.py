import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ephoros_api.api.problems import Problem, problem_response
from ephoros_api.config import Settings

router = APIRouter(prefix="/api/v1", tags=["ops"])

Check = Callable[[], Awaitable[None]]


class Health(BaseModel):
    status: Literal["ok"]


class Readiness(BaseModel):
    status: Literal["ok"]
    checks: dict[str, str]


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_checks(request: Request) -> dict[str, Check]:
    checks: dict[str, Check] = request.app.state.checks
    return checks


@router.get("/healthz")
async def healthz() -> Health:
    return Health(status="ok")


@router.get(
    "/readyz",
    response_model=Readiness,
    responses={503: {"model": Problem, "content": {"application/problem+json": {}}}},
)
async def readyz(
    checks: Annotated[dict[str, Check], Depends(get_checks)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Readiness | JSONResponse:
    results = await asyncio.gather(
        *(asyncio.wait_for(check(), settings.readiness_timeout_s) for check in checks.values()),
        return_exceptions=True,
    )
    # class name only: exception messages can carry DSNs and hostnames
    report = {
        name: f"fail: {type(r).__name__}" if isinstance(r, BaseException) else "ok"
        for name, r in zip(checks, results, strict=True)
    }
    if all(v == "ok" for v in report.values()):
        return Readiness(status="ok", checks=report)
    return problem_response(503, "Dependencies not ready", checks=report)
