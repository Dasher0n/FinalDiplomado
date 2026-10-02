"""Perfiles disponibles y su contexto para la interfaz."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentProfile, CurrentUser, DbSession
from app.db.models import CollectionProfile, UserCollection
from app.schemas.perfiles import ContextoPerfilRespuesta, PerfilesRespuesta, PerfilRespuesta

router = APIRouter(prefix="/profiles", tags=["perfiles"])


def _perfil(perfil: CollectionProfile) -> PerfilRespuesta:
    return PerfilRespuesta(
        id=perfil.id,
        nombre=perfil.nombre,
        tipo=perfil.tipo,
        descripcion=perfil.descripcion,
        version_configuracion=perfil.version_configuracion,
        metas=perfil.metas,
    )


@router.get("", response_model=PerfilesRespuesta)
async def listar_perfiles(session: DbSession) -> PerfilesRespuesta:
    perfiles = list(
        (await session.scalars(select(CollectionProfile).order_by(CollectionProfile.id))).all()
    )
    return PerfilesRespuesta(perfiles=[_perfil(perfil) for perfil in perfiles])


@router.get("/context", response_model=ContextoPerfilRespuesta)
async def contexto_perfil(
    session: DbSession, user: CurrentUser, perfil: CurrentProfile
) -> ContextoPerfilRespuesta:
    cantidad = await session.scalar(
        select(func.count())
        .select_from(UserCollection)
        .where(UserCollection.user_id == user.id, UserCollection.profile_id == perfil.id)
    )
    return ContextoPerfilRespuesta(perfil=_perfil(perfil), juegos_en_coleccion=cantidad or 0)
