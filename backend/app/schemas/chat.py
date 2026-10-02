"""Contratos de la capa conversacional."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PasoPlan(BaseModel):
    id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    estado: str = "pendiente"


class ChatSolicitud(BaseModel):
    mensaje: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    game_id: str | None = None


class TarjetaChat(BaseModel):
    tipo: str
    datos: dict[str, Any]


class CandidatoChat(BaseModel):
    id: str
    nombre: str
    imagen_url: str | None = None


class ChatRespuesta(BaseModel):
    run_id: str
    session_id: str
    intent: str
    plan: list[PasoPlan]
    answer: str
    tarjetas: list[TarjetaChat] = Field(default_factory=list)
    candidatos: list[CandidatoChat] = Field(default_factory=list)
    critic_passed: bool
    llm_used: bool


class RunResumen(BaseModel):
    id: str
    session_id: str | None
    pregunta: str
    intent: str | None
    estado: str
    creado_en: str


class RunDetalle(ChatRespuesta):
    pregunta: str
