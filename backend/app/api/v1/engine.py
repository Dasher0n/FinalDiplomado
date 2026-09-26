"""Endpoints que exponen el motor determinista a la interfaz."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.api.v1.catalogo import JuegoNoEncontrado, transformar_bgp_url
from app.core.errors import SommelierError
from app.db.models import Game
from app.engine.artefactos import ArtefactosMotor
from app.engine.motor import (
    cobertura,
    evaluar_redundancia,
    niveles_de_juego,
    plan_compra,
    que_saco_hoy,
)
from app.repositories.catalogo import CatalogoRepository
from app.schemas.engine import (
    CoberturaEjeRespuesta,
    CoberturaRespuesta,
    EstaNocheJuego,
    EstaNocheRespuesta,
    EstaNocheSolicitud,
    EvaluarRespuesta,
    EvaluarSolicitud,
    JuegoMotor,
    NivelCubierto,
    PlanCompraRespuesta,
    PlanCompraSolicitud,
    SimilitudRespuesta,
)

router = APIRouter(prefix="/engine", tags=["motor"])

_ATRIBUTO_POR_EJE = {
    "Jugadores": "nivel_jugadores",
    "Duración": "nivel_duracion",
    "Peso": "nivel_peso",
    "Interacción": "nivel_interaccion",
    "Mecánicas": "familias_mec",
    "Temática": "familias_tema",
}


class SolicitudInvalidaMotor(SommelierError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "solicitud_motor_invalida"


def _artefactos(request: Request) -> ArtefactosMotor:
    return request.app.state.artefactos_motor


def _niveles(
    juego: Game, artefactos: ArtefactosMotor, estados: dict[tuple[str, str], str]
) -> list[NivelCubierto]:
    cubre = niveles_de_juego(juego, artefactos.tipos)
    return [
        NivelCubierto(eje=eje, nivel=nivel, estado=estados[(eje, nivel)])
        for eje, nivel in sorted(cubre & set(estados))
    ]


def _juego(
    juego: Game,
    artefactos: ArtefactosMotor,
    estados_niveles: dict[tuple[str, str], str] | None = None,
) -> JuegoMotor:
    return JuegoMotor(
        id=juego.id,
        nombre=juego.nombre,
        imagen_url=juego.image_url,
        promedio=juego.average,
        precio_usd=juego.precio_usd,
        precio_confiable=juego.precio_confiable,
        fecha_precio=juego.fecha_precio,
        url_bgp=transformar_bgp_url(juego.bgp_url),
        peso=juego.weight,
        nivel_peso=juego.nivel_peso,
        peso_estimado=juego.weight_imputado,
        peso_pocos_votos=juego.weight_pocos_votos,
        duracion_estimada=juego.duracion_imputada,
        jugadores_estimados=juego.jugadores_imputados,
        niveles_que_cubre=(
            _niveles(juego, artefactos, estados_niveles) if estados_niveles is not None else []
        ),
    )


def _conteos_niveles(juegos: list[Game], artefactos: ArtefactosMotor, eje: str) -> dict[str, int]:
    atributo = _ATRIBUTO_POR_EJE[eje]
    conteos = {nivel: 0 for nivel in artefactos.tipos[eje]}
    for juego in juegos:
        valores = getattr(juego, atributo) or []
        if isinstance(valores, str):
            valores = [valores]
        for nivel in valores:
            if nivel in conteos:
                conteos[nivel] += 1
    return conteos


async def _coleccion(session: DbSession, user: CurrentUser) -> list[Game]:
    return [juego for juego, _ in await CatalogoRepository(session).juegos_de_coleccion(user.id)]


@router.post("/evaluate", response_model=EvaluarRespuesta)
async def evaluar(
    solicitud: EvaluarSolicitud, request: Request, session: DbSession, user: CurrentUser
) -> EvaluarRespuesta:
    repo = CatalogoRepository(session)
    candidato = await repo.obtener_juego(solicitud.game_id)
    if candidato is None:
        raise JuegoNoEncontrado("No existe un juego con ese identificador.")
    artefactos = _artefactos(request)
    coleccion = await _coleccion(session, user)
    veredicto, cercano, resultado, exacta = evaluar_redundancia(artefactos, candidato, coleccion)
    cobertura_actual = cobertura(artefactos, coleccion)
    estados_huecos = {
        (eje, nivel): "faltante"
        for eje, eje_cobertura in cobertura_actual.ejes.items()
        for nivel in eje_cobertura.faltantes
    } | {
        (eje, nivel): "debil"
        for eje, eje_cobertura in cobertura_actual.ejes.items()
        for nivel in eje_cobertura.debiles
    }
    razones = {
        "redundante": [
            "Comparte una edición o línea de producto con tu colección."
            if exacta
            else "Su similitud con tu colección alcanza el criterio de redundancia.",
            "No cubre niveles faltantes ni débiles.",
        ],
        "parecido_pero_cubre_hueco": [
            "Se parece a un juego que ya tienes.",
            "También cubre niveles faltantes o débiles.",
        ],
        "parecido": ["Se parece a un juego que ya tienes, sin alcanzar redundancia."],
        "aporta": ["Aporta una experiencia distinta a tu colección."],
    }
    return EvaluarRespuesta(
        veredicto=veredicto,
        juego=_juego(candidato, artefactos, estados_huecos),
        juego_mas_parecido=_juego(cercano, artefactos) if cercano else None,
        similitud=SimilitudRespuesta(**resultado.__dict__) if resultado else None,
        regla_exacta=exacta,
        niveles_que_cubre=_niveles(candidato, artefactos, estados_huecos),
        veredicto_razones=razones[veredicto],
    )


@router.get("/coverage", response_model=CoberturaRespuesta)
async def ver_cobertura(
    request: Request, session: DbSession, user: CurrentUser
) -> CoberturaRespuesta:
    artefactos = _artefactos(request)
    coleccion = await _coleccion(session, user)
    resultado = cobertura(artefactos, coleccion)
    return CoberturaRespuesta(
        ejes={
            eje: CoberturaEjeRespuesta(
                porcentaje=round(100 * len(valor.cubiertos) / len(artefactos.tipos[eje]), 1),
                cubiertos=list(valor.cubiertos),
                faltantes=list(valor.faltantes),
                debiles=valor.debiles,
                conteo_por_nivel=_conteos_niveles(coleccion, artefactos, eje),
            )
            for eje, valor in resultado.ejes.items()
        }
    )


@router.post("/buy-plan", response_model=PlanCompraRespuesta)
async def comprar_plan(
    solicitud: PlanCompraSolicitud, request: Request, session: DbSession, user: CurrentUser
) -> PlanCompraRespuesta:
    if solicitud.modo == "precio" and solicitud.presupuesto is None:
        raise SolicitudInvalidaMotor("El modo precio requiere un presupuesto.")
    artefactos = _artefactos(request)
    repo = CatalogoRepository(session)
    resultado = plan_compra(
        artefactos,
        await _coleccion(session, user),
        await repo.todos_los_juegos(),
        n=solicitud.n,
        modo=solicitud.modo,
        presupuesto=solicitud.presupuesto,
        average_min=solicitud.average_min,
        users_rated_min=solicitud.users_rated_min,
        ejes_ignorados=solicitud.ejes_ignorados,
    )
    cobertura_actual = cobertura(artefactos, await _coleccion(session, user))
    estados_huecos = {
        (eje, nivel): "faltante"
        for eje, eje_cobertura in cobertura_actual.ejes.items()
        if eje not in solicitud.ejes_ignorados
        for nivel in eje_cobertura.faltantes
    } | {
        (eje, nivel): "debil"
        for eje, eje_cobertura in cobertura_actual.ejes.items()
        if eje not in solicitud.ejes_ignorados
        for nivel in eje_cobertura.debiles
    }
    return PlanCompraRespuesta(
        juegos=[_juego(juego, artefactos, estados_huecos) for juego in resultado.juegos],
        valor_cubierto=resultado.valor_cubierto,
        valor_pendiente=resultado.valor_pendiente,
        costo=resultado.costo,
    )


@router.post("/tonight", response_model=EstaNocheRespuesta)
async def esta_noche(
    solicitud: EstaNocheSolicitud, request: Request, session: DbSession, user: CurrentUser
) -> EstaNocheRespuesta:
    artefactos = _artefactos(request)
    juegos = que_saco_hoy(
        await _coleccion(session, user),
        solicitud.jugadores,
        solicitud.minutos,
        solicitud.edad_minima,
    )
    return EstaNocheRespuesta(
        juegos=[
            EstaNocheJuego(
                **_juego(juego, artefactos).model_dump(),
                es_mejor_numero_jugadores=mejor,
                duracion_imputada=juego.duracion_imputada,
            )
            for juego, mejor in juegos
        ]
    )
