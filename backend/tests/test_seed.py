"""La siembra no toca red y puede ejecutarse repetidamente."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Game, User, UserCollection
from app.db.seed import seed_database
from app.db.session import dispose_db, init_db


async def test_seed_imports_catalog_and_is_idempotent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    artefactos_dir = Path(__file__).parent / "fixtures"

    async with maker() as session:
        first = await seed_database(session, artefactos_dir)
        await session.commit()
        second = await seed_database(session, artefactos_dir)
        await session.commit()

        assert first == {"games": 3, "users": 1, "collection": 3}
        assert second == {"games": 0, "users": 0, "collection": 0}
        assert await session.scalar(select(func.count()).select_from(Game)) == 3
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(UserCollection)) == 3
        game = await session.get(Game, "1")
        assert game is not None
        assert game.precio_usd is not None
        assert game.fila_vector == 0

    await engine.dispose()


async def test_init_db_migra_indice_legacy_de_coleccion(monkeypatch) -> None:
    database_url = "sqlite+aiosqlite:///:memory:"
    monkeypatch.setattr("app.db.session.settings.database_url", database_url)
    monkeypatch.setattr("app.db.session._engine", None)
    monkeypatch.setattr("app.db.session._sessionmaker", None)

    from app.db.session import get_engine

    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("DROP TABLE user_collection"))
        await connection.execute(
            text(
                "CREATE TABLE user_collection (id VARCHAR(32) PRIMARY KEY, "
                "user_id VARCHAR(32) NOT NULL, game_id VARCHAR(32) NOT NULL, "
                "precio_pagado NUMERIC, agregado_en DATETIME NOT NULL, "
                "UNIQUE (user_id, game_id))"
            )
        )
    await init_db()
    async with get_engine().connect() as connection:
        columnas = (await connection.execute(text("PRAGMA table_info(user_collection)"))).mappings()
        assert "profile_id" in {columna["name"] for columna in columnas}
        indices = (await connection.execute(text("PRAGMA index_list(user_collection)"))).mappings()
        for indice in indices:
            if indice["unique"]:
                nombres = (
                    await connection.execute(text(f"PRAGMA index_info({indice['name']})"))
                ).mappings()
                assert {columna["name"] for columna in nombres} != {"user_id", "game_id"}
    await dispose_db()
