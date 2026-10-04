"""Configuración para desplegar detrás de un proxy: documentación cerrada fuera de dev."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app

RUTAS_DE_DOCUMENTACION = ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("entorno", ["prod", "test"])
@pytest.mark.parametrize("ruta", RUTAS_DE_DOCUMENTACION)
def test_la_documentacion_se_cierra_fuera_de_dev(
    monkeypatch: pytest.MonkeyPatch, entorno: str, ruta: str
) -> None:
    monkeypatch.setattr(settings, "environment", entorno)

    with TestClient(create_app()) as client:
        assert client.get(ruta).status_code == 404


@pytest.mark.parametrize("ruta", RUTAS_DE_DOCUMENTACION)
def test_la_documentacion_existe_en_dev(monkeypatch: pytest.MonkeyPatch, ruta: str) -> None:
    monkeypatch.setattr(settings, "environment", "dev")

    with TestClient(create_app()) as client:
        assert client.get(ruta).status_code == 200


def test_el_contrato_openapi_se_puede_generar_con_la_documentacion_cerrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "environment", "prod")

    esquema = create_app().openapi()

    assert "/api/v1/auth/login" in esquema["paths"]


def test_cors_se_configura_desde_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "https://demo.example, https://otro.example")

    assert Settings().cors_origins == ["https://demo.example", "https://otro.example"]
