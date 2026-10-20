"""RFC 9457 problem details for every error response."""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException


class Problem(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None


def problem_response(status: int, detail: str | None = None, **extra: Any) -> JSONResponse:
    problem = Problem(title=HTTPStatus(status).phrase, status=status, detail=detail, **extra)
    return JSONResponse(
        jsonable_encoder(problem),
        status_code=status,
        media_type="application/problem+json",
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return problem_response(exc.status_code, str(exc.detail))


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return problem_response(422, "Request validation failed", errors=exc.errors())


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
