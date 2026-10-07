"""Perfiles versionados de objetivos para colecciones personales y mesas."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

CONFIGURACION_PERFILES_VERSION = 2

MIGUEL_GAME_IDS = (
    "13",
    "244144",
    "172994",
    "1070",
    "436892",
    "380110",
    "384138",
    "118",
    "325414",
    "457314",
    "374680",
    "172225",
    "256804",
    "68448",
    "322289",
    "266524",
    "429405",
    "381248",
    "1219",
    "230408",
    "181",
    "4324",
    "418059",
    "400366",
    "383172",
    "342942",
    "169786",
    "266192",
    "224517",
    "167791",
    "366013",
    "399941",
    "355483",
    "26990",
    "255664",
    "199042",
    "39856",
    "387917",
    "425428",
    "822",
    "9209",
    "311322",
    "175549",
)

CAFE_GAME_IDS = (
    "822",
    "68448",
    "178900",
    "9209",
    "70323",
    "39856",
    "205398",
    "192291",
    "98778",
    "131357",
    "11",
    "181304",
    "324856",
    "366013",
    "41114",
    "263918",
    "9220",
    "254640",
    "158899",
    "188834",
    "233867",
    "172",
    "12",
    "12942",
    "432",
    "291453",
    "260605",
    "225694",
    "143741",
    "420087",
    "156129",
    "171131",
    "274960",
    "63268",
    "262543",
    "46213",
    "150145",
    "295374",
    "168435",
    "135779",
)

_MECANICAS_CAFE = {
    "Aventura y narrativa": 2,
    "Cartas clásicas y bazas": 2,
    "Colección y contratos": 3,
    "Construcción de mazo": 2,
    "Control de área": 2,
    "Dados y riesgo": 3,
    "Deducción y engaño": 3,
    "Destreza y velocidad": 2,
    "Draft": 3,
    "Económico y mercado": 2,
    "Gestión de mano": 3,
    "Losetas y patrones": 3,
    "Lápiz y papel": 2,
    "Motor y progresión": 2,
    "Movimiento y carreras": 2,
    "Negociación y diplomacia": 2,
    "Party y comunicación": 3,
    "Selección de acciones": 3,
    "Subastas": 2,
    "Táctica y guerra": 2,
}

_TEMATICA_CAFE = {
    "Abstracto o sin tema": 3,
    "Ciencia ficción y espacio": 2,
    "Cultura pop y humor": 3,
    "Deportes y carreras": 2,
    "Economía, industria y ciudades": 3,
    "Exploración y aventura": 3,
    "Fantasía y mitología": 3,
    "Historia antigua y medieval": 2,
    "Historia moderna y guerra": 2,
    "Horror": 1,
    "Intriga y misterio": 2,
    "Naturaleza y animales": 3,
}

PERFILES = (
    {
        "id": "coleccionista",
        "nombre": "Coleccionista",
        "tipo": "personal",
        "descripcion": "Colección personal equilibrada.",
        "metas": {},
    },
    {
        "id": "miguel",
        "nombre": "Colección de Miguel",
        "tipo": "personal",
        "descripcion": "Colección personal de Miguel.",
        "metas": {},
    },
    {
        "id": "cafe",
        "nombre": "Café demo",
        "tipo": "mesa",
        "descripcion": "Ludoteca B2B variada y rotativa. No opera partidas en solitario.",
        "exclusiones_plan": {
            "mecanicas": ("Legacy Game",),
            "prefijos_titulo": ("EXIT: The Game",),
        },
        "metas": {
            "Jugadores": {"1": 0, "2": 3, "3 a 4": 4, "5 a 6": 5, "7 o más": 4},
            "Duración": {"hasta 30": 6, "31 a 60": 6, "61 a 120": 2, "más de 120": 1},
            "Peso": {"ligero": 8, "medio": 7, "pesado": 2},
            "Interacción": {"cooperativo": 4, "directa": 7, "indirecta": 5, "ninguna": 5},
            "Mecánicas": _MECANICAS_CAFE,
            "Temática": _TEMATICA_CAFE,
        },
    },
)


def juego_excluido_del_plan(perfil_id: str, nombre: str, mecanicas: Collection[str]) -> bool:
    """Indica si un candidato no debe aparecer en los planes del perfil."""
    perfil = next(perfil for perfil in PERFILES if perfil["id"] == perfil_id)
    exclusiones = cast(dict[str, Collection[str]], perfil.get("exclusiones_plan", {}))
    return bool(
        set(mecanicas) & set(exclusiones.get("mecanicas", ()))
        or nombre.startswith(tuple(exclusiones.get("prefijos_titulo", ())))
    )
