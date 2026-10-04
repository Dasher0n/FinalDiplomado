"""Tabla de resolución de nombres de juego por el endpoint HTTP del chat.

Reutiliza el mecanismo simulado de test_chat_llm.py: se sustituyen `_plan_llm`,
`_narrar_llm`, `_criticar_llm` y `openai.AsyncOpenAI`. No hay acceso a la red.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from rapidfuzz import fuzz
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.inspection import inspect

from app.api.v1 import chat as chat_api
from app.core.config import Settings
from app.db.base import Base
from app.db.models import AgentStep, Game
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app
from app.services import chat as chat_service
from app.services.chat import normalizar_nombre

CATAN_ID = "13"
SETI_ID = "418059"
CRIATURAS_ID = "400366"
FALSO_POSITIVO_ID = "119890"
WINGSPAN_ID = "174430"

NOMBRES = ["Catan", "Criaturas maravillosas"]

FRASES = [
    "{x} sería una buena compra?",
    "{x} seria buena compra",
    "{x} es buena compra?",
    "{x} vale la pena?",
    "¿vale la pena {x}?",
    "¿qué tal {x}?",
    "¿qué tal entraría {x} en la colección?",
    "¿cómo entraría {x}?",
    "¿debería comprar {x}?",
    "¿me conviene {x}?",
    "¿conviene comprar {x}?",
    "háblame de {x}",
    "detalle de {x}",
    "info de {x}",
    "{x}",
    '"{x}" vale la pena?',
]

# Salida simulada del planner: (identificador, argumentos o None, motivo de descarte esperado).
SALIDAS_PLANNER: list[tuple[str, dict[str, Any] | None, str | None]] = [
    ("omitido", {}, None),
    ("none", {"nombre": None}, None),
    ("vacio", {"nombre": ""}, "invalido"),
    ("null", {"nombre": "null"}, "invalido"),
    ("None_texto", {"nombre": "None"}, "invalido"),
    ("espacio", {"nombre": " "}, "invalido"),
    ("el_juego", {"nombre": "el juego"}, "invalido"),
    ("no_anclado", {"nombre": "Wingspan"}, "no_anclado"),
    ("id_no_aceptado", {"game_id": WINGSPAN_ID}, "id_no_aceptado"),
    ("correcto", None, None),
]

TOOLS_DE_JUEGO = {"detalle_juego", "evaluar_compra"}


@pytest.fixture(scope="module")
def entorno() -> Generator[tuple[TestClient, Any]]:
    """Catálogo mínimo con los IDs reales: Catan, SETI, Criaturas y el falso positivo."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            await seed_database(session, Path(__file__).parent / "fixtures")
            await session.commit()
            for viejo, nuevo in (("2", CATAN_ID), ("1", WINGSPAN_ID), ("3", SETI_ID)):
                await session.execute(
                    text('UPDATE games SET "ID" = :n WHERE "ID" = :v'), {"n": nuevo, "v": viejo}
                )
                await session.execute(
                    text("UPDATE user_collection SET game_id = :n WHERE game_id = :v"),
                    {"n": nuevo, "v": viejo},
                )
            await session.execute(
                text('UPDATE games SET "Name" = :n, "Users rated" = 21902 WHERE "ID" = :i'),
                {"n": "SETI: Search for Extraterrestrial Intelligence", "i": SETI_ID},
            )
            base = await session.get(Game, WINGSPAN_ID)
            columnas = [atributo.key for atributo in inspect(Game).column_attrs]
            extras = [
                (CRIATURAS_ID, "Wondrous Creatures", 7342),
                (FALSO_POSITIVO_ID, "Agricola: All Creatures", 9000),
                ("17785", "Seti", 47),
                ("900001", "Unstable Unicorns", 30000),
                ("900002", "Unstable Unicorns: NSFW Base Game", 9000),
                ("900003", "Unstable Unicorns: Chaos", 800),
                ("900004", "Beasts of Balance", 5000),
            ]
            # Las filas vectoriales 3 en adelante no se evalúan: estos juegos solo son candidatos.
            for fila, (id_juego, nombre, votos) in enumerate(extras, start=3):
                valores = {clave: getattr(base, clave) for clave in columnas}
                valores.update(
                    id=id_juego,
                    nombre=nombre,
                    users_rated=votos,
                    fila_vector=fila,
                    product_line=[],
                    reimplements=[],
                    reimplemented_by=[],
                )
                session.add(Game(**valores))
            await session.commit()

    async def sesion_de_prueba() -> Any:
        async with sessionmaker() as session:
            yield session

    asyncio.run(preparar())
    app = create_app()
    app.dependency_overrides[get_session] = sesion_de_prueba
    with TestClient(app) as client:
        yield client, sessionmaker
    asyncio.run(engine.dispose())


