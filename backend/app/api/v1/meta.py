"""Estado y capacidades disponibles del backend."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings

router = APIRouter(tags=["meta"])


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    environment: str
    database: bool
    llm_active: bool
    web_search_active: bool


class Capabilities(BaseModel):
    llm_active: bool
    web_search_active: bool
    api_fase: int
    endpoints_habilitados: list[str]
    modelos_llm: dict[str, dict[str, str | bool]]
    error_modelos_llm: str | None = None


@router.get("/health", response_model=HealthStatus, summary="Estado del servicio")
async def health(session: DbSession) -> HealthStatus:
    database_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    return HealthStatus(
        status="ok" if database_ok else "degraded",
        app=settings.app_name,
        environment=settings.environment,
        database=database_ok,
        llm_active=settings.llm_active,
        web_search_active=settings.web_search_active,
    )


@router.get("/capabilities", response_model=Capabilities, summary="Capacidades activas")
async def capabilities(request: Request) -> Capabilities:
    modelos = getattr(request.app.state, "modelos_llm", {})
    return Capabilities(
        llm_active=settings.llm_active,
        web_search_active=settings.web_search_active,
        api_fase=4,
        endpoints_habilitados=["GET /api/v1/health", "GET /api/v1/capabilities"],
        modelos_llm=modelos.get("modelos", {}),
        error_modelos_llm=modelos.get("error"),
    )
