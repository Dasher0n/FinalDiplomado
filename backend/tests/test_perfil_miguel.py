"""Perfil "miguel": definición y siembra idempotente de su colección."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import CollectionProfile, Game, UserCollection
from app.db.seed import seed_demo_user_and_collection
from app.profiles import MIGUEL_GAME_IDS, PERFILES


def test_perfil_miguel_es_personal_con_metas_por_defecto() -> None:
    perfil = next(p for p in PERFILES if p["id"] == "miguel")
    coleccionista = next(p for p in PERFILES if p["id"] == "coleccionista")

    assert perfil["tipo"] == "personal"
    assert perfil["metas"] == coleccionista["metas"] == {}
    assert len(MIGUEL_GAME_IDS) == 43 == len(set(MIGUEL_GAME_IDS))


async def test_siembra_agrega_43_juegos_a_miguel_y_es_idempotente() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        session.add_all(
            Game(id=game_id, nombre=f"Juego {game_id}", fila_vector=fila)
            for fila, game_id in enumerate(MIGUEL_GAME_IDS)
        )
        await session.flush()

        await seed_demo_user_and_collection(session)
        await session.commit()
        total = (
            select(func.count())
            .select_from(UserCollection)
            .where(UserCollection.profile_id == "miguel")
        )
        assert await session.scalar(total) == 43

        _, agregados = await seed_demo_user_and_collection(session)
        await session.commit()
        assert agregados == 0
        assert await session.scalar(total) == 43
        assert await session.get(CollectionProfile, "miguel") is not None

    await engine.dispose()
