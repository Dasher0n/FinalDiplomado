"""Pruebas locales del narrator LLM del chat."""

from __future__ import annotations

from typing import Any

import openai
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services import chat as chat_service


@pytest.mark.asyncio
async def test_narrador_llm_usa_cliente_simulado_y_solo_resultados(monkeypatch: Any) -> None:
    llamadas: dict[str, Any] = {}

    class Responses:
        async def create(self, **kwargs: Any) -> Any:
            llamadas.update(kwargs)
            return type("Respuesta", (), {"output_text": "**Wingspan** aporta."})()

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    resultados = [
        {
            "juego": {
                "nombre": "Wingspan",
                "peso": 2.345,
                "precio_usd": 67.5,
                "fecha_precio": "2026-09-24T23:12:15Z",
            },
            "similitud": {"total": 0.8342},
            "veredicto": "aporta",
        }
    ]

    answer = await chat_service._narrar_llm(settings, resultados)

    assert answer == "**Wingspan** aporta."
    assert llamadas["model"] == settings.llm_model
    assert "Wingspan" in llamadas["input"][1]["content"]
    assert "No inventes cifras" in llamadas["input"][0]["content"]
    assert "Solo puedes afirmar hechos presentes literalmente" in llamadas["input"][0]["content"]
    assert "reimplementa o misma_linea_de_producto" in llamadas["input"][0]["content"]
    assert "presenta A, B y C con su valor cubierto" in llamadas["input"][0]["content"]
    assert "funciones que no estén en el manifiesto" in llamadas["input"][0]["content"]
    assert "una sola pregunta concreta" in llamadas["input"][0]["content"]
    assert "sin emojis" in llamadas["input"][0]["content"]
    assert "USD 67.50" in llamadas["input"][1]["content"]
    assert "24 sep 2026" in llamadas["input"][1]["content"]
    assert "0.83" in llamadas["input"][1]["content"]
