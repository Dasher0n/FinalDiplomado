"""Logging estructurado minimo sin filtrar configuracion sensible."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
    "message",
    "asctime",
}


class SafeExtraLogger(logging.Logger):
    """Evita que claves de negocio reservadas rompan el registro de errores."""

    def makeRecord(  # noqa: N802
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: object,
        args: Any,
        exc_info: Any,
        func: str | None = None,
        extra: Mapping[str, object] | None = None,
        sinfo: str | None = None,
    ) -> logging.LogRecord:
        if extra:
            extra = {
                (f"ctx_{key}" if key in _RESERVED else key): value for key, value in extra.items()
            }
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)


logging.setLoggerClass(SafeExtraLogger)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except TypeError, ValueError:
                    payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if json_output
        else logging.Formatter("%(levelname)-8s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
