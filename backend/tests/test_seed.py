"""La siembra no toca red y puede ejecutarse repetidamente."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Game, User, UserCollection
from app.db.seed import seed_database


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

        assert first == {"games": 2, "users": 1, "collection": 2}
        assert second == {"games": 0, "users": 0, "collection": 0}
        assert await session.scalar(select(func.count()).select_from(Game)) == 2
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(UserCollection)) == 2
        game = await session.get(Game, "1")
        assert game is not None
        assert game.precio_usd is not None
        assert game.fila_vector == 0

    await engine.dispose()
