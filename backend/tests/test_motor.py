"""Pruebas doradas y de reglas para el motor determinista."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.db.models import Game
from app.db.seed import DEMO_GAMES, game_values
from app.engine.artefactos import ArtefactosMotor
from app.engine.motor import (
    buscar_local,
    cobertura,
    evaluar_redundancia,
    plan_compra,
    que_saco_hoy,
    regla_exacta,
    similitud,
)

RAIZ = Path(__file__).resolve().parents[2]
ARTEFACTOS = ArtefactosMotor.cargar(RAIZ / "artefactos")


def cargar_juegos(ids: set[str]) -> dict[str, Game]:
    juegos = {}
    with (RAIZ / "artefactos" / "catalogo.csv").open(encoding="utf-8", newline="") as archivo:
        for fila_vector, fila in enumerate(csv.DictReader(archivo)):
            if fila["ID"] in ids:
                juegos[fila["ID"]] = Game(**game_values(fila, fila_vector))
                if len(juegos) == len(ids):
                    return juegos
    raise AssertionError(f"No se encontraron todos los juegos: {ids - set(juegos)}")


PARES = (
    ("224517", "28720", (0.98, 1.00, 1.00, 0.84, 0.94)),
    ("174430", "295770", (0.70, 0.99, 1.00, 1.00, 0.88)),
    ("68448", "173346", (0.65, 0.94, 0.88, 1.00, 0.83)),
    ("30549", "161936", (0.63, 1.00, 1.00, 0.61, 0.71)),
    ("266192", "410201", (0.78, 0.99, 1.00, 0.41, 0.70)),
    ("266192", "350184", (0.19, 1.00, 0.88, 0.81, 0.59)),
    ("233078", "178900", (0.10, 0.64, 0.88, 0.00, 0.24)),
    ("162886", "12333", (0.28, 0.98, 0.00, 0.00, 0.21)),
    ("174430", "39856", (0.10, 0.86, 0.00, 0.00, 0.13)),
)


@pytest.mark.parametrize(("izquierda", "derecha", "esperado"), PARES)
def test_similitud_dorada(
    izquierda: str, derecha: str, esperado: tuple[float, float, float, float, float]
) -> None:
    juegos = cargar_juegos({izquierda, derecha})
    resultado = similitud(ARTEFACTOS, juegos[izquierda], juegos[derecha])
    assert resultado.mecanicas == pytest.approx(esperado[0], abs=0.01)
    assert resultado.ocasion == pytest.approx(esperado[1], abs=0.01)
    assert resultado.interaccion == pytest.approx(esperado[2], abs=0.01)
    assert resultado.tematica == pytest.approx(esperado[3], abs=0.01)
    assert resultado.total == pytest.approx(esperado[4], abs=0.01)


def test_redundancia_usa_regla_exacta_y_umbral_del_pickle() -> None:
    juegos = cargar_juegos({"30549", "161936", "266192", "410201"})
    assert regla_exacta(juegos["161936"], juegos["30549"])
    veredicto, _, parecido, exacta = evaluar_redundancia(
        ARTEFACTOS, juegos["410201"], [juegos["266192"]]
    )
    assert parecido is not None
    assert parecido.total < ARTEFACTOS.umbral_redundante
    assert exacta is True
    assert veredicto == "parecido_pero_cubre_hueco"


def test_cobertura_de_coleccion_demo() -> None:
    ids = {
        "224517",
        "174430",
        "178900",
        "13",
        "68448",
        "230802",
        "167791",
        "30549",
        "173346",
        "295947",
        "162886",
        "237182",
    }
    juegos = cargar_juegos(ids)
    coleccion = [juego for juego in juegos.values() if juego.nombre in DEMO_GAMES]
    resultado = cobertura(ARTEFACTOS, coleccion)
    assert {"más de 120"} <= set(resultado.ejes["Duración"].faltantes)
    assert {"Subastas", "Lápiz y papel", "Destreza y velocidad"} <= set(
        resultado.ejes["Mecánicas"].faltantes
    )
    assert {"Horror", "Cultura pop y humor", "Deportes y carreras", "Abstracto o sin tema"} <= set(
        resultado.ejes["Temática"].faltantes
    )
    assert {"5 a 6", "7 o más"} <= set(resultado.ejes["Jugadores"].debiles)


def test_plan_precio_compara_greedy_con_mejor_individual() -> None:
    juegos = cargar_juegos({"266192", "410201", "350184"})
    resultado = plan_compra(
        ARTEFACTOS,
        [juegos["266192"]],
        [juegos["410201"], juegos["350184"]],
        n=2,
        modo="precio",
        presupuesto=100,
        users_rated_min=0,
    )
    assert resultado.costo <= 100
    assert resultado.valor_cubierto > 0
    assert resultado.valor_pendiente >= 0


def test_que_saco_hoy_y_busqueda_ambigua() -> None:
    juegos = cargar_juegos({"13", "178900", "68448", "173346"})
    disponibles = que_saco_hoy(juegos.values(), jugadores=6, minutos=45)
    assert all(juego.max_playtime is None or juego.max_playtime <= 45 for juego, _ in disponibles)
    estado, candidatos = buscar_local(
        "7 Wonders", [juegos["68448"], juegos["173346"]], umbral_directo=101
    )
    assert estado == "ambiguo"
    assert {juego.id for juego in candidatos} == {"68448", "173346"}
