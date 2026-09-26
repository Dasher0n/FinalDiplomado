"""Lista la coleccion demo desde SQLite sin modificar la base."""

from __future__ import annotations

import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
BASE_DATOS = RAIZ / "backend" / "data" / "sommelier.db"


def main() -> int:
    uri = f"{BASE_DATOS.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conexion:
        filas = conexion.execute(
            """
            SELECT games.ID, games.Name, games.year
            FROM games
            JOIN user_collection ON user_collection.game_id = games.ID
            JOIN users ON users.id = user_collection.user_id
            WHERE users.email = ?
            ORDER BY games.Name
            """,
            ("demo@sommelier.local",),
        ).fetchall()

    for game_id, nombre, year in filas:
        print(f"{game_id}\t{nombre}\t{year}")
    return 0 if len(filas) == 12 else 1


if __name__ == "__main__":
    raise SystemExit(main())
