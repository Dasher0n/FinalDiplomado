"""Usuarios, login, token y aislamiento por sesión. Sin red ni LLM."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import seguridad
from app.core.config import settings
from app.db.base import Base
from app.db.models import Usuario
from app.main import create_app
from app.services.usuarios import sembrar_usuarios
from tests.auth import USUARIOS, iniciar_sesion

MENSAJE = "Usuario o contraseña incorrectos"
RUTAS_PROTEGIDAS = [
    "/api/v1/collection",
    "/api/v1/profiles",
    "/api/v1/profiles/context",
    "/api/v1/engine/coverage",
    "/api/v1/chat/suggestions",
    "/api/v1/chat/runs",
    "/api/v1/capabilities",
    "/api/v1/auth/yo",
]


def _token(**cambios: Any) -> str:
    carga: dict[str, Any] = {
        "sub": "no-importa",
        "perfil": "cafe",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **cambios,
    }
    return jwt.encode(carga, settings.jwt_secret.get_secret_value(), algorithm="HS256")


@pytest.mark.parametrize("perfil", ["cafe", "coleccionista"])
def test_login_correcto_devuelve_token_nombre_y_perfil(api_client: TestClient, perfil: str) -> None:
    usuario, clave = USUARIOS[perfil]

    respuesta = api_client.post(
        "/api/v1/auth/login", headers={}, json={"usuario": usuario, "clave": clave}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["perfil"] == perfil
    assert cuerpo["nombre"] == {"cafe": "Café demo", "coleccionista": "Colección personal"}[perfil]
    carga = jwt.decode(cuerpo["token"], settings.jwt_secret.get_secret_value(), ["HS256"])
    assert carga["perfil"] == perfil and carga["exp"] > datetime.now(UTC).timestamp()
    yo = api_client.get(
        "/api/v1/auth/yo", headers={"Authorization": f"Bearer {cuerpo['token']}"}
    ).json()
    assert yo == {"usuario": usuario, "nombre": cuerpo["nombre"], "perfil": perfil}


@pytest.mark.parametrize(
    ("usuario", "clave"),
    [("cafe", "clave-equivocada"), ("no-existe", "lo-que-sea"), ("coleccionista", "x")],
)
def test_login_incorrecto_siempre_da_el_mismo_mensaje(
    api_client: TestClient, usuario: str, clave: str
) -> None:
    respuesta = api_client.post("/api/v1/auth/login", json={"usuario": usuario, "clave": clave})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["message"] == MENSAJE


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS)
def test_sin_token_responde_401(api_client: TestClient, ruta: str) -> None:
    api_client.headers.pop("Authorization")

    assert api_client.get(ruta).status_code == 401
    assert api_client.post("/api/v1/chat", json={"mensaje": "hola"}).status_code == 401


def test_health_y_login_no_exigen_token(api_client: TestClient) -> None:
    api_client.headers.pop("Authorization")

    assert api_client.get("/api/v1/health").status_code == 200
    assert (
        api_client.post("/api/v1/auth/login", json={"usuario": "x", "clave": "y"}).status_code
        == 401
    )


def _usuario_id(api_client: TestClient) -> str:
    return jwt.decode(
        api_client.headers["Authorization"].removeprefix("Bearer "),
        settings.jwt_secret.get_secret_value(),
        ["HS256"],
    )["sub"]


@pytest.mark.parametrize(
    "construir",
    [
        lambda uid: _token(sub=uid, exp=datetime.now(UTC) - timedelta(minutes=1)),
        lambda uid: jwt.encode(
            {"sub": uid, "perfil": "cafe", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "otro-secreto-distinto-de-treinta-y-dos-bytes!!",
            algorithm="HS256",
        ),
        lambda uid: "esto.no.es-un-token",
        lambda uid: _token(sub=uid).rsplit(".", 1)[0],
        lambda uid: _token(sub="usuario-que-no-existe"),
    ],
    ids=["vencido", "firma_invalida", "mal_formado", "sin_firma", "usuario_inexistente"],
)
def test_token_vencido_o_invalido_responde_401(api_client: TestClient, construir: Any) -> None:
    token = construir(_usuario_id(api_client))

    respuesta = api_client.get("/api/v1/collection", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401


def test_el_perfil_sale_del_token_aunque_llegue_otro_en_la_url(api_client: TestClient) -> None:
    # La sesión es la del perfil personal; ?perfil=cafe se ignora en cualquier endpoint.
    contexto = api_client.get("/api/v1/profiles/context", params={"perfil": "cafe"}).json()
    assert contexto["perfil"]["id"] == "coleccionista" and contexto["juegos_en_coleccion"] == 3

    cafe = iniciar_sesion(api_client, "cafe")
    contexto = api_client.get(
        "/api/v1/profiles/context", params={"perfil": "coleccionista"}, headers=cafe
    ).json()
    assert contexto["perfil"]["id"] == "cafe" and contexto["juegos_en_coleccion"] == 0
    juegos = api_client.get("/api/v1/collection", params={"perfil": "coleccionista"}, headers=cafe)
    assert juegos.json()["juegos"] == []


def test_una_persona_no_ve_las_sesiones_ni_las_corridas_de_la_otra(
    api_client: TestClient,
) -> None:
    cafe = iniciar_sesion(api_client, "cafe")
    primera = api_client.post(
        "/api/v1/chat", headers=cafe, json={"mensaje": "¿Qué le falta a mi colección?"}
    ).json()

    # La otra persona no puede continuar esa sesión: empieza una nueva.
    ajena = api_client.post(
        "/api/v1/chat",
        json={"mensaje": "¿Qué le falta a mi colección?", "session_id": primera["session_id"]},
    ).json()
    assert ajena["session_id"] != primera["session_id"]
    # Tampoco ve sus corridas.
    corridas_cafe = {c["id"] for c in api_client.get("/api/v1/chat/runs", headers=cafe).json()}
    corridas_otra = {c["id"] for c in api_client.get("/api/v1/chat/runs").json()}
    assert primera["run_id"] in corridas_cafe and primera["run_id"] not in corridas_otra
    assert api_client.get(f"/api/v1/chat/runs/{primera['run_id']}").status_code == 404
    assert api_client.get(f"/api/v1/chat/runs/{primera['run_id']}", headers=cafe).status_code == 200


def test_el_hash_no_contiene_la_clave_y_se_verifica() -> None:
    clave = "una-clave-de-prueba-larga"

    primero, segundo = seguridad.hashear_clave(clave), seguridad.hashear_clave(clave)

    assert clave not in primero and primero.startswith("scrypt$")
    assert primero != segundo  # sal aleatoria por usuario
    assert seguridad.verificar_clave(clave, primero)
    assert not seguridad.verificar_clave("otra-clave", primero)
    assert not seguridad.verificar_clave(clave, "basura")


def _base_en_memoria() -> tuple[Any, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def crear() -> None:
        async with engine.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)

    asyncio.run(crear())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_la_siembra_guarda_solo_el_hash_y_es_idempotente() -> None:
    engine, sessionmaker = _base_en_memoria()

    async def sembrar() -> tuple[list[str], list[str], list[Usuario]]:
        async with sessionmaker() as session:
            primera = await sembrar_usuarios(session)
            segunda = await sembrar_usuarios(session)
            await session.commit()
            filas = list((await session.scalars(select(Usuario))).all())
            return primera, segunda, filas

    primera, segunda, filas = asyncio.run(sembrar())

    assert primera == ["cafe", "coleccionista"] and segunda == []
    assert {fila.usuario: (fila.nombre, fila.perfil) for fila in filas} == {
        "cafe": ("Café demo", "cafe"),
        "coleccionista": ("Colección personal", "coleccionista"),
    }
    for fila in filas:
        assert fila.clave_hash.startswith("scrypt$")
        assert USUARIOS[fila.perfil][1] not in fila.clave_hash
    asyncio.run(engine.dispose())


def test_sin_clave_en_el_entorno_no_se_crea_el_usuario_y_se_advierte(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "clave_usuario_cafe", SecretStr(""))
    engine, sessionmaker = _base_en_memoria()

    async def sembrar() -> list[str]:
        async with sessionmaker() as session:
            return await sembrar_usuarios(session)

    with caplog.at_level(logging.WARNING):
        creados = asyncio.run(sembrar())

    assert creados == ["coleccionista"]
    assert "CLAVE_USUARIO_CAFE" in caplog.text
    assert USUARIOS["coleccionista"][1] not in caplog.text
    asyncio.run(engine.dispose())


def test_el_backend_no_arranca_sin_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", SecretStr(""))

    with pytest.raises(RuntimeError, match="JWT_SECRET"), TestClient(create_app()):
        pass
