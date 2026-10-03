"""Punto de entrada de la API."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.session import dispose_db, init_db
from app.engine.artefactos import ArtefactosMotor

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging("DEBUG" if settings.debug else "INFO")
    log.info(
        "Arrancando backend",
        extra={"environment": settings.environment, "llm_active": settings.llm_active},
    )
    await init_db()
    app.state.artefactos_motor = ArtefactosMotor.cargar(settings.artefactos_dir)
    app.state.modelos_llm = {"activo": settings.llm_active, "modelos": {}, "error": None}
    if settings.llm_active:
        try:
            from openai import AsyncOpenAI

            cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
            disponibles = {modelo.id for modelo in (await cliente.models.list()).data}
            app.state.modelos_llm = {
                "activo": True,
                "modelos": {
                    "LLM_MODEL": {
                        "nombre": settings.llm_model,
                        "disponible": settings.llm_model in disponibles,
                    },
                    "LLM_MODEL_FAST": {
                        "nombre": settings.llm_model_fast,
                        "disponible": settings.llm_model_fast in disponibles,
                    },
                },
                "error": None,
            }
        except Exception as error:  # noqa: BLE001
            app.state.modelos_llm["error"] = str(error)[:300]
    try:
        yield
    finally:
        await dispose_db()


def operation_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}_{route.name}"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="API del sommelier de juegos de mesa.",
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = str(int((time.perf_counter() - started) * 1000))
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
