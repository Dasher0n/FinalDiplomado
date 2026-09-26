"""Verificaciones locales desechables de la Fase 0."""

from __future__ import annotations

import csv
import importlib.metadata
import pickle
import sys
from argparse import ArgumentParser
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
ARTEFACTOS = RAIZ / "artefactos"
PAQUETES = ("scikit-learn", "scipy", "numpy", "pandas")
PRECIOS_VALIDOS = {
    "precio_usd",
    "n_ofertas_us_stock",
    "precio_confiable",
    "fecha_precio",
    "bgp_url",
}


def buscar_citas(valor: object) -> list[str]:
    """Extrae las URL de las citas sin conservar la respuesta completa."""
    if isinstance(valor, dict):
        citas: list[str] = []
        if valor.get("type") == "url_citation" and isinstance(valor.get("url"), str):
            citas.append(valor["url"])
        for hijo in valor.values():
            citas.extend(buscar_citas(hijo))
        return citas
    if isinstance(valor, list):
        return [cita for hijo in valor for cita in buscar_citas(hijo)]
    return []


def verificar_web_search() -> int:
    """Hace la unica llamada autorizada de la Fase 0, sin reintentos."""
    from openai import OpenAI
    from pydantic import SecretStr
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class AjustesFaseCero(BaseSettings):
        model_config = SettingsConfigDict(env_file=None)

        openai_api_key: SecretStr

    ajustes = AjustesFaseCero()
    cliente = OpenAI(api_key=ajustes.openai_api_key.get_secret_value())
    respuesta = cliente.responses.create(
        model="gpt-5.1",
        input=(
            "Busca en la web el juego de mesa Metropoli de Ideotas Juegos. "
            "Identificalo y menciona datos basicos respaldados por fuentes."
        ),
        tools=[{"type": "web_search"}],
        tool_choice="required",
    )
    citas = sorted(set(buscar_citas(respuesta.model_dump(mode="json"))))
    print(f"web_search_modelo={respuesta.model}")
    print(f"web_search_citas={len(citas)}")
    for cita in citas:
        print(f"web_search_cita={cita}")
    return 0 if citas else 1


def version_instalada(nombre: str) -> str:
    try:
        return importlib.metadata.version(nombre)
    except importlib.metadata.PackageNotFoundError:
        return "no instalada"


def main() -> int:
    argumentos = ArgumentParser()
    argumentos.add_argument("--web-search", action="store_true")
    opciones = argumentos.parse_args()

    if opciones.web_search:
        return verificar_web_search()

    print(f"Python={sys.version.split()[0]}")
    for paquete in PAQUETES:
        print(f"{paquete}={version_instalada(paquete)}")

    with (ARTEFACTOS / "catalogo.csv").open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = set(lector.fieldnames or [])
        muestra = next(lector)
        filas_catalogo = 1
        bgp_tiene_marcador = "TU_USUARIO/FinalDiplomado" in muestra["bgp_url"]
        for fila in lector:
            filas_catalogo += 1
            bgp_tiene_marcador |= "TU_USUARIO/FinalDiplomado" in fila["bgp_url"]
    faltantes = sorted(PRECIOS_VALIDOS - columnas)
    print(f"filas_catalogo={filas_catalogo}")
    print(f"columnas_catalogo={len(columnas)}")
    print(f"nombres_columnas={sorted(columnas)}")
    print(f"columnas_precio_faltantes={faltantes}")
    print(f"image_url_es_itemrep={'__itemrep' in muestra['image_url']}")
    print(f"thumbnail_es_micro={'__micro' in muestra['Thumbnail']}")
    print(f"bgp_url_tiene_marcador={bgp_tiene_marcador}")

    try:
        with (ARTEFACTOS / "preproceso.pkl").open("rb") as archivo:
            preproceso = pickle.load(archivo)
    except ModuleNotFoundError as error:
        print(f"preproceso=no cargado: dependencia ausente ({error.name})")
        return 1

    print(f"preproceso_tipo={type(preproceso).__name__}")
    print(f"preproceso_claves={sorted(preproceso)}")
    for clave in (
        "cols_ocasion",
        "limites_ocasion",
        "pesos",
        "umbral_ofertas_precio",
        "umbral_parecido",
        "umbral_redundante",
    ):
        print(f"preproceso_{clave}={preproceso[clave]!r}")
    niveles_jugadores = {
        nivel: (min(jugadores), max(jugadores))
        for nivel, jugadores in preproceso["niveles_jugadores"].items()
    }
    print(f"preproceso_niveles_jugadores_rangos={niveles_jugadores}")
    print(f"mlb_mecanicas_clases={len(preproceso['mlb_mecanicas'].classes_)}")
    print(f"mlb_tematica_clases={len(preproceso['mlb_tematica'].classes_)}")

    try:
        from scipy import sparse
        import numpy as np

        mecanicas = sparse.load_npz(ARTEFACTOS / "X_mecanicas.npz")
        tematica = sparse.load_npz(ARTEFACTOS / "X_tematica.npz")
        ocasion = np.load(ARTEFACTOS / "X_ocasion.npy")
        interaccion = np.load(ARTEFACTOS / "X_interaccion.npy")
    except ModuleNotFoundError as error:
        print(f"matrices=no cargadas: dependencia ausente ({error.name})")
        return 1

    print(f"X_mecanicas={mecanicas.shape}")
    print(f"X_tematica={tematica.shape}")
    print(f"X_ocasion={ocasion.shape}")
    print(f"X_interaccion={interaccion.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
