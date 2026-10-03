"""Pruebas de los endpoints de metadatos."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_database_and_never_exposes_secret() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["database"] is True
    assert "openai_api_key" not in response.text


def test_capabilities_informa_estado_de_modelos() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    assert response.json()["api_fase"] == 4
    assert len(response.json()["endpoints_habilitados"]) == 2
    assert response.json()["modelos_llm"] == {}
    assert response.json()["error_modelos_llm"] is None
