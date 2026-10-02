"""Aislamiento de configuracion y red para la suite."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/opencode/sommelier-test.db")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_ENABLED", "false")


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host in {"127.0.0.1", "::1", "localhost"}:
            return original_connect(self, address, *args, **kwargs)
        raise RuntimeError(f"Una prueba intento acceder a la red: {host}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def api_client() -> Generator[TestClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            await seed_database(session, Path(__file__).parent / "fixtures")
            await session.commit()

    async def sesion_de_prueba() -> AsyncGenerator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    async def cerrar() -> None:
        await engine.dispose()

    asyncio.run(preparar())
    app = create_app()
    app.dependency_overrides[get_session] = sesion_de_prueba
    with TestClient(app) as client:
        yield client
    asyncio.run(cerrar())
