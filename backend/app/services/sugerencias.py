"""Preguntas sugeridas del chat: tres distintas en cada carga y por perfil."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class JuegoCurado:
    id: str
    nombre: str  # Nombre en inglés tal como el catálogo lo resuelve directo.


# Juegos populares del catálogo. Una prueba verifica que cada uno existe, se resuelve directo
# sin identificación por LLM, tiene precio confiable y que evaluar_compra lo encuentra.
JUEGOS_CURADOS: tuple[JuegoCurado, ...] = (
    JuegoCurado("13", "Catan"),
    JuegoCurado("822", "Carcassonne"),
    JuegoCurado("30549", "Pandemic"),
    JuegoCurado("230802", "Azul"),
    JuegoCurado("9209", "Ticket to Ride"),
    JuegoCurado("178900", "Codenames"),
    JuegoCurado("36218", "Dominion"),
    JuegoCurado("39856", "Dixit"),
    JuegoCurado("266192", "Wingspan"),
    JuegoCurado("410201", "Wyrmspan"),
    JuegoCurado("68448", "7 Wonders"),
    JuegoCurado("148228", "Splendor"),
    JuegoCurado("167791", "Terraforming Mars"),
    JuegoCurado("199792", "Everdell"),
    JuegoCurado("237182", "Root"),
    JuegoCurado("169786", "Scythe"),
    JuegoCurado("224517", "Brass: Birmingham"),
    JuegoCurado("162886", "Spirit Island"),
    JuegoCurado("31260", "Agricola"),
    JuegoCurado("295947", "Cascadia"),
    JuegoCurado("204583", "Kingdomino"),
    JuegoCurado("163412", "Patchwork"),
    JuegoCurado("199561", "Sagrada"),
    JuegoCurado("70323", "King of Tokyo"),
    JuegoCurado("124361", "Concordia"),
    JuegoCurado("312484", "Lost Ruins of Arnak"),
    JuegoCurado("342942", "Ark Nova"),
    JuegoCurado("316554", "Dune: Imperium"),
    JuegoCurado("98778", "Hanabi"),
    JuegoCurado("54043", "Jaipur"),
    JuegoCurado("65244", "Forbidden Island"),
    JuegoCurado("70919", "Takenoko"),
)

PLANTILLAS_COMPRA = (
    "¿Qué tal entraría {x} en la colección?",
    "Tengo ganas de comprar {x}, ¿vale la pena?",
    "¿{x} sería buena compra?",
    "¿Me conviene {x}?",
    "¿Debería comprar {x}?",
)
PLANTILLAS_COBERTURA = (
    "¿Qué le falta a mi colección?",
    "¿Qué tipo de juego me hace falta?",
    "¿Qué experiencias me faltan?",
    "¿Qué huecos tiene mi colección?",
)
# Intenciones que el planner ya soporta y que tienen sentido como pregunta de inicio.
PLANTILLAS_OTRAS: dict[str, tuple[str, ...]] = {
    "que_compro": (
        "Dame un plan de {n} juegos para cubrir huecos",
        "¿Qué compro para cubrir huecos? {n} juegos",
    ),
    "que_saco_hoy": (
        "Somos {j} y tenemos {m} minutos, ¿qué saco?",
        "Hoy jugamos {j} personas y tenemos {m} minutos, ¿qué saco?",
    ),
    "coleccion": (
        "¿Qué juegos tengo en mi colección?",
        "Muéstrame mi colección",
    ),
    "detalle_juego": (
        "Háblame de {x}",
        "Detalle de {x}",
    ),
}


def generar_sugerencias(ids_en_coleccion: set[str], azar: random.Random | None = None) -> list[str]:
    """Una pregunta de compra, una de huecos y una más al azar; siempre distintas."""
    azar = azar or random.Random()
    disponibles = [j for j in JUEGOS_CURADOS if j.id not in ids_en_coleccion] or list(
        JUEGOS_CURADOS
    )
    juego = azar.choice(disponibles)
    compra = azar.choice(PLANTILLAS_COMPRA).format(x=juego.nombre)
    cobertura = azar.choice(PLANTILLAS_COBERTURA)
    intencion = azar.choice(tuple(PLANTILLAS_OTRAS))
    otro_juego = azar.choice([j for j in JUEGOS_CURADOS if j.id != juego.id])
    otra = azar.choice(PLANTILLAS_OTRAS[intencion]).format(
        x=otro_juego.nombre,
        n=azar.randint(2, 4),
        j=azar.randint(3, 6),
        m=azar.choice((30, 45, 60, 90)),
    )
    preguntas = [compra, cobertura, otra]
    azar.shuffle(preguntas)
    return preguntas
