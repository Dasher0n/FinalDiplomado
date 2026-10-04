"""Esquemas de escritura de la coleccion."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


class AgregarColeccionSolicitud(BaseModel):
    game_id: str
    precio_pagado: Decimal | None = Field(default=None, ge=0)


class ColeccionMutacionRespuesta(BaseModel):
    game_id: str
    agregado: bool
    precio_pagado: Decimal | None = None

    @field_serializer("precio_pagado", when_used="unless-none")
    def serializar_precio(self, valor: Decimal) -> str:
        return f"{valor:.2f}"
