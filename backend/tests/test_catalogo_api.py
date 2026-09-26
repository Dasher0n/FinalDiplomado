"""Pruebas de lectura del catalogo y la coleccion sin acceso a red."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.catalogo import transformar_bgp_url
from app.db.base import Base
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app


@pytest.fixture
def api_client() -> Generator[TestClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            await seed_database(session, Path(__file__).parent / "fixtures")
            await session.commit()

    async def sesion_de_prueba() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    async def cerrar() -> None:
        await engine.dispose()

    import asyncio

    asyncio.run(preparar())
    app = create_app()
    app.dependency_overrides[get_session] = sesion_de_prueba
    with TestClient(app) as client:
        yield client
    asyncio.run(cerrar())


def test_collection_returns_demo_games(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/collection")

    assert response.status_code == 200
    assert [game["nombre"] for game in response.json()["juegos"]] == ["Catan", "Wingspan"]


def test_games_searches_catalog_without_simulated_data(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/games", params={"q": "span", "limit": 1})

    assert response.status_code == 200
    assert response.json() == {
        "juegos": [
            {
                "id": "1",
                "nombre": "Wingspan",
                "anio": 2019,
                "imagen_url": "https://example.test/wingspan.jpg",
                "miniatura_url": "https://example.test/wingspan-thumb.jpg",
                "jugadores_minimos": 1.0,
                "jugadores_maximos": 5.0,
                "duracion_minima": 40.0,
                "duracion_maxima": 70.0,
                "promedio": 8.1,
                "precio": {
                    "precio_usd": "55.00",
                    "precio_confiable": True,
                    "fecha_precio": "2026-01-01T00:00:00Z",
                    "ofertas_us_con_stock": 3.0,
                    "url_bgp": "https://example.test/precio",
                },
            }
        ]
    }


def test_game_detail_returns_basic_attributes_and_price(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/games/2")

    assert response.status_code == 200
    detail = response.json()
    assert detail["nombre"] == "Catan"
    assert detail["mecanicas"] == ["Trading"]
    assert detail["precio"]["precio_usd"] == "50.00"


def test_game_detail_returns_domain_not_found_error(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/games/inexistente")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "juego_no_encontrado"


def test_bgp_url_replaces_encoded_utm_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.v1.catalogo.settings.bgp_sitename", "mi-sitio.local")
    url = (
        "https://boardgameprices.com/price?game=42&"
        "utm_source=site_https%3A%2F%2Fgithub.com%2FTU_USUARIO%2FFinalDiplomado&currency=USD"
    )

    assert transformar_bgp_url(url) == (
        "https://boardgameprices.com/price?game=42&utm_source=mi-sitio.local&currency=USD"
    )


def test_collection_mutations_and_engine_endpoints(api_client: TestClient) -> None:
    duplicate = api_client.post("/api/v1/collection", json={"game_id": "1"})
    removed = api_client.delete("/api/v1/collection/2")
    evaluate = api_client.post("/api/v1/engine/evaluate", json={"game_id": "1"})
    coverage = api_client.get("/api/v1/engine/coverage")
    tonight = api_client.post("/api/v1/engine/tonight", json={"jugadores": 2, "minutos": 90})

    assert duplicate.status_code == 201
    assert duplicate.json()["agregado"] is False
    assert removed.status_code == 200
    assert evaluate.status_code == 200
    assert evaluate.json()["juego"]["nombre"] == "Wingspan"
    assert coverage.status_code == 200
    assert "ejes" in coverage.json()
    assert tonight.status_code == 200


def test_plan_precio_requires_budget(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/engine/buy-plan", json={"modo": "precio", "n": 2})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "solicitud_motor_invalida"
