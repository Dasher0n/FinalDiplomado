"""Aislamiento de configuracion y red para la suite."""

from __future__ import annotations

import os
from typing import Any

import pytest

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
