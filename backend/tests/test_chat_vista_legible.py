"""Vista legible sin identificadores, artículos en candidatos, borradores y unidades."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.services import chat as chat_service
from tests.test_chat_determinista import _pasos  # noqa: F401
from tests.test_chat_resolucion_nombres import _preparar, entorno  # noqa: F401

FIXTURES = Path(__file__).parent / "fixtures"
EVALUACIONES = json.loads((FIXTURES / "narrador_entrada_casos.json").read_text())
DETALLE = json.loads((FIXTURES / "narrador_detalle_catan.json").read_text())["detalle_catan"]


def _textos(valor: Any) -> list[str]:
    """Todas las claves y los valores de texto de la vista."""
    if isinstance(valor, dict):
        return [t for clave, item in valor.items() for t in [clave, *_textos(item)]]
    if isinstance(valor, list):
        return [t for item in valor for t in _textos(item)]
    return [valor] if isinstance(valor, str) else []


@pytest.mark.parametrize(
    "resultado",
    [
        EVALUACIONES["caso4"],
        EVALUACIONES["caso6"],
        {
            **EVALUACIONES["caso4"],
            "veredicto": "parecido_pero_cubre_hueco",
            "regla_exacta": "misma_linea_de_producto",
        },
        DETALLE,
    ],
    ids=["evaluar_seti", "evaluar_catan", "evaluar_con_regla_exacta", "detalle_catan"],
)
def test_la_vista_legible_no_contiene_guiones_bajos(resultado: dict[str, Any]) -> None:
    vista = chat_service._vista_legible([resultado])

    assert [texto for texto in _textos(vista) if "_" in texto] == []


def test_la_vista_legible_usa_etiquetas_en_espanol() -> None:
    resultado = {
        **EVALUACIONES["caso6"],
        "veredicto": "parecido_pero_cubre_hueco",
        "regla_exacta": "misma_linea_de_producto",
    }

    vista = chat_service._vista_legible([resultado])[0]

    assert vista["Evaluación del motor"] == "parecido, pero cubre un hueco"
    assert vista["Regla exacta"] == "misma línea de producto"
    assert vista["Huecos que cubre"] == ["Duración: 61 a 120 minutos"]
    assert vista["Qué tan parecido"] == "parecido"
    assert vista["Similitud"]["Total"] == "52%"
    assert "Niveles que refuerza" in vista and "Ya cubiertos" in vista
    assert "Juego más parecido" in vista


@pytest.mark.parametrize(
    ("eje", "nivel", "esperado"),
    [
        ("Duración", "más de 120", "Duración: más de 120 minutos"),
        ("Duración", "61 a 120", "Duración: 61 a 120 minutos"),
        ("Duración", "30 minutos o menos", "Duración: 30 minutos o menos"),
        ("Peso", "pesado", "Peso: pesado"),
        ("Interacción", "directa", "Interacción: directa"),
        ("Jugadores", "3 a 4", "Jugadores: 3 a 4"),
    ],
)
def test_etiquetas_de_nivel_con_unidades(eje: str, nivel: str, esperado: str) -> None:
    assert chat_service._etiqueta_nivel(eje, nivel) == esperado


@pytest.mark.asyncio
async def test_articulos_iniciales_no_impiden_la_coincidencia_exacta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    juegos = [
        SimpleNamespace(id="134559", nombre="Errant Knights", users_rated=300),
        SimpleNamespace(id="257987", nombre="The Towers of Arkhanos", users_rated=900),
        SimpleNamespace(id="84876", nombre="The Castles of Burgundy", users_rated=60000),
        SimpleNamespace(id="355483", nombre="Wandering Towers", users_rated=7137),
    ]

    class Catalogo:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=[
                        "The Errant Towers",
                        "The Wandering Towers",
                        "The Roaming Towers",
                        "The Straying Towers",
                        "The Wayward Towers",
                    ],
                    identificaciones=[
                        "The Wandering Towers",
                        "The Towers of Arkhanos",
                        "The Castles of Burgundy",
                    ],
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, candidatos, *_ = await chat_service._resolver_con_traduccion(
        Catalogo(),
        "Las torres errantes",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    ids = [juego.id for juego in candidatos]
    assert estado == "ambiguo" and ids[0] == "355483" and len(ids) == 3


def test_sin_articulo_ignora_el_primero_de_cada_idioma() -> None:
    for titulo in (
        "the wandering towers",
        "a wandering towers",
        "el wandering towers",
        "las wandering towers",
        "an wandering towers",
        "los wandering towers",
    ):
        assert chat_service._sin_articulo(titulo) == "wandering towers"
    assert chat_service._sin_articulo("theory of evolution") == "theory of evolution"


def test_el_borrador_del_narrador_queda_en_la_traza_junto_a_los_findings(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {"nombre": "Catan"}
    borradores = ["**Catan** primer borrador.", "**Catan** segundo borrador."]
    llamadas = {"n": 0}

    async def narrador(*_args: Any, **_kwargs: Any) -> str:
        return borradores[llamadas["n"]]

    async def critico(*_args: Any) -> list[dict[str, str]]:
        llamadas["n"] += 1
        return (
            [{"categoria": "cifra_sin_fuente", "detalle": "Cifra."}] if llamadas["n"] == 1 else []
        )

    monkeypatch.setattr(chat_service, "_narrar_llm", narrador)
    monkeypatch.setattr(chat_service, "_criticar_llm", critico)

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Catan?"}).json()

    pasos, _ = _pasos(sessionmaker, respuesta["run_id"])
    narradores = [p for p in pasos if p.agent_name == "narrator"]
    criticos = [p for p in pasos if p.agent_name == "critic"]
    assert narradores[0].output["borrador"] == borradores[0]
    assert narradores[1].output["borrador"] == borradores[1]
    assert criticos[0].estado == "rejected"
    assert criticos[0].output["findings"] == [
        {"categoria": "cifra_sin_fuente", "detalle": "Cifra."}
    ]
    assert "primer borrador" in criticos[0].output["borrador"]
    assert "segundo borrador" in criticos[1].output["borrador"]
