"""Entrada del narrador sin ambigüedad: precio fuera, similitud etiquetada y niveles explícitos.

Los resultados de tools vienen de los casos 4 (SETI) y 6 (Catan frente a Bohnanza) de la
verificación real, saneados, con los campos derivados que agrega el backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services import chat as chat_service

CASOS = json.loads((Path(__file__).parent / "fixtures" / "narrador_entrada_casos.json").read_text())

NARRACION_SETI = (
    "**SETI aporta a la colección**\n\n"
    "- La similitud con King of Tokyo es 33%, etiqueta distinto.\n"
    "- Cubre Duración: más de 120 minutos y Peso: pesado, que son huecos de tu colección."
)
NARRACION_CATAN = (
    "**Catan es parecido a Bohnanza**\n\n"
    "- La similitud total es 52%, etiqueta parecido.\n"
    "- Cubre Duración: 61 a 120 minutos, un hueco de tu colección."
)


def _vista_critica(narracion: str, resultados: list[dict[str, Any]]) -> str:
    """Lo que ve el crítico: la narración presentada, sin la línea de precio del backend."""
    return chat_service._presentar_respuesta(
        chat_service._con_sugerencia_final(narracion, "evaluar_compra", resultados),
        "evaluar_compra",
        resultados,
    )


@pytest.mark.parametrize(
    ("caso", "narracion"), [("caso4", NARRACION_SETI), ("caso6", NARRACION_CATAN)]
)
def test_narracion_con_campos_formateados_pasa_el_critico_determinista(
    caso: str, narracion: str
) -> None:
    resultados = [CASOS[caso]]

    respuesta = _vista_critica(narracion, resultados)

    assert chat_service._criticar_determinista(respuesta, resultados) == []


@pytest.mark.parametrize(
    ("caso", "narracion", "calificativo"),
    [
        ("caso4", NARRACION_SETI.replace("etiqueta distinto", "es redundante"), "redundante"),
        ("caso6", NARRACION_CATAN.replace("52%", "92%"), "92%"),
        ("caso6", NARRACION_CATAN + "\n- Cuesta 50 USD en tiendas.", "USD"),
        ("caso4", NARRACION_SETI + "\n- Cuesta $79.99 hoy.", "$"),
    ],
)
def test_critico_determinista_rechaza_calificativo_propio_o_precio(
    caso: str, narracion: str, calificativo: str
) -> None:
    resultados = [CASOS[caso]]

    hallazgos = chat_service._criticar_determinista(
        _vista_critica(narracion, resultados), resultados
    )

    assert hallazgos, calificativo


def test_precio_sale_del_narrador_y_lo_agrega_el_backend() -> None:
    resultados = [CASOS["caso4"]]

    copia = json.dumps(chat_service._formatear_resultados_narrador(resultados))
    respuesta = chat_service._agregar_precio(_vista_critica(NARRACION_SETI, resultados), resultados)

    assert "79.99" not in copia and "precio" not in copia
    assert "Precio de referencia: USD 79.99 (BoardGamePrices, 24 sep 2026)." in respuesta
    sin_precio = [{**CASOS["caso4"], "precio_texto": "sin precio confiable"}]
    assert "Precio de referencia: sin precio confiable." in chat_service._agregar_precio(
        _vista_critica(NARRACION_SETI, sin_precio), sin_precio
    )
    assert respuesta.index("Precio de referencia") < respuesta.index("💡")


def test_similitud_llega_como_porcentaje_con_etiqueta() -> None:
    copia = chat_service._formatear_resultados_narrador([CASOS["caso6"]])[0]

    assert copia["similitud"]["total"] == "52%"
    assert copia["similitud_etiqueta"] == "parecido"
    assert copia["faltantes_que_cubre"] == ["Duración: 61 a 120 minutos"]
    assert "niveles_que_cubre" not in copia


@pytest.mark.parametrize(
    ("total", "veredicto", "esperada"),
    [
        (0.80, "redundante", "redundante"),
        (0.80, "parecido_pero_cubre_hueco", "muy parecido"),
        (0.7729157377558937, "redundante", "redundante"),
        (0.50, "parecido", "parecido"),
        (0.4165141436034246, "parecido", "parecido"),
        (0.33, "aporta", "distinto"),
    ],
)
def test_etiqueta_de_similitud_usa_los_umbrales_del_motor(
    total: float, veredicto: str, esperada: str
) -> None:
    etiqueta = chat_service._etiqueta_similitud(
        total, veredicto, 0.7729157377558937, 0.4165141436034246
    )

    assert etiqueta == esperada


def test_prompt_del_narrador_prohibe_precio_y_limita_la_similitud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from types import SimpleNamespace

    import openai
    from pydantic import SecretStr

    from app.core.config import Settings

    llamada: dict[str, Any] = {}

    class Responses:
        async def create(self, **kwargs: Any) -> Any:
            llamada.update(kwargs)
            return SimpleNamespace(output_text="ok")

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)

    asyncio.run(chat_service._narrar_llm(settings, [CASOS["caso4"]], "¿Vale la pena SETI?"))

    sistema = llamada["input"][0]["content"]
    assert "ni precio ni presupuesto" in sistema
    assert "Qué tan parecido" in sistema and "sin calificativos propios" in sistema
    assert "Huecos que cubre" in sistema
    assert "una sola oración" in sistema and "Experiencia del juego" in sistema
    assert "Sin números, sin veredicto" in sistema
    assert "No menciones la duración ni el número de jugadores" in sistema
    usuario = llamada["input"][1]["content"]
    assert "79.99" not in usuario and "33%" in usuario
