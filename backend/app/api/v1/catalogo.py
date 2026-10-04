"""Endpoints de solo lectura del catalogo y la coleccion demo."""

from __future__ import annotations

from urllib.parse import quote_plus, unquote_plus, urlsplit, urlunsplit

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentProfile, CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import SommelierError
from app.db.models import Game, UserCollection
from app.repositories.catalogo import CatalogoRepository
from app.schemas.catalogo import (
    BusquedaJuegosRespuesta,
    ColeccionRespuesta,
    JuegoColeccion,
    JuegoDetalle,
    JuegoListado,
    PrecioJuego,
)
from app.schemas.coleccion import AgregarColeccionSolicitud, ColeccionMutacionRespuesta

router = APIRouter(tags=["catalogo"])


class JuegoNoEncontrado(SommelierError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "juego_no_encontrado"


@router.get("/collection", response_model=ColeccionRespuesta, summary="Coleccion demo")
async def obtener_coleccion(
    session: DbSession, user: CurrentUser, perfil: CurrentProfile
) -> ColeccionRespuesta:
    juegos = await CatalogoRepository(session).juegos_de_coleccion(user.id, perfil.id)
    return ColeccionRespuesta(
        juegos=[_juego_coleccion(game, collection) for game, collection in juegos]
    )


@router.post(
    "/collection", response_model=ColeccionMutacionRespuesta, status_code=status.HTTP_201_CREATED
)
async def agregar_coleccion(
    solicitud: AgregarColeccionSolicitud,
    session: DbSession,
    user: CurrentUser,
    perfil: CurrentProfile,
) -> ColeccionMutacionRespuesta:
    if await CatalogoRepository(session).obtener_juego(solicitud.game_id) is None:
        raise JuegoNoEncontrado("No existe un juego con ese identificador.")
    existente = await session.scalar(
        select(UserCollection).where(
            UserCollection.user_id == user.id,
            UserCollection.profile_id == perfil.id,
            UserCollection.game_id == solicitud.game_id,
        )
    )
    if existente is not None:
        return ColeccionMutacionRespuesta(
            game_id=solicitud.game_id, agregado=False, precio_pagado=existente.precio_pagado
        )
    session.add(
        UserCollection(
            user_id=user.id,
            profile_id=perfil.id,
            game_id=solicitud.game_id,
            precio_pagado=solicitud.precio_pagado,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return ColeccionMutacionRespuesta(game_id=solicitud.game_id, agregado=False)
    return ColeccionMutacionRespuesta(
        game_id=solicitud.game_id, agregado=True, precio_pagado=solicitud.precio_pagado
    )


@router.delete("/collection/{game_id}", response_model=ColeccionMutacionRespuesta)
async def quitar_coleccion(
    game_id: str, session: DbSession, user: CurrentUser, perfil: CurrentProfile
) -> ColeccionMutacionRespuesta:
    existente = await session.scalar(
        select(UserCollection).where(
            UserCollection.user_id == user.id,
            UserCollection.profile_id == perfil.id,
            UserCollection.game_id == game_id,
        )
    )
    if existente is None:
        raise JuegoNoEncontrado("El juego no esta en tu coleccion.")
    await session.delete(existente)
    await session.commit()
    return ColeccionMutacionRespuesta(game_id=game_id, agregado=False)


@router.get("/games", response_model=BusquedaJuegosRespuesta, summary="Buscar juegos")
async def buscar_juegos(
    session: DbSession,
    q: str = "",
    limit: int = Query(default=20, ge=1, le=100),
) -> BusquedaJuegosRespuesta:
    juegos = await CatalogoRepository(session).buscar_juegos(q.strip(), limit)
    return BusquedaJuegosRespuesta(juegos=[_juego_listado(game) for game in juegos])


@router.get("/games/{game_id}", response_model=JuegoDetalle, summary="Detalle de un juego")
async def obtener_juego(game_id: str, session: DbSession) -> JuegoDetalle:
    game = await CatalogoRepository(session).obtener_juego(game_id)
    if game is None:
        raise JuegoNoEncontrado("No existe un juego con ese identificador.")
    return _juego_detalle(game)


def _precio(game: Game) -> PrecioJuego:
    return PrecioJuego(
        precio_usd=game.precio_usd,
        precio_confiable=game.precio_confiable,
        fecha_precio=game.fecha_precio,
        ofertas_us_con_stock=game.n_ofertas_us_stock,
        url_bgp=transformar_bgp_url(game.bgp_url),
    )


def _juego_listado(game: Game) -> JuegoListado:
    return JuegoListado(
        id=game.id,
        nombre=game.nombre,
        anio=game.year,
        imagen_url=game.image_url,
        miniatura_url=game.thumbnail,
        jugadores_minimos=game.min_players,
        jugadores_maximos=game.max_players,
        duracion_minima=game.min_playtime,
        duracion_maxima=game.max_playtime,
        promedio=game.average,
        precio=_precio(game),
    )


def _juego_coleccion(game: Game, collection: UserCollection) -> JuegoColeccion:
    return JuegoColeccion(
        **_juego_listado(game).model_dump(),
        precio_pagado=collection.precio_pagado,
        agregado_en=collection.agregado_en,
    )


def _juego_detalle(game: Game) -> JuegoDetalle:
    return JuegoDetalle(
        **_juego_listado(game).model_dump(),
        edad_minima=game.min_age,
        edad_comunitaria=game.community_age,
        peso=game.weight,
        mecanicas=game.mechanics,
        categorias=game.categories,
        disenadores=game.designers,
        familias_mecanicas=game.familias_mec,
        familias_tematicas=game.familias_tema,
        nivel_jugadores=game.nivel_jugadores,
        nivel_duracion=game.nivel_duracion,
        nivel_peso=game.nivel_peso,
        nivel_interaccion=game.nivel_interaccion,
        origen=game.origen,
        confianza=game.confianza,
        fuentes=game.fuentes,
        evidencia=game.evidencia,
        peso_estimado=game.weight_imputado,
        peso_pocos_votos=game.weight_pocos_votos,
        duracion_estimada=game.duracion_imputada,
        jugadores_estimados=game.jugadores_imputados,
    )


def transformar_bgp_url(url: str | None) -> str | None:
    """Sustituye estructuralmente utm_source sin alterar el resto de la URL."""
    sitename = settings.bgp_sitename.strip()
    if not url or not sitename:
        return url

    partes = urlsplit(url)
    parametros: list[str] = []
    cambiado = False
    for parametro in partes.query.split("&"):
        clave, separador, valor = parametro.partition("=")
        if clave == "utm_source":
            # Solo se decodifica el valor de este parametro antes de sustituirlo.
            if unquote_plus(valor) == sitename:
                parametros.append(parametro)
            else:
                parametros.append(f"{clave}{separador}{quote_plus(sitename)}")
                cambiado = True
        else:
            parametros.append(parametro)
    if not cambiado:
        return url
    return urlunsplit(partes._replace(query="&".join(parametros)))
