"""Siembra idempotente del catalogo, usuario demo y su coleccion."""

from __future__ import annotations

import asyncio
import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.models import CollectionProfile, Game, User, UserCollection
from app.db.session import dispose_db, get_sessionmaker, init_db
from app.profiles import (
    CAFE_GAME_IDS,
    CONFIGURACION_PERFILES_VERSION,
    MIGUEL_GAME_IDS,
    PERFILES,
)

DEMO_GAMES = (
    "Wingspan",
    "Brass: Birmingham",
    "Gloomhaven",
    "Codenames",
    "Catan",
    "Azul",
    "Terraforming Mars",
    "Pandemic",
    "7 Wonders Duel",
    "Cascadia",
    "Spirit Island",
    "Root",
)

_JSON_COLUMNS = {
    "best_players",
    "rec_players",
    "mechanics",
    "categories",
    "subdomains",
    "product_line",
    "reimplements",
    "reimplemented_by",
    "designers",
    "interaccion_motivos",
    "familias_mec",
    "familias_tema",
    "nivel_jugadores",
}
_FLOAT_COLUMNS = {
    "min_players",
    "max_players",
    "min_playtime",
    "max_playtime",
    "min_age",
    "community_age",
    "weight",
    "num_weights",
    "Rank",
    "Average",
    "Users rated",
    "min_playtime_log",
    "max_playtime_log",
    "players_lo",
    "players_hi",
    "n_ofertas_us_stock",
}
_INT_COLUMNS = {"year", "players_votes", "interaccion"}
_BOOL_COLUMNS = {
    "jugadores_imputados",
    "weight_imputado",
    "duracion_imputada",
    "weight_pocos_votos",
    "cooperativo",
    "precio_confiable",
    "tiene_mecanicas",
    "tiene_categorias",
}


def value_or_none(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def parse_json(value: str | None) -> list[Any] | None:
    raw = value_or_none(value)
    return json.loads(raw) if raw else None


def parse_float(value: str | None) -> float | None:
    raw = value_or_none(value)
    return float(raw) if raw else None


def parse_int(value: str | None) -> int | None:
    raw = value_or_none(value)
    return int(float(raw)) if raw else None


def parse_bool(value: str | None) -> bool:
    return value_or_none(value) == "True"


def parse_decimal(value: str | None) -> Decimal | None:
    raw = value_or_none(value)
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"Precio invalido en catalogo: {raw}") from exc


def parse_datetime(value: str | None) -> datetime | None:
    raw = value_or_none(value)
    return datetime.fromisoformat(raw) if raw else None


def game_values(row: dict[str, str], fila_vector: int) -> dict[str, Any]:
    """Convierte una fila CSV sin usar nunca las columnas residuales de precio."""
    values: dict[str, Any] = {
        "id": row["ID"],
        "nombre": row["Name"],
        "fila_vector": fila_vector,
        "origen": "bgg_ranking" if value_or_none(row["Rank"]) else "bgg_sin_rank",
        "confianza": "alta",
        "fuentes": [],
        "evidencia": [],
        "image_url": value_or_none(row["image_url"]),
        "thumbnail": value_or_none(row["Thumbnail"]),
        "nivel_duracion": value_or_none(row["nivel_duracion"]),
        "nivel_peso": value_or_none(row["nivel_peso"]),
        "nivel_interaccion": value_or_none(row["nivel_interaccion"]),
        "fecha_precio": parse_datetime(row["fecha_precio"]),
        "precio_usd": parse_decimal(row["precio_usd"]),
        "bgp_url": value_or_none(row["bgp_url"]),
    }
    for column in _JSON_COLUMNS:
        values[column] = parse_json(row[column])
    for column in _FLOAT_COLUMNS:
        attribute = {"Rank": "rank", "Average": "average", "Users rated": "users_rated"}.get(
            column, column
        )
        values[attribute] = parse_float(row[column])
    for column in _INT_COLUMNS:
        values[column] = parse_int(row[column])
    for column in _BOOL_COLUMNS:
        values[column] = parse_bool(row[column])
    return values


