from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class NotFoundError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class LifecycleError(Exception):
    """Raised on an invalid study/run status transition."""

    def __init__(self, message: str) -> None:
        self.message = message


def _envelope(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=_envelope("NOT_FOUND", exc.message))

    @app.exception_handler(LifecycleError)
    async def _lifecycle(request: Request, exc: LifecycleError) -> JSONResponse:
        return JSONResponse(status_code=409, content=_envelope("LIFECYCLE_ERROR", exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("VALIDATION_ERROR", "Invalid request", exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("HTTP_ERROR", str(exc.detail)),
        )
