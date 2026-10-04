"""Contraseñas con scrypt y tokens JWT. Nunca se guarda ni se registra una clave en claro."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

_N, _R, _P = 2**14, 8, 1
_ALGORITMO = "HS256"


class TokenInvalido(Exception):
    """El token falta, está vencido o su firma no es válida."""


def _scrypt(clave: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(clave.encode(), salt=sal, n=n, r=r, p=p, maxmem=64 * 1024 * 1024)


def hashear_clave(clave: str) -> str:
    """Formato scrypt$n$r$p$sal$hash, con sal aleatoria por usuario."""
    sal = os.urandom(16)
    derivada = _scrypt(clave, sal, _N, _R, _P)
    codificar = base64.b64encode
    return f"scrypt${_N}${_R}${_P}${codificar(sal).decode()}${codificar(derivada).decode()}"


def verificar_clave(clave: str, almacenado: str) -> bool:
    try:
        _, n, r, p, sal, esperado = almacenado.split("$")
        derivada = _scrypt(clave, base64.b64decode(sal), int(n), int(r), int(p))
        return hmac.compare_digest(derivada, base64.b64decode(esperado))
    except ValueError, TypeError:
        return False


def crear_token(usuario_id: str, perfil: str, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now(UTC)
    carga = {
        "sub": usuario_id,
        "perfil": perfil,
        "exp": ahora + timedelta(hours=settings.jwt_horas),
    }
    return jwt.encode(carga, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITMO)


def decodificar_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[_ALGORITMO],
            options={"require": ["exp", "sub", "perfil"]},
        )
    except jwt.PyJWTError as error:
        raise TokenInvalido from error
