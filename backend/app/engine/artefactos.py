"""Carga local de los artefactos inmutables del motor."""

from __future__ import annotations

import csv
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, load_npz  # type: ignore[import-untyped]


@dataclass(frozen=True)
class ArtefactosMotor:
    """Matrices alineadas con ``Game.fila_vector`` y metadatos del pickle."""

    mecanicas: csr_matrix
    tematica: csr_matrix
    ocasion: np.ndarray[Any, Any]
    interaccion: np.ndarray[Any, Any]
    pesos: dict[str, float]
    umbral_parecido: float
    umbral_redundante: float
    tipos: dict[str, tuple[str, ...]]

    @classmethod
    def cargar(cls, directorio: Path) -> ArtefactosMotor:
        with (directorio / "preproceso.pkl").open("rb") as archivo:
            preproceso: dict[str, Any] = pickle.load(archivo)

        tipos: dict[str, list[str]] = {}
        with (directorio / "tipos_experiencia.csv").open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                tipos.setdefault(fila["eje"], []).append(fila["nivel"])

        return cls(
            mecanicas=load_npz(directorio / "X_mecanicas.npz").tocsr(),
            tematica=load_npz(directorio / "X_tematica.npz").tocsr(),
            ocasion=np.load(directorio / "X_ocasion.npy"),
            interaccion=np.load(directorio / "X_interaccion.npy"),
            pesos={clave: float(valor) for clave, valor in preproceso["pesos"].items()},
            umbral_parecido=float(preproceso["umbral_parecido"]),
            umbral_redundante=float(preproceso["umbral_redundante"]),
            tipos={eje: tuple(niveles) for eje, niveles in tipos.items()},
        )
