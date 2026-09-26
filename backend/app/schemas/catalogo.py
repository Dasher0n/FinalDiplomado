"""Esquemas de lectura del catalogo y la coleccion."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class PrecioJuego(BaseModel):
    precio_usd: Decimal | None
    precio_confiable: bool
    fecha_precio: datetime | None
    ofertas_us_con_stock: float | None
    url_bgp: str | None

    @field_serializer("precio_usd", when_used="unless-none")
    def serializar_precio_usd(self, precio: Decimal) -> str:
        return f"{precio:.2f}"


class JuegoListado(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre: str
    anio: int | None
    imagen_url: str | None
    miniatura_url: str | None
    jugadores_minimos: float | None
    jugadores_maximos: float | None
    duracion_minima: float | None
    duracion_maxima: float | None
    promedio: float | None
    precio: PrecioJuego


class JuegoColeccion(JuegoListado):
    precio_pagado: Decimal | None
    agregado_en: datetime


class ColeccionRespuesta(BaseModel):
    juegos: list[JuegoColeccion]


class BusquedaJuegosRespuesta(BaseModel):
    juegos: list[JuegoListado]


class JuegoDetalle(JuegoListado):
    edad_minima: float | None
    edad_comunitaria: float | None
    peso: float | None
    mecanicas: list[Any] | None
    categorias: list[Any] | None
    disenadores: list[Any] | None
    familias_mecanicas: list[Any] | None
    familias_tematicas: list[Any] | None
    nivel_jugadores: list[Any] | None
    nivel_duracion: str | None
    nivel_peso: str | None
    nivel_interaccion: str | None
    origen: str
    confianza: str
    fuentes: list[Any]
    evidencia: list[Any]
    peso_estimado: bool
    peso_pocos_votos: bool
    duracion_estimada: bool
    jugadores_estimados: bool

    @field_serializer("peso", when_used="unless-none")
    def serializar_peso(self, peso: float) -> float:
        return round(peso, 1)
