"""Alias confirmados: se guardan al confirmar y se resuelven sin identificación por LLM."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AgentStep, ConfirmedAlias
from app.services import chat as chat_service
from tests.test_chat_resolucion_nombres import (  # noqa: F401
    CRIATURAS_ID,
    _preparar,
    entorno,
)


def _preparar_alias(monkeypatch: pytest.MonkeyPatch, literales: list[str]) -> tuple[Any, list[str]]:
    """Planner de detalle_juego por nombre e identificación simulada con conteo de llamadas."""
    espias = _preparar(monkeypatch, llm_caido=False)
    identificaciones: list[str] = []

    async def planner(_settings: Any, mensaje: str, *_args: Any) -> chat_service.PlanLlm:
        nombre = chat_service._extraer_nombre_juego(mensaje) or mensaje
        return chat_service.PlanLlm(
            intent="detalle_juego",
            steps=[chat_service.PasoPlan(id="1", tool="detalle_juego", args={"nombre": nombre})],
        )

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            identificaciones.append(kwargs["input"])
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=literales, identificaciones=[]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    return espias, identificaciones


def _post(client: TestClient, mensaje: str, perfil: str, **extra: Any) -> dict[str, Any]:
    respuesta = client.post(
        "/api/v1/chat", params={"perfil": perfil}, json={"mensaje": mensaje, **extra}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _alias(sessionmaker: Any) -> list[ConfirmedAlias]:
    async def leer() -> list[ConfirmedAlias]:
        async with sessionmaker() as session:
            return list((await session.scalars(select(ConfirmedAlias))).all())

    return asyncio.run(leer())


def _pasos(sessionmaker: Any, run_id: str, agente: str) -> list[AgentStep]:
    async def leer() -> list[AgentStep]:
        async with sessionmaker() as session:
            return list(
                (
                    await session.scalars(
                        select(AgentStep).where(
                            AgentStep.run_id == run_id, AgentStep.agent_name == agente
                        )
                    )
                ).all()
            )

    return asyncio.run(leer())


def test_confirmar_un_candidato_guarda_el_alias_y_se_resuelve_sin_llm(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _, identificaciones = _preparar_alias(monkeypatch, ["Wondrous Creatures"])
    primera = _post(client, "Criaturas maravillosas", "cafe")
    assert [c["id"] for c in primera["candidatos"]] == [CRIATURAS_ID]
    assert len(identificaciones) == 1 and _alias(sessionmaker) == []

    confirmada = _post(
        client,
        "Wondrous Creatures",
        "cafe",
        game_id=CRIATURAS_ID,
        session_id=primera["session_id"],
    )

    assert confirmada["tarjetas"][0]["datos"]["juego"]["id"] == CRIATURAS_ID
    [alias] = _alias(sessionmaker)
    assert (alias.alias_normalizado, alias.game_id, alias.profile_id, alias.origen) == (
        "criaturas maravillosas",
        CRIATURAS_ID,
        "cafe",
        "candidato",
    )
    identificaciones.clear()

    directa = _post(client, "Criaturas maravillosas", "cafe")

    assert identificaciones == []
    assert directa["tarjetas"][0]["datos"]["juego"]["id"] == CRIATURAS_ID
    assert directa["tarjetas"][0]["datos"]["origen_resolucion"] == "alias"
    assert "Interpreté «Criaturas maravillosas» como «Wondrous Creatures»." in directa["answer"]
    assert directa["critic_passed"] is True
    [paso] = _pasos(sessionmaker, directa["run_id"], "resolution")
    assert paso.output == {"origen_resolucion": "alias", "llm_called": False}


def test_un_alias_de_un_perfil_no_afecta_al_otro(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _sessionmaker = entorno
    _, identificaciones = _preparar_alias(monkeypatch, ["Wondrous Creatures"])
    # El alias "criaturas maravillosas" ya existe en el perfil cafe (prueba anterior).
    identificaciones.clear()

    otro = _post(client, "Criaturas maravillosas", "coleccionista")

    assert len(identificaciones) == 1
    assert otro["tarjetas"][0]["datos"].get("origen_resolucion") is None
    assert "Interpreté" not in otro["answer"]


def test_escribir_el_nombre_en_ingles_tambien_guarda_el_alias(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _, identificaciones = _preparar_alias(monkeypatch, [])
    primera = _post(client, "Criaturas asombrosas", "cafe")
    assert primera["tarjetas"][0]["datos"]["estado"] == "no_encontrado"

    ingles = _post(
        client,
        "El nombre en inglés es: Wondrous Creatures",
        "cafe",
        session_id=primera["session_id"],
    )

    assert ingles["tarjetas"][0]["datos"]["juego"]["id"] == CRIATURAS_ID
    alias = {a.alias_normalizado: a for a in _alias(sessionmaker)}["criaturas asombrosas"]
    assert (alias.game_id, alias.origen, alias.profile_id) == (CRIATURAS_ID, "ingles", "cafe")
    identificaciones.clear()

    directa = _post(client, "Criaturas asombrosas", "cafe")

    assert identificaciones == []
    assert directa["tarjetas"][0]["datos"]["juego"]["id"] == CRIATURAS_ID


def test_un_candidato_ajeno_a_la_confirmacion_no_guarda_alias(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _preparar_alias(monkeypatch, [])
    antes = len(_alias(sessionmaker))
    primera = _post(client, "Criaturas fabulosas", "cafe")

    _post(
        client,
        "Seti",
        "cafe",
        game_id="17785",
        session_id=primera["session_id"],
    )

    assert len(_alias(sessionmaker)) == antes


def test_identificacion_pide_cinco_literales_con_variantes_del_adjetivo() -> None:
    with pytest.raises(ValueError):
        chat_service._TitulosTraducidosLlm(traducciones_literales=["aa"] * 6)
    ok = chat_service._TitulosTraducidosLlm(
        traducciones_literales=["Wondrous Creatures"] * 5, identificaciones=[]
    )
    assert len(ok.traducciones_literales) == 5


@pytest.mark.asyncio
async def test_prompt_de_identificacion_pide_variantes_del_adjetivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import SecretStr

    from app.core.config import Settings

    llamada: dict[str, Any] = {}

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            llamada.update(kwargs)
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=["aa", "bb", "cc", "dd", "ee"], identificaciones=[]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    class Catalogo:
        async def todos_los_juegos(self) -> list[Any]:
            return []

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)

    *_, traza = await chat_service._resolver_con_traduccion(
        Catalogo(), "Criaturas maravillosas", None, settings
    )

    assert "hasta 5 traducciones literales" in llamada["input"]
    assert "wondrous, marvelous, wonderful, amazing" in llamada["input"]
    assert traza["traducciones_literales"] == ["aa", "bb", "cc", "dd", "ee"]
