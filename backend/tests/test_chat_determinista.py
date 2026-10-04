"""Traza del crítico, respuestas deterministas y candidatos de confirmación."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AgentRun, AgentStep
from app.services import chat as chat_service
from tests.test_chat_resolucion_nombres import (  # noqa: F401
    CATAN_ID,
    CRIATURAS_ID,
    FALSO_POSITIVO_ID,
    _preparar,
    entorno,
)

LITERALES = ["Wonderful Creatures", "Marvelous Creatures", "Wondrous Creatures"]
IDENTIFICACIONES = ["Fantastic Creatures", "Unstable Unicorns", "Beasts of Balance"]


def _pasos(sessionmaker: Any, run_id: str) -> tuple[list[AgentStep], bool | None]:
    async def leer() -> tuple[list[AgentStep], bool | None]:
        async with sessionmaker() as session:
            pasos = (
                await session.scalars(
                    select(AgentStep)
                    .where(AgentStep.run_id == run_id)
                    .order_by(AgentStep.creado_en)
                )
            ).all()
            run = await session.get(AgentRun, run_id)
            return list(pasos), run.critic_passed

    return asyncio.run(leer())


def _no_debe_llamarse(*_args: Any, **_kwargs: Any) -> Any:
    pytest.fail("Una respuesta determinista no debe llamar al narrador ni al crítico.")


def test_traza_rechazada_del_critico_conserva_sus_findings(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {"nombre": "Catan"}
    llamadas = {"n": 0}

    async def critico(*_args: Any) -> list[dict[str, str]]:
        llamadas["n"] += 1
        return [{"tipo": "cifra", "mensaje": "Cifra sin respaldo."}] if llamadas["n"] == 1 else []

    monkeypatch.setattr(chat_service, "_criticar_llm", critico)

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Catan?"}).json()

    pasos, _ = _pasos(sessionmaker, respuesta["run_id"])
    rechazos = [p for p in pasos if p.agent_name == "critic" and p.estado == "rejected"]
    assert len(rechazos) == 1
    assert rechazos[0].output["findings"] == [{"tipo": "cifra", "mensaje": "Cifra sin respaldo."}]
    aprobados = [p for p in pasos if p.agent_name == "critic" and p.estado == "ok"]
    assert aprobados[0].output["findings"] == []


def test_aclaracion_es_determinista_sin_narrador_ni_critico(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {}
    monkeypatch.setattr(chat_service, "_narrar_llm", _no_debe_llamarse)
    monkeypatch.setattr(chat_service, "_criticar_llm", _no_debe_llamarse)

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿sería buena compra?"}).json()

    assert "¿De qué juego me hablas? Escríbeme su nombre." in respuesta["answer"]
    assert respuesta["critic_passed"] is None
    pasos, critic_passed = _pasos(sessionmaker, respuesta["run_id"])
    assert critic_passed is None
    omitidos = {p.agent_name: p for p in pasos if p.estado == "omitido"}
    assert omitidos["narrator"].output["motivo"] == "determinista"
    assert omitidos["critic"].output["motivo"] == "determinista"


def test_el_critico_sigue_rechazando_preguntas_del_narrador() -> None:
    hallazgos = chat_service._criticar_determinista("¿Quieres comprarlo?", [])

    assert any("pregunta de seguimiento" in hallazgo for hallazgo in hallazgos)


def test_confirmacion_de_candidatos_con_listas_reales_del_caso(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias = _preparar(monkeypatch, llm_caido=False)
    espias.salida_planner = {}
    monkeypatch.setattr(chat_service, "_narrar_llm", _no_debe_llamarse)
    monkeypatch.setattr(chat_service, "_criticar_llm", _no_debe_llamarse)

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=LITERALES, identificaciones=IDENTIFICACIONES
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)

    respuesta = client.post(
        "/api/v1/chat", json={"mensaje": "Criaturas maravillosas seria una buena compra?"}
    ).json()

    ids = [candidato["id"] for candidato in respuesta["candidatos"]]
    nombres = [candidato["nombre"] for candidato in respuesta["candidatos"]]
    assert ids[0] == CRIATURAS_ID
    assert len(ids) <= 3 and len(set(ids)) == len(ids)
    assert FALSO_POSITIVO_ID not in ids
    assert sum(nombre.startswith("Unstable Unicorns") for nombre in nombres) == 1
    assert respuesta["sugerir_nombre_ingles"] is True
    assert "¿Te refieres a…?" in respuesta["answer"]
    assert "no sé a cuál" not in respuesta["answer"]
    assert respuesta["critic_passed"] is None
    # El frontend pinta un botón por cada elemento de `candidatos`.
    assert respuesta["tarjetas"][0]["datos"]["candidatos"] == respuesta["candidatos"]
    assert CATAN_ID not in ids


@pytest.mark.asyncio
async def test_planner_registra_salida_cruda_y_error_de_validacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from app.core.config import Settings

    resultados: list[Any] = [
        chat_service._PlanRespuestaLlm(intent="general"),
        ValueError("evaluar_compra requiere un nombre de juego válido"),
    ]

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            resultado = resultados.pop(0)
            if isinstance(resultado, Exception):
                raise resultado
            return SimpleNamespace(output_parsed=resultado)

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    intentos: list[dict[str, Any]] = []

    await chat_service._plan_llm(settings, "hola", "", None, intentos)
    with pytest.raises(ValueError):
        await chat_service._plan_llm(settings, "hola", "", "error previo", intentos)

    assert intentos[0] == {"salida_cruda": '{"intent":"general","steps":[]}', "error": None}
    assert intentos[1]["salida_cruda"] is None
    assert "requiere un nombre" in intentos[1]["error"]
