"""Dependencias compartidas de la API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.seguridad import TokenInvalido, decodificar_token
from app.db.models import CollectionProfile, User, Usuario
from app.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]
_esquema = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Sesion:
    """Quién llama: el perfil sale siempre del token y nunca de la solicitud."""

    usuario_id: str
    usuario: str
    nombre: str
    perfil: str


async def exigir_sesion(
    session: DbSession,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema)],
) -> Sesion:
    """Exige Authorization: Bearer <token> válido y de un usuario que exista."""
    no_autenticado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión no válida")
    if credenciales is None:
        raise no_autenticado
    try:
        carga = decodificar_token(credenciales.credentials)
    except TokenInvalido:
        raise no_autenticado from None
    registro = await session.get(Usuario, carga["sub"])
    if registro is None:
        raise no_autenticado
    return Sesion(registro.id, registro.usuario, registro.nombre, registro.perfil)


SesionActual = Annotated[Sesion, Depends(exigir_sesion)]


async def get_current_user(session: DbSession) -> User:
    """Dueño de los datos de colección (el usuario demo sembrado): se aíslan por perfil."""
    user = await session.scalar(select(User).where(User.email == settings.demo_user_email.lower()))
    if user is None:
        raise RuntimeError("El usuario demo no existe. Ejecuta la siembra inicial.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_profile(session: DbSession, sesion: SesionActual) -> CollectionProfile:
    profile = await session.get(CollectionProfile, sesion.perfil)
    if profile is None:
        raise RuntimeError("El perfil de la sesión no existe. Ejecuta la siembra inicial.")
    return profile


CurrentProfile = Annotated[CollectionProfile, Depends(get_current_profile)]