class Espias:
    """Registra lo que llega a las tools, a la resolución y a la identificación por LLM."""

    def __init__(self) -> None:
        self.tools: list[tuple[str, dict[str, Any]]] = []
        self.resoluciones: list[Any] = []
        self.identificaciones: list[str] = []
        self.salida_planner: dict[str, Any] | None = None
        self.llamadas_planner = 0


def _preparar(monkeypatch: pytest.MonkeyPatch, llm_caido: bool) -> Espias:
    espias = Espias()
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    monkeypatch.setattr(chat_api, "settings", settings)

    async def planner(*_args: Any) -> chat_service.PlanLlm | None:
        espias.llamadas_planner += 1
        if llm_caido:
            raise RuntimeError("LLM caído")
        if espias.salida_planner is None:
            return None
        return chat_service.PlanLlm(
            intent="evaluar_compra",
            steps=[
                chat_service.PasoPlan(id="1", tool="evaluar_compra", args=espias.salida_planner)
            ],
        )

    async def narrador(*_args: Any, **_kwargs: Any) -> str:
        if llm_caido:
            raise RuntimeError("LLM caído")
        return "**Resultado** del análisis."

    async def critico(*_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
        if llm_caido:
            raise RuntimeError("LLM caído")
        return []

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            espias.identificaciones.append(kwargs["input"])
            if llm_caido:
                raise RuntimeError("LLM caído")
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=["Wondrous Creatures"], identificaciones=[]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    original_tool = chat_service._ejecutar_tool
    original_resolver = chat_service._resolver_con_traduccion

    async def espia_tool(nombre: str, args: dict[str, Any], *resto: Any) -> dict[str, Any]:
        espias.tools.append((nombre, dict(args)))
        return await original_tool(nombre, args, *resto)

    async def espia_resolver(repo: Any, nombre: Any, game_id: Any, settings: Settings) -> Any:
        espias.resoluciones.append(nombre)
        return await original_resolver(repo, nombre, game_id, settings)

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", narrador)
    monkeypatch.setattr(chat_service, "_criticar_llm", critico)
    monkeypatch.setattr(chat_service, "_ejecutar_tool", espia_tool)
    monkeypatch.setattr(chat_service, "_resolver_con_traduccion", espia_resolver)
    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    return espias


def _traza_planner(sessionmaker: Any, run_id: str) -> dict[str, Any]:
    async def leer() -> dict[str, Any]:
        async with sessionmaker() as session:
            paso = await session.scalar(
                select(AgentStep).where(
                    AgentStep.run_id == run_id, AgentStep.agent_name == "planner"
                )
            )
            return dict(paso.output) if paso and paso.output else {}

    return asyncio.run(leer())


def _afirmar_tools_de_juego_validas(
    espias: Espias, mensaje: str, game_ids_aceptados: set[str] | None = None
) -> None:
    """Invariante: nada se ejecuta con nombre vacío, no anclado o game_id no aceptado."""
    aceptados = game_ids_aceptados or set()
    for tool, args in espias.tools:
        if tool not in TOOLS_DE_JUEGO:
            continue
        game_id = args.get("game_id")
        if game_id is not None:
            assert game_id in aceptados, f"game_id no aceptado: {args}"
            continue
        nombre = chat_service.nombre_valido(args.get("nombre"))
        assert nombre, f"nombre vacío o inválido: {args}"
        assert fuzz.partial_ratio(normalizar_nombre(nombre), normalizar_nombre(mensaje)) >= 90, (
            f"nombre no anclado: {args}"
        )


def _afirmar_confirmacion_criaturas(respuesta: dict[str, Any], espias: Espias) -> None:
    assert espias.resoluciones
    assert set(espias.resoluciones) == {"Criaturas maravillosas"}
    datos = respuesta["tarjetas"][0]["datos"]
    assert datos["estado"] in {"ambiguo", "no_encontrado"}
    assert "juego" not in datos and "veredicto" not in datos
    assert FALSO_POSITIVO_ID not in {candidato["id"] for candidato in respuesta["candidatos"]}
    assert respuesta["sugerir_nombre_ingles"] is True


@pytest.mark.parametrize("salida", SALIDAS_PLANNER, ids=[item[0] for item in SALIDAS_PLANNER])
@pytest.mark.parametrize("frase", FRASES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_tabla_con_llm(
    entorno: tuple[TestClient, Any],
    monkeypatch: pytest.MonkeyPatch,
    nombre: str,
    frase: str,
    salida: tuple[str, dict[str, Any] | None, str | None],
) -> None:
    client, sessionmaker = entorno
    identificador, args, motivo_esperado = salida
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {"nombre": nombre} if args is None else args
    mensaje = frase.format(x=nombre)

    respuesta = client.post("/api/v1/chat", json={"mensaje": mensaje}).json()

    _afirmar_tools_de_juego_validas(espias, mensaje)
    traza = _traza_planner(sessionmaker, respuesta["run_id"])
    assert traza["motivo_descarte"] == motivo_esperado, traza
    if nombre == "Catan":
        assert respuesta["tarjetas"][0]["datos"]["juego"]["id"] == CATAN_ID
        esperado = "planner" if identificador == "correcto" else "regex"
        assert traza["origen_nombre"] == esperado, traza
        assert traza["nombre_final"] == "Catan"
    else:
        assert traza["nombre_final"] == "Criaturas maravillosas", traza
        _afirmar_confirmacion_criaturas(respuesta, espias)
        assert any("«Criaturas maravillosas»" in texto for texto in espias.identificaciones)
        candidatos = {candidato["id"] for candidato in respuesta["candidatos"]}
        assert CRIATURAS_ID in candidatos


@pytest.mark.parametrize("frase", FRASES)
@pytest.mark.parametrize("nombre", NOMBRES)
def test_tabla_con_llm_caido(
    entorno: tuple[TestClient, Any],
    monkeypatch: pytest.MonkeyPatch,
    nombre: str,
    frase: str,
) -> None:
    client, _sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=True)
    mensaje = frase.format(x=nombre)

    respuesta = client.post("/api/v1/chat", json={"mensaje": mensaje}).json()

    _afirmar_tools_de_juego_validas(espias, mensaje)
    if nombre == "Catan":
        assert respuesta["tarjetas"][0]["datos"]["juego"]["id"] == CATAN_ID
    else:
        _afirmar_confirmacion_criaturas(respuesta, espias)


def test_sin_nombre_ni_foco_pide_aclaracion_sin_tools(
    entorno: tuple[TestClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {}

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿sería buena compra?"}).json()

    assert "¿De qué juego me hablas? Escríbeme su nombre." in respuesta["answer"]
    assert espias.tools == []
    assert _traza_planner(sessionmaker, respuesta["run_id"])["origen_nombre"] == "ninguno"


def test_referencia_con_foco_usa_el_juego_en_foco(
    entorno: tuple[TestClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {"nombre": "Catan"}
    primera = client.post("/api/v1/chat", json={"mensaje": "Catan"}).json()
    assert primera["tarjetas"][0]["datos"]["juego"]["id"] == CATAN_ID
    espias.tools.clear()
    espias.salida_planner = {}

    respuesta = client.post(
        "/api/v1/chat",
        json={"mensaje": "¿y ese vale la pena?", "session_id": primera["session_id"]},
    ).json()

    assert respuesta["tarjetas"][0]["datos"]["juego"]["id"] == CATAN_ID
    assert _traza_planner(sessionmaker, respuesta["run_id"])["origen_nombre"] == "foco"
    _afirmar_tools_de_juego_validas(espias, "¿y ese vale la pena?", {CATAN_ID})


def test_titulo_nuevo_tiene_prioridad_sobre_el_foco(
    entorno: tuple[TestClient, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {"nombre": "Catan"}
    primera = client.post("/api/v1/chat", json={"mensaje": "Catan"}).json()
    espias.tools.clear()
    espias.salida_planner = {"nombre": "SETI"}

    respuesta = client.post(
        "/api/v1/chat",
        json={"mensaje": "¿Vale la pena SETI?", "session_id": primera["session_id"]},
    ).json()

    assert respuesta["tarjetas"][0]["datos"]["juego"]["id"] == SETI_ID
    _afirmar_tools_de_juego_validas(espias, "¿Vale la pena SETI?", {CATAN_ID})