async def seed_catalog(session: AsyncSession, catalog_path: Path) -> int:
    if not await asyncio.to_thread(catalog_path.is_file):
        raise FileNotFoundError(f"No existe el catalogo: {catalog_path}")
    existing_ids = set((await session.scalars(select(Game.id))).all())
    pending: list[Game] = []
    inserted = 0
    with catalog_path.open(encoding="utf-8", newline="") as file:
        for fila_vector, row in enumerate(csv.DictReader(file)):
            if row["ID"] in existing_ids:
                continue
            pending.append(Game(**game_values(row, fila_vector)))
            if len(pending) == 500:
                session.add_all(pending)
                await session.flush()
                inserted += len(pending)
                pending.clear()
        if pending:
            session.add_all(pending)
            await session.flush()
            inserted += len(pending)
    return inserted


async def seed_demo_user_and_collection(session: AsyncSession) -> tuple[bool, int]:
    email = settings.demo_user_email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    created_user = user is None
    if user is None:
        user = User(email=email, nombre="Usuario demo")
        session.add(user)
        await session.flush()

    perfiles = {perfil["id"]: perfil for perfil in PERFILES}
    existentes = {
        perfil.id: perfil
        for perfil in (
            await session.scalars(
                select(CollectionProfile).where(CollectionProfile.id.in_(perfiles))
            )
        ).all()
    }
    for profile_id, perfil in perfiles.items():
        if profile_id not in existentes:
            session.add(
                CollectionProfile(
                    id=profile_id,
                    nombre=perfil["nombre"],
                    tipo=perfil["tipo"],
                    descripcion=perfil["descripcion"],
                    version_configuracion=CONFIGURACION_PERFILES_VERSION,
                    metas=perfil["metas"],
                )
            )
        elif existentes[profile_id].version_configuracion < CONFIGURACION_PERFILES_VERSION:
            existente = existentes[profile_id]
            existente.nombre = cast(str, perfil["nombre"])
            existente.tipo = cast(str, perfil["tipo"])
            existente.descripcion = cast(str, perfil["descripcion"])
            existente.version_configuracion = CONFIGURACION_PERFILES_VERSION
            existente.metas = cast(dict[str, Any], perfil["metas"])
    await session.flush()

    additions: list[UserCollection] = []
    for profile_id, ids in (
        ("coleccionista", None),
        ("cafe", CAFE_GAME_IDS),
        ("miguel", MIGUEL_GAME_IDS),
    ):
        games = await session.scalars(
            select(Game.id).where(Game.nombre.in_(DEMO_GAMES) if ids is None else Game.id.in_(ids))
        )
        game_ids = set(games.all())
        collection_ids = set(
            (
                await session.scalars(
                    select(UserCollection.game_id).where(
                        UserCollection.user_id == user.id, UserCollection.profile_id == profile_id
                    )
                )
            ).all()
        )
        additions.extend(
            UserCollection(user_id=user.id, profile_id=profile_id, game_id=game_id)
            for game_id in game_ids - collection_ids
        )
    session.add_all(additions)
    await session.flush()
    return created_user, len(additions)


async def seed_database(
    session: AsyncSession, artefactos_dir: Path | None = None
) -> dict[str, int]:
    directory = artefactos_dir or settings.artefactos_dir
    games = await seed_catalog(session, directory / "catalogo.csv")
    user_created, collection = await seed_demo_user_and_collection(session)
    return {"games": games, "users": int(user_created), "collection": collection}


async def main() -> int:
    setup_logging("INFO")
    await init_db()
    async with get_sessionmaker()() as session:
        result = await seed_database(session)
        await session.commit()
    await dispose_db()
    print("Siembra completada.")
    print(f"  Juegos nuevos: {result['games']}")
    print(f"  Usuario demo nuevo: {result['users']}")
    print(f"  Juegos agregados a la coleccion demo: {result['collection']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
