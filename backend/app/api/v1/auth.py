"""Inicio de sesión y datos de la sesión actual."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, SesionActual
from app.core.seguridad import crear_token
from app.schemas.auth import LoginRespuesta, LoginSolicitud, YoRespuesta
from app.services.usuarios import autenticar

router = APIRouter(prefix="/auth", tags=["auth"])

MENSAJE_LOGIN = "Usuario o contraseña incorrectos"


@router.post("/login", response_model=LoginRespuesta)
async def login(solicitud: LoginSolicitud, session: DbSession) -> LoginRespuesta:
    registro = await autenticar(session, solicitud.usuario, solicitud.clave)
    if registro is None:
        # Siempre el mismo mensaje: no revela si el usuario existe.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MENSAJE_LOGIN)
    return LoginRespuesta(
        token=crear_token(registro.id, registro.perfil),
        nombre=registro.nombre,
        perfil=registro.perfil,
    )


@router.get("/yo", response_model=YoRespuesta)
async def yo(sesion: SesionActual) -> YoRespuesta:
    return YoRespuesta(usuario=sesion.usuario, nombre=sesion.nombre, perfil=sesion.perfil)
