"""Errores de dominio y sobre comun para la API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class SommelierError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "sommelier_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SommelierError)
    async def handle_domain(_: Request, exc: SommelierError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "La solicitud no es valida.",
            exc.errors(),
        )

    @app.exception_handler(HTTPException)
    async def handle_http(_: Request, exc: HTTPException) -> JSONResponse:
        message = (
            exc.detail if isinstance(exc.detail, str) else "La solicitud no se pudo completar."
        )
        details: Any = {} if isinstance(exc.detail, str) else exc.detail
        return error_response(exc.status_code, "http_error", message, details)
