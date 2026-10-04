"""Siembra de usuarios al arrancar y comprobación de credenciales."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.seguridad import hashear_clave, verificar_clave
from app.db.models import Usuario

log = get_logger(__name__)

# Hash de una clave descartada para gastar el mismo tiempo cuando el usuario no existe.
_HASH_RELLENO = hashear_clave("relleno-sin-uso")


@dataclass(frozen=True)
class UsuarioSemilla:
    usuario: str
    nombre: str
    perfil: str  # id del perfil de colección: "cafe" o "coleccionista" (Colección personal)
    variable: str


SEMILLAS = (
    UsuarioSemilla("cafe", "Café demo", "cafe", "CLAVE_USUARIO_CAFE"),
    UsuarioSemilla(
        "coleccionista", "Colección personal", "coleccionista", "CLAVE_USUARIO_COLECCIONISTA"
    ),
)


def _clave_de(semilla: UsuarioSemilla) -> str:
    secreto = (
        settings.clave_usuario_cafe
        if semilla.variable == "CLAVE_USUARIO_CAFE"
        else settings.clave_usuario_coleccionista
    )
    return secreto.get_secret_value()


async def sembrar_usuarios(session: AsyncSession) -> list[str]:
    """Crea los usuarios que falten. Sin clave en el entorno no se crea y se advierte."""
    creados: list[str] = []
    for semilla in SEMILLAS:
        existente = await session.scalar(select(Usuario).where(Usuario.usuario == semilla.usuario))
        if existente is not None:
            continue
        clave = _clave_de(semilla)
        if not clave:
            log.warning(
                f"No se crea el usuario {semilla.usuario}: falta {semilla.variable} en el entorno",
                extra={"usuario": semilla.usuario, "variable": semilla.variable},
            )
            continue
        session.add(
            Usuario(
                usuario=semilla.usuario,
                nombre=semilla.nombre,
                perfil=semilla.perfil,
                clave_hash=hashear_clave(clave),
            )
        )
        creados.append(semilla.usuario)
    await session.flush()
    return creados


async def autenticar(session: AsyncSession, usuario: str, clave: str) -> Usuario | None:
    registro = await session.scalar(select(Usuario).where(Usuario.usuario == usuario.strip()))
    if registro is None:
        verificar_clave(clave, _HASH_RELLENO)
        return None
    return registro if verificar_clave(clave, registro.clave_hash) else None
