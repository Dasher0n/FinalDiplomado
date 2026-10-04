"""Contratos de inicio de sesión."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginSolicitud(BaseModel):
    usuario: str = Field(min_length=1, max_length=64)
    clave: str = Field(min_length=1, max_length=256)


class LoginRespuesta(BaseModel):
    token: str
    nombre: str
    perfil: str


class YoRespuesta(BaseModel):
    usuario: str
    nombre: str
    perfil: str
