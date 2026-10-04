"""Ayudas de sesión para las pruebas: inicia sesión con las claves de prueba."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

USUARIOS = {
    "cafe": ("cafe", os.environ["CLAVE_USUARIO_CAFE"]),
    "coleccionista": ("coleccionista", os.environ["CLAVE_USUARIO_COLECCIONISTA"]),
}


def iniciar_sesion(client: TestClient, perfil: str) -> dict[str, str]:
    """Devuelve el encabezado Authorization de la persona dueña de ese perfil."""
    usuario, clave = USUARIOS[perfil]
    respuesta = client.post("/api/v1/auth/login", json={"usuario": usuario, "clave": clave})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['token']}"}
