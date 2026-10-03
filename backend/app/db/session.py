"""Engine y sesiones async de SQLAlchemy."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    _, _, path = url.partition("///")
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = settings.database_url
        ensure_sqlite_dir(url)
        _engine = create_async_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args={"timeout": 30} if url.startswith("sqlite") else {},
        )
        if url.startswith("sqlite"):

            @event.listens_for(_engine.sync_engine, "connect")
            def sqlite_pragmas(connection: Any, _: Any) -> None:
                cursor = connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from app.db import models  # noqa: F401
    from app.db.base import Base

    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            columnas_runs = (
                await connection.execute(text("PRAGMA table_info(agent_runs)"))
            ).mappings()
            nombres_runs = {columna["name"] for columna in columnas_runs}
            if "critic_attempts" not in nombres_runs:
                await connection.execute(
                    text(
                        "ALTER TABLE agent_runs ADD COLUMN critic_attempts "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                )
            if "critic_findings" not in nombres_runs:
                await connection.execute(
                    text("ALTER TABLE agent_runs ADD COLUMN critic_findings JSON")
                )
            columnas = (
                await connection.execute(text("PRAGMA table_info(user_collection)"))
            ).mappings()
            if "profile_id" not in {columna["name"] for columna in columnas}:
                await connection.execute(
                    text("ALTER TABLE user_collection ADD COLUMN profile_id VARCHAR(32)")
                )
                await connection.execute(
                    text("UPDATE user_collection SET profile_id = 'coleccionista'")
                )
            indices = (
                await connection.execute(text("PRAGMA index_list(user_collection)"))
            ).mappings()
            for indice in indices:
                if not indice["unique"]:
                    continue
                columnas_indice = (
                    await connection.execute(text(f"PRAGMA index_info({indice['name']})"))
                ).mappings()
                if {columna["name"] for columna in columnas_indice} == {"user_id", "game_id"}:
                    await connection.execute(text("DROP TABLE IF EXISTS user_collection_perfiles"))
                    await connection.execute(
                        text(
                            "INSERT OR IGNORE INTO collection_profiles "
                            "(id, nombre, tipo, descripcion, version_configuracion, "
                            "metas, creado_en) "
                            "VALUES ('coleccionista', 'Coleccionista', 'personal', '', 0, '{}', "
                            "CURRENT_TIMESTAMP)"
                        )
                    )
                    await connection.execute(
                        text(
                            "CREATE TABLE user_collection_perfiles ("
                            "id VARCHAR(32) NOT NULL PRIMARY KEY, "
                            "user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
                            "profile_id VARCHAR(32) NOT NULL REFERENCES collection_profiles(id) "
                            "ON DELETE CASCADE, "
                            "game_id VARCHAR(32) NOT NULL REFERENCES games(ID) ON DELETE CASCADE, "
                            "precio_pagado NUMERIC, agregado_en DATETIME NOT NULL, "
                            "CONSTRAINT uq_coleccion_perfil_juego "
                            "UNIQUE (user_id, profile_id, game_id)"
                            ")"
                        )
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO user_collection_perfiles "
                            "(id, user_id, profile_id, game_id, precio_pagado, agregado_en) "
                            "SELECT id, user_id, profile_id, game_id, precio_pagado, agregado_en "
                            "FROM user_collection"
                        )
                    )
                    await connection.execute(text("DROP TABLE user_collection"))
                    await connection.execute(
                        text("ALTER TABLE user_collection_perfiles RENAME TO user_collection")
                    )
                    break


async def dispose_db() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
