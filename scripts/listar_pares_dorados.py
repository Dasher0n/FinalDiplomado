"""Lista las ediciones del catalogo usadas por los pares dorados del motor."""

from __future__ import annotations

import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
BASE_DATOS = RAIZ / "backend" / "data" / "sommelier.db"
PARES = (
    ("Brass: Birmingham", "Lancashire"),
    ("Gloomhaven", "Frosthaven"),
    ("7 Wonders", "7 Wonders Duel"),
    ("Pandemic", "Pandemic Legacy: Season 1"),
    ("Wingspan", "Wyrmspan"),
    ("Wingspan", "Earth"),
    ("Twilight Imperium: Fourth Edition", "Codenames"),
    ("Spirit Island", "Twilight Struggle"),
    ("Gloomhaven", "Dixit"),
)


def buscar(conexion: sqlite3.Connection, nombre: str) -> tuple[str, str, int] | None:
    fila = conexion.execute(
        "SELECT ID, Name, year FROM games WHERE Name = ? ORDER BY Rank LIMIT 1", (nombre,)
    ).fetchone()
    if fila is not None:
        return fila
    return conexion.execute(
        "SELECT ID, Name, year FROM games WHERE Name LIKE ? ORDER BY Rank LIMIT 1", (f"%{nombre}%",)
    ).fetchone()


def main() -> int:
    uri = f"{BASE_DATOS.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conexion:
        for izquierda, derecha in PARES:
            for nombre in (izquierda, derecha):
                fila = buscar(conexion, nombre)
                if fila is None:
                    print(f"NO_ENCONTRADO\t{nombre}")
                else:
                    game_id, nombre_exacto, year = fila
                    print(f"{game_id}\t{nombre_exacto}\t{year}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
