"""Pruebas de la capa LLM con fixtures locales y sin acceso de red."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.v1 import chat as chat_api
from app.core.config import Settings
from app.services import chat as chat_service


def _fixture() -> dict[str, Any]:
    return json.loads((Path(__file__).parent / "fixtures" / "llm_chat_saneado.json").read_text())


def test_critic_determinista_rechaza_cifra_fuera_de_las_tools() -> None:
    findings = chat_service._criticar_determinista(
        "La similitud es 99.0.",
        [{"similitud": {"total": 0.7}, "juego": {"nombre": "Wingspan"}}],
    )

    assert findings == ["La cifra 99.0 no aparece en los resultados de las tools."]


def test_chat_reintenta_narrador_y_persiste_critic(
    api_client: TestClient, monkeypatch: Any
) -> None:
    fixture = _fixture()
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    monkeypatch.setattr(chat_api, "settings", settings)

    async def planner(*_args: Any) -> chat_service.PlanLlm:
        return chat_service.PlanLlm.model_validate(fixture["planner"])

    async def narrator(
        _settings: Settings,
        _results: list[dict[str, Any]],
        feedback: list[str] | None = None,
    ) -> str:
        return fixture["narrador_corregido"] if feedback else fixture["narrador_inicial"]

    async def critic(*_args: Any) -> list[str]:
        return []

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", narrator)
    monkeypatch.setattr(chat_service, "_criticar_llm", critic)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Wingspan?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == fixture["narrador_corregido"]
    assert payload["critic_passed"] is True
    assert payload["critic_attempts"] == 1
    assert payload["llm_used"] is True
    persisted = api_client.get(f"/api/v1/chat/runs/{payload['run_id']}")
    assert persisted.json()["critic_attempts"] == 1
    assert persisted.json()["critic_findings"] == []


def test_fixtures_llm_no_contienen_secretos() -> None:
    fixtures = (Path(__file__).parent / "fixtures").glob("*.json")
    for fixture in fixtures:
        text = fixture.read_text()
        assert "Bearer" not in text
        assert "sk-" not in text
