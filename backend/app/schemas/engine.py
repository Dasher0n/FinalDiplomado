"""Esquemas de las operaciones deterministas del motor."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

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


class CoberturaEjeRespuesta(BaseModel):
    porcentaje: float
    cubiertos: list[str]
    faltantes: list[str]
    debiles: dict[str, str]
    conteo_por_nivel: dict[str, int]


class ConteoEstados(BaseModel):
    solidos: int
    debiles: int
    faltantes: int


class CambioNivel(BaseModel):
    eje: str
    nivel: str
    antes: int
    despues: int


class ImpactoEje(BaseModel):
    antes: ConteoEstados
    despues: ConteoEstados


class ImpactoCobertura(BaseModel):
    ejes: dict[str, ImpactoEje]
    cambios_nivel: list[CambioNivel]


class JuegoSimilar(BaseModel):
    juego: JuegoMotor
    similitud: SimilitudRespuesta


class EvaluarSolicitud(BaseModel):
    game_id: str
    top_k: int = Field(default=3, ge=1, le=10)


class EvaluarRespuesta(BaseModel):
    veredicto: str
    juego: JuegoMotor
    juego_mas_parecido: JuegoMotor | None
    similitud: SimilitudRespuesta | None
    regla_exacta: bool
    niveles_que_cubre: list[NivelCubierto]
    veredicto_razones: list[str]
    similares: list[JuegoSimilar]
    impacto: ImpactoCobertura


class CoberturaRespuesta(BaseModel):
    ejes: dict[str, CoberturaEjeRespuesta]


class PlanCompraSolicitud(BaseModel):
    n: int = Field(default=5, ge=1, le=20)
    modo: str = Field(default="juego", pattern="^(juego|precio)$")
    presupuesto: float | None = Field(default=None, gt=0)
    average_min: float = Field(default=0, ge=0)
    users_rated_min: int = Field(default=1000, ge=0)
    ejes_ignorados: list[str] = Field(default_factory=list)
    orden: str = Field(default="mejor_ajuste", pattern="^(mejor_ajuste|mejor_valorados)$")


class CoberturaRadar(BaseModel):
    porcentajes: dict[str, float]


class JuegoPlanCompra(JuegoMotor):
    impacto: ImpactoCobertura


class PlanCompraRespuesta(BaseModel):
    juegos: list[JuegoPlanCompra]
    valor_cubierto: float
    valor_pendiente: float
    precio_total_usd: float
    juegos_sin_precio: int


class EstaNocheSolicitud(BaseModel):
    jugadores: int = Field(ge=1, le=99)
    minutos: float = Field(gt=0, le=10000)
    edad_minima: float | None = Field(default=None, ge=0)


class EstaNocheJuego(JuegoMotor):
    nivel_ajuste: Literal["ideal", "funciona"]
    best_players: list[int]
    duracion_imputada: bool


class EstaNocheRespuesta(BaseModel):
    juegos: list[EstaNocheJuego]


class VentaImpactoSolicitud(BaseModel):
    game_id: str


class VentaImpactoRespuesta(BaseModel):
    juego: JuegoMotor
    impacto: ImpactoCobertura
