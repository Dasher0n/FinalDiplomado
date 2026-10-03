"""Reglas puras del motor de recomendaciones."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz, process

from app.db.models import Game
from app.engine.artefactos import ArtefactosMotor

_ATRIBUTO_POR_EJE = {
    "Jugadores": "nivel_jugadores",
    "Duración": "nivel_duracion",
    "Peso": "nivel_peso",
    "Interacción": "nivel_interaccion",
    "Mecánicas": "familias_mec",
    "Temática": "familias_tema",
}


@dataclass(frozen=True)
class Similitud:
    mecanicas: float | None
    ocasion: float
    interaccion: float
    tematica: float | None
    total: float


@dataclass(frozen=True)
class CoberturaEje:
    cubiertos: tuple[str, ...]
    faltantes: tuple[str, ...]
    debiles: dict[str, str]


@dataclass(frozen=True)
class ResultadoCobertura:
    ejes: dict[str, CoberturaEje]


@dataclass(frozen=True)
class ResultadoCompra:
    juegos: tuple[Game, ...]
    valor_cubierto: float
    valor_pendiente: float
    costo: float


def similitud(artefactos: ArtefactosMotor, primero: Game, segundo: Game) -> Similitud:
    """Calcula los cuatro bloques y renormaliza solo los que existen en ambos juegos."""
    izquierda, derecha = primero.fila_vector, segundo.fila_vector
    mecanicas = (
        float(artefactos.mecanicas[izquierda].multiply(artefactos.mecanicas[derecha]).sum())
        if primero.tiene_mecanicas and segundo.tiene_mecanicas
        else None
    )
    tematica = (
        float(artefactos.tematica[izquierda].multiply(artefactos.tematica[derecha]).sum())
        if primero.tiene_categorias and segundo.tiene_categorias
        else None
    )
    ocasion = float(
        1 - ((artefactos.ocasion[izquierda] - artefactos.ocasion[derecha]) ** 2).sum() / 2
    )
    interaccion = float(
        1 - ((artefactos.interaccion[izquierda] - artefactos.interaccion[derecha]) ** 2).sum() / 2
    )
    bloques = {
        "mecanicas": mecanicas,
        "ocasion": ocasion,
        "interaccion": interaccion,
        "tematica": tematica,
    }
    disponibles = {nombre: valor for nombre, valor in bloques.items() if valor is not None}
    divisor = sum(artefactos.pesos[nombre] for nombre in disponibles)
    total = sum(artefactos.pesos[nombre] * valor for nombre, valor in disponibles.items()) / divisor
    return Similitud(mecanicas, ocasion, interaccion, tematica, float(total))


def cobertura(
    artefactos: ArtefactosMotor,
    juegos: Iterable[Game],
    metas: dict[str, dict[str, int]] | None = None,
) -> ResultadoCobertura:
    cuentas: dict[str, dict[str, list[str]]] = {
        eje: {nivel: [] for nivel in niveles} for eje, niveles in artefactos.tipos.items()
    }
    for juego in juegos:
        for eje, atributo in _ATRIBUTO_POR_EJE.items():
            valores = getattr(juego, atributo) or []
            if isinstance(valores, str):
                valores = [valores]
            for nivel in valores:
                if nivel in cuentas[eje]:
                    cuentas[eje][nivel].append(juego.nombre)

    metas = metas or {}
    ejes = {}
    for eje, niveles in cuentas.items():
        metas_eje = metas.get(eje, {})
        niveles_relevantes = {
            nivel: juegos_nivel
            for nivel, juegos_nivel in niveles.items()
            if metas_eje.get(nivel, 2) > 0
        }
        ejes[eje] = CoberturaEje(
            cubiertos=tuple(
                nivel
                for nivel, juegos_nivel in niveles_relevantes.items()
                if len(juegos_nivel) >= metas_eje.get(nivel, 2)
            ),
            faltantes=tuple(
                nivel for nivel, juegos_nivel in niveles_relevantes.items() if not juegos_nivel
            ),
            debiles={
                nivel: juegos_nivel[0]
                for nivel, juegos_nivel in niveles_relevantes.items()
                if 0 < len(juegos_nivel) < metas_eje.get(nivel, 2)
            },
        )
    return ResultadoCobertura(ejes)


def niveles_de_juego(juego: Game, tipos: dict[str, tuple[str, ...]]) -> set[tuple[str, str]]:
    niveles: set[tuple[str, str]] = set()
    for eje, atributo in _ATRIBUTO_POR_EJE.items():
        valores = getattr(juego, atributo) or []
        if isinstance(valores, str):
            valores = [valores]
        niveles.update((eje, valor) for valor in valores if valor in tipos[eje])
    return niveles


def regla_exacta(candidato: Game, existente: Game) -> bool:
    if set(candidato.product_line or []) & set(existente.product_line or []):
        return True
    return existente.id in set(candidato.reimplements or []) | set(
        candidato.reimplemented_by or []
    ) or candidato.id in set(existente.reimplements or []) | set(existente.reimplemented_by or [])


def evaluar_redundancia(
    artefactos: ArtefactosMotor,
    candidato: Game,
    coleccion: Iterable[Game],
    metas: dict[str, dict[str, int]] | None = None,
) -> tuple[str, Game | None, Similitud | None, bool]:
    juegos = tuple(coleccion)
    if not juegos:
        return "aporta", None, None, False
    parecidos = [(similitud(artefactos, candidato, juego), juego) for juego in juegos]
    mejor, juego_mejor = max(parecidos, key=lambda par: par[0].total)
    cubre_hueco = bool(
        niveles_de_juego(candidato, artefactos.tipos)
        & {
            (eje, nivel)
            for eje, resultado in cobertura(artefactos, juegos, metas).ejes.items()
            for nivel in (*resultado.faltantes, *resultado.debiles)
        }
    )
    exacta = any(regla_exacta(candidato, juego) for juego in juegos)
    es_redundante = exacta or mejor.total >= artefactos.umbral_redundante
    if es_redundante and cubre_hueco:
        return "parecido_pero_cubre_hueco", juego_mejor, mejor, exacta
    if es_redundante:
        return "redundante", juego_mejor, mejor, exacta
    if mejor.total >= artefactos.umbral_parecido:
        return "parecido", juego_mejor, mejor, False
    return "aporta", juego_mejor, mejor, False


def plan_compra(
    artefactos: ArtefactosMotor,
    coleccion: Iterable[Game],
    candidatos: Iterable[Game],
    *,
    n: int,
    modo: str,
    presupuesto: float | None = None,
    average_min: float = 0,
    users_rated_min: int = 1000,
    ejes_ignorados: Iterable[str] = (),
    precios_usuario: dict[str, Decimal | float] | None = None,
    orden: str = "mejor_ajuste",
    metas: dict[str, dict[str, int]] | None = None,
    excluir_ids: Iterable[str] = (),
) -> ResultadoCompra:
    if modo not in {"juego", "precio"}:
        raise ValueError("El modo debe ser juego o precio")
    if modo == "precio" and presupuesto is None:
        raise ValueError("El modo precio requiere presupuesto")
    if orden not in {"mejor_ajuste", "mejor_valorados"}:
        raise ValueError("El orden debe ser mejor_ajuste o mejor_valorados")
    coleccion = tuple(coleccion)
    excluidos = set(excluir_ids)
    ignorados = set(ejes_ignorados)
    precios_usuario = precios_usuario or {}
    metas = metas or {}
    conteos = {
        (eje, nivel): 0
        for eje, niveles in artefactos.tipos.items()
        if eje not in ignorados
        for nivel in niveles
        if metas.get(eje, {}).get(nivel, 2) > 0
    }
    for juego in coleccion:
        for nivel in niveles_de_juego(juego, artefactos.tipos):
            if nivel in conteos:
                conteos[nivel] += 1
    conteos_iniciales = dict(conteos)

    def valor_incremental(nivel: tuple[str, str], conteo: int) -> float:
        eje, etiqueta = nivel
        meta = metas.get(eje, {}).get(etiqueta, 2)
        if conteo >= meta:
            return 0
        niveles_relevantes = sum(
            metas.get(eje, {}).get(item, 2) > 0 for item in artefactos.tipos[eje]
        )
        if conteo == 0:
            if meta == 1:
                return 1 / niveles_relevantes
            return 0.5 / niveles_relevantes
        return 0.5 / niveles_relevantes / (meta - 1)

    def valor_pendiente(conteos_actuales: dict[tuple[str, str], int]) -> float:
        return sum(
            sum(valor_incremental(nivel, conteo + paso) for paso in range(meta - conteo))
            for nivel, conteo in conteos_actuales.items()
            for eje, etiqueta in [nivel]
            for meta in [metas.get(eje, {}).get(etiqueta, 2)]
        )

    def costo(juego: Game) -> float | None:
        if modo == "juego":
            return 1.0
        precio = precios_usuario.get(juego.id, juego.precio_usd if juego.precio_confiable else None)
        return float(precio) if precio is not None else None

    disponibles = [
        juego
        for juego in candidatos
        if juego.id not in {existente.id for existente in coleccion} | excluidos
        and (juego.average or 0) >= average_min
        and (juego.users_rated or 0) >= users_rated_min
        and costo(juego) is not None
        and any(
            valor_incremental(nivel, conteos[nivel])
            for nivel in niveles_de_juego(juego, artefactos.tipos) & set(conteos)
        )
    ]
    seleccion: list[Game] = []
    gasto = 0.0
    valor_greedy = 0.0
    while disponibles and (modo == "precio" or len(seleccion) < n):
        opciones = [
            juego
            for juego in disponibles
            if modo == "juego" or gasto + (costo(juego) or 0) <= (presupuesto or 0)
        ]
        if not opciones:
            break

        def clave(juego: Game) -> tuple[float, float]:
            valor = sum(
                valor_incremental(nivel, conteos[nivel])
                for nivel in niveles_de_juego(juego, artefactos.tipos) & set(conteos)
            )
            ajuste = valor / (costo(juego) or 1)
            return (ajuste, juego.average or 0)

        elegido = max(opciones, key=clave)
        valor = sum(
            valor_incremental(nivel, conteos[nivel])
            for nivel in niveles_de_juego(elegido, artefactos.tipos) & set(conteos)
        )
        if valor == 0:
            break
        seleccion.append(elegido)
        for nivel in niveles_de_juego(elegido, artefactos.tipos) & set(conteos):
            conteos[nivel] += 1
        valor_greedy += valor
        gasto += costo(elegido) or 0
        disponibles.remove(elegido)

    if modo == "precio":
        individuales = [
            juego for juego in disponibles + seleccion if (costo(juego) or 0) <= (presupuesto or 0)
        ]
        if individuales:
            mejor_individual = max(
                individuales,
                key=lambda juego: (
                    sum(
                        valor_incremental(nivel, conteos_iniciales[nivel])
                        for nivel in niveles_de_juego(juego, artefactos.tipos)
                        & set(conteos_iniciales)
                    ),
                    juego.average or 0,
                ),
            )
            valor_individual = sum(
                valor_incremental(nivel, conteos_iniciales[nivel])
                for nivel in niveles_de_juego(mejor_individual, artefactos.tipos)
                & set(conteos_iniciales)
            )
            if valor_individual > valor_greedy:
                seleccion = [mejor_individual]
                gasto = costo(mejor_individual) or 0
                valor_greedy = valor_individual
                conteos = dict(conteos_iniciales)
                for nivel in niveles_de_juego(mejor_individual, artefactos.tipos) & set(conteos):
                    conteos[nivel] += 1
    return ResultadoCompra(
        tuple(seleccion),
        round(valor_greedy, 12),
        round(valor_pendiente(conteos), 12),
        gasto,
    )


def opciones_compra(
    artefactos: ArtefactosMotor,
    coleccion: Iterable[Game],
    candidatos: Iterable[Game],
    *,
    n: int,
    modo: str,
    presupuesto: float | None = None,
    average_min: float = 0,
    users_rated_min: int = 1000,
    ejes_ignorados: Iterable[str] = (),
    precios_usuario: dict[str, Decimal | float] | None = None,
    orden: str = "mejor_ajuste",
    metas: dict[str, dict[str, int]] | None = None,
) -> tuple[ResultadoCompra, ...]:
    """Genera alternativas disjuntas para que cada plan sea una decisión real."""
    candidatos = tuple(candidatos)
    excluidos: set[str] = set()
    opciones: list[ResultadoCompra] = []
    for _ in range(3):
        resultado = plan_compra(
            artefactos,
            coleccion,
            candidatos,
            n=n,
            modo=modo,
            presupuesto=presupuesto,
            average_min=average_min,
            users_rated_min=users_rated_min,
            ejes_ignorados=ejes_ignorados,
            precios_usuario=precios_usuario,
            orden=orden,
            metas=metas,
            excluir_ids=excluidos,
        )
        opciones.append(resultado)
        excluidos.update(juego.id for juego in resultado.juegos)
    return tuple(opciones)


def que_saco_hoy(
    juegos: Iterable[Game], jugadores: int, minutos: float, edad_minima: float | None = None
) -> list[tuple[Game, bool]]:
    resultado = []
    for juego in juegos:
        recomendados = set(juego.rec_players or [])
        dentro_caja = (
            (juego.min_players or jugadores) <= jugadores <= (juego.max_players or jugadores)
        )
        if (recomendados and jugadores not in recomendados) or (
            not recomendados and not dentro_caja
        ):
            continue
        if juego.max_playtime is not None and juego.max_playtime > minutos:
            continue
        edad = juego.community_age if juego.community_age is not None else juego.min_age
        if edad_minima is not None and edad is not None and edad > edad_minima:
            continue
        resultado.append((juego, jugadores in set(juego.best_players or [])))
    return sorted(resultado, key=lambda par: (par[1], par[0].average or 0), reverse=True)


def normalizar_nombre(nombre: str) -> str:
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", nombre.lower())
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"[\W_]+", " ", sin_acentos, flags=re.UNICODE).strip()


def buscar_local(
    consulta: str,
    juegos: Iterable[Game],
    *,
    aliases: dict[str, str] | None = None,
    umbral_directo: float = 90,
    umbral_ambiguo: float = 75,
) -> tuple[str, tuple[Game, ...]]:
    juegos = tuple(juegos)
    por_nombre = {normalizar_nombre(juego.nombre): juego for juego in juegos}
    for alias, game_id in (aliases or {}).items():
        juego = next((item for item in juegos if item.id == game_id), None)
        if juego is not None:
            por_nombre[normalizar_nombre(alias)] = juego
    resultados = process.extract(
        normalizar_nombre(consulta), por_nombre.keys(), scorer=fuzz.ratio, limit=5
    )
    if not resultados or resultados[0][1] < umbral_ambiguo:
        return "no_encontrado", ()
    candidatos = tuple(
        dict.fromkeys(
            por_nombre[nombre]
            for nombre, puntuacion, _ in resultados
            if puntuacion >= umbral_ambiguo
        )
    )
    if resultados[0][1] >= umbral_directo:
        return "encontrado", (por_nombre[resultados[0][0]],)
    return "ambiguo", candidatos
