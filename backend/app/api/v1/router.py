"""Router agregado de la API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.meta import router as meta_router

api_router = APIRouter()
api_router.include_router(meta_router)
