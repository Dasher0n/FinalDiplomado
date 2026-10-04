"""Contrato del planner: enums, reintento con la causa real y foco en el prompt.

Las salidas inválidas son las capturadas en la verificación real (C4), saneadas.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient

from app.services import chat as chat_service
from tests.test_chat_resolucion_nombres import (  # noqa: F401
    CATAN_ID,
    CRIATURAS_ID,
    _preparar,
    _traza_planner,
    entorno,
)

SALIDAS = json.loads(
    (Path(__file__).parent / "fixtures" / "planner_salidas_reales_saneadas.json").read_text()
)
_ARGS_NULOS = dict.fromkeys(
    ("nombre", "game_id", "n", "average_min", "users_rated_min", "ejes_ignorados")
)


def _plan(intent: str, tool: str | None = None, **args: Any) -> dict[str, Any]:
    pasos = [{"id": "p1", "tool": tool, "args": {**_ARGS_NULOS, **args}, "depends_on": []}]
    return {"intent": intent, "steps": pasos if tool else []}


def _simular_planner(monkeypatch: pytest.MonkeyPatch, salidas: list[dict[str, Any]]) -> list[str]:
    """Usa el _plan_llm real con un cliente que valida cada salida como lo hace el SDK."""
    prompts: list[str] = []

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            if kwargs["text_format"] is chat_service._PlanRespuestaLlm:
                prompts.append(kwargs["input"])
                return SimpleNamespace(
                    output_parsed=chat_service._PlanRespuestaLlm.model_validate_json(
                        json.dumps(salidas[len(prompts) - 1])
                    )
                )
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=["Wondrous Creatures"], identificaciones=[]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    return prompts


def _con_planner_real(monkeypatch: pytest.MonkeyPatch) -> Any:
    real = chat_service._plan_llm
    espias = _preparar(monkeypatch, llm_caido=False)
    monkeypatch.setattr(chat_service, "_plan_llm", real)
    return espias


def _intentos(sessionmaker: Any, run_id: str) -> dict[str, Any]:
    return _traza_planner(sessionmaker, run_id)


@pytest.mark.parametrize(
    "clave", ["intent_descriptivo", "steps_vacios_con_frase_libre", "plan_inventado"]
)
def test_intent_fuera_del_enum_no_cumple_el_esquema(clave: str) -> None:
    with pytest.raises(ValueError, match="intent"):
        chat_service._PlanRespuestaLlm.model_validate_json(json.dumps(SALIDAS[clave]))


def test_nombre_null_en_evaluar_compra_ya_no_lanza_en_el_esquema() -> None:
    plan = chat_service._PlanRespuestaLlm.model_validate_json(
        json.dumps(SALIDAS["nombre_null_en_evaluar_compra"])
    )

    assert plan.steps[0].args.nombre is None


@pytest.mark.parametrize("clave", ["intent_descriptivo", "plan_inventado"])
def test_reintento_por_intent_invalido_y_criaturas_termina_en_confirmacion(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    clave: str,
) -> None:
    client, sessionmaker = entorno
    _con_planner_real(monkeypatch)
    prompts = _simular_planner(
        monkeypatch,
        [
            SALIDAS[clave],
            _plan("evaluar_compra", "evaluar_compra", nombre="Criaturas maravillosas"),
        ],
    )

    respuesta = client.post(
        "/api/v1/chat", json={"mensaje": "Criaturas maravillosas seria una buena compra?"}
    ).json()

    assert len(prompts) == 2
    assert "no cumple el esquema" in prompts[1] and "intent" in prompts[1]
    assert "El intento anterior no fue válido" not in prompts[0]
    traza = _intentos(sessionmaker, respuesta["run_id"])
    assert traza["reintentado"] is True and traza["origen_nombre"] == "planner_reintento"
    assert CRIATURAS_ID in [c["id"] for c in respuesta["candidatos"]]
    assert respuesta["critic_passed"] is None


@pytest.mark.parametrize(
    ("primera", "causa"),
    [
        ("steps_vacios_con_frase_libre", "no cumple el esquema"),
        ("nombre_null_en_evaluar_compra", "evaluar_compra requiere nombre o game_id"),
    ],
)
def test_reintento_con_causa_real_y_aclaracion_sin_herramientas(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    primera: str,
    causa: str,
) -> None:
    client, sessionmaker = entorno
    espias = _con_planner_real(monkeypatch)
    prompts = _simular_planner(monkeypatch, [SALIDAS[primera], _plan("general")])

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿sería buena compra?"}).json()

    assert causa in prompts[1]
    if primera == "nombre_null_en_evaluar_compra":
        assert "general con steps vacío" in prompts[1]
    assert len(prompts) == 2
    assert "¿De qué juego me hablas? Escríbeme su nombre." in respuesta["answer"]
    assert respuesta["critic_passed"] is None
    assert espias.tools == []
    assert _intentos(sessionmaker, respuesta["run_id"])["origen_nombre"] == "ninguno"


def test_reintento_es_unico_aunque_ambas_salidas_sean_invalidas(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _sessionmaker = entorno
    espias = _con_planner_real(monkeypatch)
    prompts = _simular_planner(monkeypatch, [SALIDAS["steps_vacios_con_frase_libre"]] * 3)

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿sería buena compra?"}).json()

    assert len(prompts) == 2
    assert "¿De qué juego me hablas?" in respuesta["answer"]
    assert espias.tools == []


def test_planner_valido_en_el_primer_intento_tiene_origen_planner(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _con_planner_real(monkeypatch)
    prompts = _simular_planner(
        monkeypatch, [_plan("evaluar_compra", "evaluar_compra", nombre="Catan")]
    )

    respuesta = client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Catan?"}).json()

    traza = _intentos(sessionmaker, respuesta["run_id"])
    assert len(prompts) == 1
    assert traza["origen_nombre"] == "planner" and traza["reintentado"] is False
    assert "Juego en foco: ninguno" in prompts[0]
    assert respuesta["tarjetas"][0]["datos"]["juego"]["id"] == CATAN_ID


def test_foco_llega_al_prompt_y_game_id_del_foco_tiene_origen_foco(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias = _con_planner_real(monkeypatch)
    prompts = _simular_planner(
        monkeypatch,
        [
            _plan("detalle_juego", "detalle_juego", nombre="Catan"),
            _plan("evaluar_compra", "evaluar_compra", game_id=CATAN_ID),
        ],
    )
    primera = client.post("/api/v1/chat", json={"mensaje": "Catan"}).json()
    espias.tools.clear()

    respuesta = client.post(
        "/api/v1/chat",
        json={"mensaje": "¿y ese vale la pena?", "session_id": primera["session_id"]},
    ).json()

    assert "Juego en foco: ninguno" in prompts[0]
    assert f"Juego en foco: Catan (id {CATAN_ID})" in prompts[1]
    assert espias.tools[0][1] == {"game_id": CATAN_ID}
    traza = _intentos(sessionmaker, respuesta["run_id"])
    assert traza["origen_nombre"] == "foco" and traza["reintentado"] is False
