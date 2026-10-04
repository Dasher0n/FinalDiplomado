"""Router agregado de la API v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import exigir_sesion
from app.api.v1.auth import router as auth_router
from app.api.v1.catalogo import router as catalogo_router
from app.api.v1.chat import router as chat_router
from app.api.v1.engine import router as engine_router
from app.api.v1.meta import router as meta_router
from app.api.v1.perfiles import router as perfiles_router

api_router = APIRouter()
# Públicos: health y login. Todo lo demás exige un token válido.
api_router.include_router(meta_router)
api_router.include_router(auth_router)
protegidos = [Depends(exigir_sesion)]
api_router.include_router(perfiles_router, dependencies=protegidos)
api_router.include_router(catalogo_router, dependencies=protegidos)
api_router.include_router(engine_router, dependencies=protegidos)
api_router.include_router(chat_router, dependencies=protegidos)
