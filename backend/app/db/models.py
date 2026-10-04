"""Modelo de datos de la Fase 1 del sommelier de juegos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, created_at_column, pk_column, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = pk_column()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(255))
    creado_en: Mapped[datetime] = created_at_column()


class CollectionProfile(Base):
    __tablename__ = "collection_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(32))
    descripcion: Mapped[str] = mapped_column(Text)
    version_configuracion: Mapped[int] = mapped_column(Integer)
    metas: Mapped[dict[str, Any]] = mapped_column(default=dict)
    creado_en: Mapped[datetime] = created_at_column()


class Game(Base):
    """Catalogo. Conserva todas las columnas utiles de catalogo.csv."""

    __tablename__ = "games"
    __table_args__ = (Index("ix_games_nombre", "Name"), Index("ix_games_origen", "origen"))

    id: Mapped[str] = mapped_column("ID", String(32), primary_key=True)
    nombre: Mapped[str] = mapped_column("Name", String(512), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, default=None)
    min_players: Mapped[float | None] = mapped_column(Float, default=None)
    max_players: Mapped[float | None] = mapped_column(Float, default=None)
    min_playtime: Mapped[float | None] = mapped_column(Float, default=None)
    max_playtime: Mapped[float | None] = mapped_column(Float, default=None)
    min_age: Mapped[float | None] = mapped_column(Float, default=None)
    community_age: Mapped[float | None] = mapped_column(Float, default=None)
    weight: Mapped[float | None] = mapped_column(Float, default=None)
    num_weights: Mapped[float | None] = mapped_column(Float, default=None)
    best_players: Mapped[list[Any] | None] = mapped_column(default=None)
    rec_players: Mapped[list[Any] | None] = mapped_column(default=None)
    players_votes: Mapped[int | None] = mapped_column(Integer, default=None)
    mechanics: Mapped[list[Any] | None] = mapped_column(default=None)
    categories: Mapped[list[Any] | None] = mapped_column(default=None)
    subdomains: Mapped[list[Any] | None] = mapped_column(default=None)
    product_line: Mapped[list[Any] | None] = mapped_column(default=None)
    reimplements: Mapped[list[Any] | None] = mapped_column(default=None)
    reimplemented_by: Mapped[list[Any] | None] = mapped_column(default=None)
    designers: Mapped[list[Any] | None] = mapped_column(default=None)
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    rank: Mapped[float | None] = mapped_column("Rank", Float, default=None)
    average: Mapped[float | None] = mapped_column("Average", Float, default=None)
    users_rated: Mapped[float | None] = mapped_column("Users rated", Float, default=None)
    thumbnail: Mapped[str | None] = mapped_column("Thumbnail", Text, default=None)
    min_playtime_log: Mapped[float | None] = mapped_column(Float, default=None)
    max_playtime_log: Mapped[float | None] = mapped_column(Float, default=None)
    players_lo: Mapped[float | None] = mapped_column(Float, default=None)
    players_hi: Mapped[float | None] = mapped_column(Float, default=None)
    jugadores_imputados: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_imputado: Mapped[bool] = mapped_column(Boolean, default=False)
    duracion_imputada: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_pocos_votos: Mapped[bool] = mapped_column(Boolean, default=False)
    interaccion: Mapped[int | None] = mapped_column(Integer, default=None)
    cooperativo: Mapped[bool] = mapped_column(Boolean, default=False)
    interaccion_motivos: Mapped[list[Any] | None] = mapped_column(default=None)
    familias_mec: Mapped[list[Any] | None] = mapped_column(default=None)
    familias_tema: Mapped[list[Any] | None] = mapped_column(default=None)
    nivel_jugadores: Mapped[list[Any] | None] = mapped_column(default=None)
    nivel_duracion: Mapped[str | None] = mapped_column(String(64), default=None)
    nivel_peso: Mapped[str | None] = mapped_column(String(64), default=None)
    nivel_interaccion: Mapped[str | None] = mapped_column(String(64), default=None)
    fecha_precio: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    precio_usd: Mapped[Decimal | None] = mapped_column(default=None)
    n_ofertas_us_stock: Mapped[float | None] = mapped_column(Float, default=None)
    bgp_url: Mapped[str | None] = mapped_column(Text, default=None)
    precio_confiable: Mapped[bool] = mapped_column(Boolean, default=False)
    tiene_mecanicas: Mapped[bool] = mapped_column(Boolean, default=False)
    tiene_categorias: Mapped[bool] = mapped_column(Boolean, default=False)
    fila_vector: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    origen: Mapped[str] = mapped_column(String(32), default="bgg_ranking")
    confianza: Mapped[str] = mapped_column(String(16), default="alta")
    fuentes: Mapped[list[Any]] = mapped_column(default=list)
    evidencia: Mapped[list[Any]] = mapped_column(default=list)
    creado_en: Mapped[datetime] = created_at_column()


class GameVectorExtra(Base):
    __tablename__ = "game_vectors_extra"
    __table_args__ = (UniqueConstraint("game_id", "bloque", name="uq_vector_extra_bloque"),)

    id: Mapped[str] = pk_column()
    game_id: Mapped[str] = mapped_column(ForeignKey("games.ID", ondelete="CASCADE"), index=True)
    bloque: Mapped[str] = mapped_column(String(32))
    vector: Mapped[list[Any]] = mapped_column(default=list)
    creado_en: Mapped[datetime] = created_at_column()


class GameAlias(Base):
    __tablename__ = "game_aliases"

    id: Mapped[str] = pk_column()
    alias_normalizado: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.ID", ondelete="CASCADE"), index=True)
    origen: Mapped[str] = mapped_column(String(32))
    creado_en: Mapped[datetime] = created_at_column()


class ConfirmedAlias(Base):
    """Alias confirmados por la persona: texto normalizado a game_id, por perfil."""

    __tablename__ = "confirmed_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "profile_id", "alias_normalizado", name="uq_alias_perfil"),
    )

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(String(32), index=True)
    alias_normalizado: Mapped[str] = mapped_column(String(512), index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.ID", ondelete="CASCADE"), index=True)
    origen: Mapped[str] = mapped_column(String(32))
    creado_en: Mapped[datetime] = created_at_column()


class UserCollection(Base):
    __tablename__ = "user_collection"
    __table_args__ = (
        UniqueConstraint("user_id", "profile_id", "game_id", name="uq_coleccion_perfil_juego"),
    )

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("collection_profiles.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[str] = mapped_column(ForeignKey("games.ID", ondelete="CASCADE"), index=True)
    precio_pagado: Mapped[Decimal | None] = mapped_column(default=None)
    agregado_en: Mapped[datetime] = created_at_column()


class UserPrice(Base):
    __tablename__ = "user_prices"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_precio_usuario_juego"),)

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.ID", ondelete="CASCADE"), index=True)
    precio_usd: Mapped[Decimal] = mapped_column()
    capturado_en: Mapped[datetime] = created_at_column()


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    titulo: Mapped[str | None] = mapped_column(String(255), default=None)
    juego_en_foco_id: Mapped[str | None] = mapped_column(String(32), default=None)
    intent_pendiente: Mapped[str | None] = mapped_column(String(32), default=None)
    creado_en: Mapped[datetime] = created_at_column()
    actualizado_en: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    contenido: Mapped[str] = mapped_column(Text)
    agent_run_id: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    creado_en: Mapped[datetime] = created_at_column()


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), default=None
    )
    pregunta: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    plan: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    respuesta_final: Mapped[str | None] = mapped_column(Text, default=None)
    estado: Mapped[str] = mapped_column(String(16), default="running", index=True)
    error_mensaje: Mapped[str | None] = mapped_column(Text, default=None)
    critic_passed: Mapped[bool | None] = mapped_column(Boolean, default=None)
    critic_attempts: Mapped[int] = mapped_column(default=0)
    critic_findings: Mapped[list[Any] | None] = mapped_column(default=None)
    modelo: Mapped[str | None] = mapped_column(String(64), default=None)
    creado_en: Mapped[datetime] = created_at_column()
    terminado_en: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    step_id: Mapped[str | None] = mapped_column(String(64), default=None)
    input_summary: Mapped[str | None] = mapped_column(Text, default=None)
    output: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    estado: Mapped[str] = mapped_column(String(16), default="ok")
    error_mensaje: Mapped[str | None] = mapped_column(Text, default=None)
    creado_en: Mapped[datetime] = created_at_column()


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = pk_column()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), default=None
    )
    step_id: Mapped[str | None] = mapped_column(String(64), default=None)
    tool_name: Mapped[str] = mapped_column(String(64), index=True)
    argumentos: Mapped[dict[str, Any]] = mapped_column(default=dict)
    resultado: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error_codigo: Mapped[str | None] = mapped_column(String(64), default=None)
    error_mensaje: Mapped[str | None] = mapped_column(Text, default=None)
    creado_en: Mapped[datetime] = created_at_column()


class WebSearchCache(Base):
    __tablename__ = "web_search_cache"

    id: Mapped[str] = pk_column()
    consulta_normalizada: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    resultado_crudo: Mapped[str] = mapped_column(Text)
    citas: Mapped[list[Any]] = mapped_column(default=list)
    fecha: Mapped[datetime] = created_at_column()
    modelo_usado: Mapped[str] = mapped_column(String(64))
