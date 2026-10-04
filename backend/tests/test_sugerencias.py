"""Preguntas sugeridas del chat: lista curada verificada contra el catálogo real, sin red."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.db.models import Game
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app
from app.repositories.catalogo import CatalogoRepository
from app.services import chat as chat_service
from app.services.sugerencias import (
    JUEGOS_CURADOS,
    PLANTILLAS_COBERTURA,
    PLANTILLAS_COMPRA,
    PLANTILLAS_OTRAS,
    generar_sugerencias,
)

INTENCIONES_OTRAS = {
    "que_compro": "que_compro",
    "que_saco_hoy": "que_saco_hoy",
    "coleccion": "coleccion",
    "detalle_juego": "detalle_juego",
}


@pytest.fixture(scope="module")
def catalogo_real() -> Generator[tuple[TestClient, Any]]:
    """Catálogo completo y colecciones demo sembrados en una base en memoria."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> None:
        async with engine.begin() as conexion:
            await conexion.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            await seed_database(session)
            await session.commit()

    async def sesion_de_prueba() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    asyncio.run(preparar())
    app = create_app()
    app.dependency_overrides[get_session] = sesion_de_prueba
    with TestClient(app) as client:
        yield client, sessionmaker
    asyncio.run(engine.dispose())


def _juego(sessionmaker: Any, juego_id: str) -> Game | None:
    async def consulta() -> Game | None:
        async with sessionmaker() as session:
            return await session.get(Game, juego_id)

    return asyncio.run(consulta())


@pytest.mark.parametrize("curado", JUEGOS_CURADOS, ids=[j.nombre for j in JUEGOS_CURADOS])
def test_cada_juego_curado_existe_se_resuelve_directo_y_se_evalua(
    catalogo_real: tuple[TestClient, Any], curado: Any
) -> None:
    client, sessionmaker = catalogo_real

    juego = _juego(sessionmaker, curado.id)

    assert juego is not None and juego.nombre == curado.nombre
    assert juego.precio_confiable and juego.precio_usd is not None
    respuesta = client.post(
        "/api/v1/chat",
        params={"perfil": "coleccionista"},
        json={"mensaje": f"¿Qué tal entraría {curado.nombre} en la colección?"},
    ).json()
    datos = respuesta["tarjetas"][0]["datos"]
    # Resolución directa: sin LLM no hay identificación, así que "encontrado" implica coincidencia
    # exacta con el juego curado.
    assert respuesta["intent"] == "evaluar_compra"
    assert datos["estado"] == "encontrado" and datos["juego"]["id"] == curado.id
    assert datos.get("interpretado_como") is None and datos.get("traza_traduccion") is None


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("Ticket to Ride", "9209"),
        ("Codenames", "178900"),
        ("Catan", "13"),
        ("SETI", "418059"),
        ("Seti", "418059"),
    ],
)
def test_el_titulo_exacto_gana_a_las_expansiones_con_el_mismo_prefijo(
    catalogo_real: tuple[TestClient, Any], nombre: str, esperado: str
) -> None:
    _, sessionmaker = catalogo_real

    async def resolver() -> tuple[str, list[str]]:
        async with sessionmaker() as session:
            estado, juegos = await chat_service._resolver(
                CatalogoRepository(session), nombre, None, Settings()
            )
            return estado, [juego.id for juego in juegos]

    assert asyncio.run(resolver()) == ("encontrado", [esperado])


def test_las_plantillas_son_de_intenciones_que_el_planner_ya_soporta() -> None:
    assert {"evaluar_compra", "que_me_falta", *INTENCIONES_OTRAS} <= chat_service._INTENTS
    assert set(PLANTILLAS_OTRAS) == set(INTENCIONES_OTRAS)
    contexto = {"x": "Catan", "n": 3, "j": 4, "m": 45}
    for plantilla in PLANTILLAS_COMPRA:
        plan = chat_service._plan_determinista(plantilla.format(**contexto), None)
        assert (plan.intent, plan.steps[0].args) == ("evaluar_compra", {"nombre": "Catan"})
    for plantilla in PLANTILLAS_COBERTURA:
        assert chat_service._plan_determinista(plantilla, None).intent == "que_me_falta"
    for intencion, plantillas in PLANTILLAS_OTRAS.items():
        for plantilla in plantillas:
            plan = chat_service._plan_determinista(plantilla.format(**contexto), None)
            assert plan.intent == intencion, plantilla


@pytest.mark.parametrize("perfil", ["cafe", "coleccionista"])
def test_el_endpoint_devuelve_tres_preguntas_distintas_por_perfil(
    catalogo_real: tuple[TestClient, Any], perfil: str
) -> None:
    client, _ = catalogo_real
    coleccion = client.get("/api/v1/collection", params={"perfil": perfil}).json()["juegos"]
    nombres = {juego["nombre"] for juego in coleccion}
    vistas: set[str] = set()

    for _ in range(25):
        preguntas = client.get("/api/v1/chat/suggestions", params={"perfil": perfil}).json()[
            "preguntas"
        ]
        intents = [chat_service._plan_determinista(p, None).intent for p in preguntas]
        assert len(preguntas) == 3 and len(set(preguntas)) == 3
        assert intents.count("evaluar_compra") == 1 and intents.count("que_me_falta") == 1
        assert set(intents) - {"evaluar_compra", "que_me_falta"} <= set(INTENCIONES_OTRAS)
        compra = preguntas[intents.index("evaluar_compra")]
        assert chat_service._extraer_nombre_juego(compra) not in nombres
        vistas.update(preguntas)

    assert len(vistas) >= 10


def test_wyrmspan_aparece_a_veces_y_es_redundante_con_el_perfil_personal(
    catalogo_real: tuple[TestClient, Any],
) -> None:
    client, _ = catalogo_real
    coleccion = client.get("/api/v1/collection", params={"perfil": "coleccionista"}).json()[
        "juegos"
    ]
    ids = {juego["id"] for juego in coleccion}
    pregunta = next(
        p
        for semilla in range(500)
        for p in generar_sugerencias(ids, random.Random(semilla))
        if "Wyrmspan" in p and chat_service._plan_determinista(p, None).intent == "evaluar_compra"
    )

    respuesta = client.post(
        "/api/v1/chat", params={"perfil": "coleccionista"}, json={"mensaje": pregunta}
    ).json()

    assert respuesta["tarjetas"][0]["datos"]["veredicto"] == "redundante"
