"""Dependencias compartidas de la API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User
from app.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(session: DbSession) -> User:
    """Resuelve el usuario demo hasta que la Fase 2 introduzca autenticacion."""
    user = await session.scalar(select(User).where(User.email == settings.demo_user_email.lower()))
    if user is None:
        raise RuntimeError("El usuario demo no existe. Ejecuta la siembra inicial.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
