"""Consultas de solo lectura para catalogo y coleccion."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, UserCollection


class CatalogoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def buscar_juegos(self, consulta: str, limite: int) -> list[Game]:
        statement = select(Game).order_by(Game.nombre).limit(limite)
        if consulta:
            patron = f"%{_escapar_like(consulta.lower())}%"
            statement = statement.where(Game.nombre.ilike(patron, escape="\\"))
        return list((await self._session.scalars(statement)).all())

    async def obtener_juego(self, game_id: str) -> Game | None:
        return await self._session.get(Game, game_id)

    async def juegos_de_coleccion(self, user_id: str) -> list[tuple[Game, UserCollection]]:
        statement = (
            select(Game, UserCollection)
            .join(UserCollection, UserCollection.game_id == Game.id)
            .where(UserCollection.user_id == user_id)
            .order_by(Game.nombre)
        )
        return list((await self._session.execute(statement)).tuples().all())


def _escapar_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
