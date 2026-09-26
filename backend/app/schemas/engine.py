"""Esquemas de las operaciones deterministas del motor."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer


class SimilitudRespuesta(BaseModel):
    mecanicas: float | None
    ocasion: float
    interaccion: float
    tematica: float | None
    total: float


class NivelCubierto(BaseModel):
    eje: str
    nivel: str
    estado: str

    @property
    def etiqueta(self) -> str:
        return f"{self.eje}: {self.nivel}"


class JuegoMotor(BaseModel):
    id: str
    nombre: str
    imagen_url: str | None
    promedio: float | None
    precio_usd: Decimal | None
    precio_confiable: bool
    fecha_precio: datetime | None
    url_bgp: str | None
    peso: float | None
    nivel_peso: str | None
    peso_estimado: bool
    peso_pocos_votos: bool
    duracion_estimada: bool
    jugadores_estimados: bool
    niveles_que_cubre: list[NivelCubierto] = Field(default_factory=list)

    @field_serializer("precio_usd", when_used="unless-none")
    def serializar_precio(self, valor: Decimal) -> str:
        return f"{valor:.2f}"


class EvaluarSolicitud(BaseModel):
    game_id: str


class EvaluarRespuesta(BaseModel):
    veredicto: str
    juego: JuegoMotor
    juego_mas_parecido: JuegoMotor | None
    similitud: SimilitudRespuesta | None
    regla_exacta: bool
    niveles_que_cubre: list[NivelCubierto]
    veredicto_razones: list[str]


class CoberturaEjeRespuesta(BaseModel):
    porcentaje: float
    cubiertos: list[str]
    faltantes: list[str]
    debiles: dict[str, str]
    conteo_por_nivel: dict[str, int]


class CoberturaRespuesta(BaseModel):
    ejes: dict[str, CoberturaEjeRespuesta]


class PlanCompraSolicitud(BaseModel):
    n: int = Field(default=5, ge=1, le=20)
    modo: str = Field(default="juego", pattern="^(juego|precio)$")
    presupuesto: float | None = Field(default=None, gt=0)
    average_min: float = Field(default=0, ge=0)
    users_rated_min: int = Field(default=1000, ge=0)
    ejes_ignorados: list[str] = Field(default_factory=list)


class PlanCompraRespuesta(BaseModel):
    juegos: list[JuegoMotor]
    valor_cubierto: float
    valor_pendiente: float
    costo: float


class EstaNocheSolicitud(BaseModel):
    jugadores: int = Field(ge=1, le=99)
    minutos: float = Field(gt=0, le=10000)
    edad_minima: float | None = Field(default=None, ge=0)


class EstaNocheJuego(JuegoMotor):
    es_mejor_numero_jugadores: bool
    duracion_imputada: bool


class EstaNocheRespuesta(BaseModel):
    juegos: list[EstaNocheJuego]
