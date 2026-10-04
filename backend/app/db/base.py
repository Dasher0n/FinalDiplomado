"""Base declarativa y tipos compartidos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Numeric, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, Decimal: Numeric(18, 4)}


class UTCDateTime(TypeDecorator[datetime]):
    """Normaliza fechas a UTC porque SQLite no conserva la zona horaria."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return uuid.uuid4().hex


def pk_column() -> Any:
    return mapped_column(String(32), primary_key=True, default=new_uuid)


def created_at_column() -> Any:
    return mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
