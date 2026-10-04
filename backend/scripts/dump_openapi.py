"""Vuelca OpenAPI sin levantar un servidor HTTP."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"OpenAPI escrito en {target} ({len(schema.get('paths', {}))} rutas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
