"""Pruebas de lectura del catalogo y la coleccion sin acceso a red."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.catalogo import transformar_bgp_url
from tests.auth import iniciar_sesion


def test_collection_returns_demo_games(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/collection")

    assert response.status_code == 200
    assert [game["nombre"] for game in response.json()["juegos"]] == [
        "Catan",
        "Codenames",
        "Wingspan",
    ]


def test_profiles_expose_versioned_goals_and_isolated_context(api_client: TestClient) -> None:
    profiles = api_client.get("/api/v1/profiles")
    cafe = api_client.get("/api/v1/profiles/context", headers=iniciar_sesion(api_client, "cafe"))
    collector = api_client.get("/api/v1/profiles/context")

    assert profiles.status_code == 200
    cafe_profile = next(item for item in profiles.json()["perfiles"] if item["id"] == "cafe")
    assert cafe_profile["version_configuracion"] == 2
    assert cafe_profile["metas"]["Jugadores"]["1"] == 0
    assert cafe.status_code == 200
    assert cafe.json()["juegos_en_coleccion"] == 0
    assert collector.json()["juegos_en_coleccion"] == 3


def test_cafe_coverage_ignores_zero_goal(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/engine/coverage", headers=iniciar_sesion(api_client, "cafe"))

    assert response.status_code == 200
    jugadores = response.json()["ejes"]["Jugadores"]
    assert "1" not in jugadores["conteo_por_nivel"]
    assert jugadores["meta_por_nivel"]["2"] == 3


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
    assert "veredicto_razones" in evaluate.json()
    assert "peso_estimado" in evaluate.json()["juego"]
    assert all(item["juego"]["id"] != "1" for item in evaluate.json()["similares"])
    assert coverage.status_code == 200
    assert "ejes" in coverage.json()
    assert tonight.status_code == 200
    assert tonight.json()["juegos"][0]["nivel_ajuste"] == "funciona"
    assert tonight.json()["juegos"][0]["best_players"] == [3]


def test_tonight_prioritizes_ideal_fit_and_exposes_best_players(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/engine/tonight", json={"jugadores": 3, "minutos": 90})

    assert response.status_code == 200
    assert [(juego["nombre"], juego["nivel_ajuste"]) for juego in response.json()["juegos"]] == [
        ("Wingspan", "ideal"),
        ("Catan", "funciona"),
    ]
    assert response.json()["juegos"][0]["best_players"] == [3]


def test_plan_precio_requires_budget(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/engine/buy-plan", json={"modo": "precio", "n": 2})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "solicitud_motor_invalida"


def test_plan_only_lists_missing_or_weak_levels(api_client: TestClient) -> None:
    coverage = api_client.get("/api/v1/engine/coverage").json()["ejes"]
    plan = api_client.post(
        "/api/v1/engine/buy-plan",
        json={"modo": "juego", "n": 2, "users_rated_min": 0},
    )

    assert plan.status_code == 200
    opciones = plan.json()["opciones"]
    assert [opcion["etiqueta"] for opcion in opciones] == ["A", "B", "C"]
    assert (
        opciones[0]["valor_cubierto"]
        >= opciones[1]["valor_cubierto"]
        >= opciones[2]["valor_cubierto"]
    )
    ids = [{juego["id"] for juego in opcion["juegos"]} for opcion in opciones]
    assert not ids[0] & ids[1]
    assert not ids[0] & ids[2]
    assert not ids[1] & ids[2]
    for opcion in opciones:
        assert "costo" not in opcion
        assert set(opcion["impacto"]["ejes"]) == set(coverage)
        for game in opcion["juegos"]:
            assert set(game["impacto"]["ejes"]) == set(coverage)
            for level in game["niveles_que_cubre"]:
                assert coverage[level["eje"]]["conteo_por_nivel"][level["nivel"]] < 2
                assert level["estado"] in {"faltante", "debil"}


def test_impacto_venta_de_codenames_deja_jugadores_sin_cobertura(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/engine/sell-impact", json={"game_id": "3"})

    assert response.status_code == 200
    jugadores = response.json()["impacto"]["ejes"]["Jugadores"]
    assert jugadores["despues"]["faltantes"] == jugadores["antes"]["faltantes"] + 2
    perdidos = {
        cambio["nivel"]
        for cambio in response.json()["impacto"]["cambios_nivel"]
        if cambio["eje"] == "Jugadores" and cambio["despues"] == 0
    }
    assert {"5 a 6", "7 o más"} <= perdidos


def test_conteos_de_estados_suman_los_niveles_del_eje(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/engine/evaluate", json={"game_id": "1"})

    assert response.status_code == 200
    cobertura = api_client.get("/api/v1/engine/coverage").json()["ejes"]
    for eje, impacto in response.json()["impacto"]["ejes"].items():
        total = len(cobertura[eje]["conteo_por_nivel"])
        assert sum(impacto["antes"].values()) == total
        assert sum(impacto["despues"].values()) == total


def test_plan_admite_orden_mejor_valorados(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/engine/buy-plan",
        json={"modo": "juego", "n": 1, "users_rated_min": 0, "orden": "mejor_valorados"},
    )

    assert response.status_code == 200
