"""Esquemas de perfiles de colección y contexto de operación."""

from __future__ import annotations

from pydantic import BaseModel


class PerfilRespuesta(BaseModel):
    id: str
    nombre: str
    tipo: str
    descripcion: str
    version_configuracion: int
    metas: dict[str, dict[str, int]]


class PerfilesRespuesta(BaseModel):
    perfiles: list[PerfilRespuesta]


class ContextoPerfilRespuesta(BaseModel):
    perfil: PerfilRespuesta
    juegos_en_coleccion: int
