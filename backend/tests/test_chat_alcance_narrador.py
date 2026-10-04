"""Vista del crítico, alcance del narrador, plantilla legible y orden de candidatos."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services import chat as chat_service

CASOS = json.loads((Path(__file__).parent / "fixtures" / "narrador_entrada_casos.json").read_text())

NARRACION_SETI = (
    "- Cubre los huecos Duración: más de 120 minutos y Peso: pesado.\n"
    "- Ya estaban cubiertos Interacción: directa y Jugadores: 2.\n"
    "- Se parece más a King of Tokyo, con 33% de similitud (distinto)."
)
AVISO = "Entiendo mejor los nombres en inglés; si tu juego no aparece, escríbelo en inglés."


def _compuesta(narracion: str, caso: str) -> str:
    resultados = [CASOS[caso]]
    texto = chat_service._con_encabezado(narracion, "evaluar_compra", resultados)
    return chat_service._presentar_respuesta(
        chat_service._con_sugerencia_final(texto, "evaluar_compra", resultados),
        "evaluar_compra",
        resultados,
    )


def test_critico_llm_recibe_la_vista_formateada_y_la_fuente_de_verdad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamada: dict[str, Any] = {}

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            llamada.update(kwargs)
            return SimpleNamespace(
                output_parsed=chat_service._CriticaRespuestaLlm(ok=True, hallazgos=[])
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)

    asyncio.run(chat_service._criticar_llm(settings, "Se parece 52%", [CASOS["caso6"]], "¿y ese?"))

    sistema, usuario = llamada["input"][0]["content"], llamada["input"][1]["content"]
    assert "fuente de verdad" in sistema and "repetirlos no es una cifra sin fuente" in sistema
    assert "Huecos que cubre" in sistema
    assert '"Total": "52%"' in usuario and "0.5243" not in usuario
    assert "Qué tan parecido" in usuario and "Ya cubiertos" in usuario
    assert "precio_texto" not in usuario


@pytest.mark.parametrize(
    "frase",
    [
        "**Veredicto: sí** y cubre Peso: pesado.",
        "- Propongo comprarlo porque cubre Peso: pesado.",
        "- Te recomiendo este juego.",
        "- Sí vale la pena para tu colección.",
    ],
)
def test_critico_determinista_rechaza_veredicto_y_recomendacion_del_narrador(frase: str) -> None:
    resultados = [CASOS["caso4"]]
    respuesta = _compuesta(NARRACION_SETI + "\n" + frase, "caso4")

    hallazgos = chat_service._criticar_determinista(respuesta, resultados)

    assert any("veredictos ni recomendaciones" in h for h in hallazgos)


@pytest.mark.parametrize("caso", ["caso4", "caso6"])
def test_encabezado_del_backend_y_narracion_en_las_formas_permitidas_pasan(caso: str) -> None:
    resultados = [CASOS[caso]]
    narracion = (
        NARRACION_SETI
        if caso == "caso4"
        else "- Cubre el hueco Duración: 61 a 120 minutos.\n"
        "- Se parece más a Bohnanza, con 52% (parecido)."
    )

    respuesta = _compuesta(narracion, caso)

    assert chat_service._criticar_determinista(respuesta, resultados) == []
    assert respuesta.splitlines()[0].startswith("🔁 **") or "aporta" in respuesta.splitlines()[0]


@pytest.mark.parametrize("caso", ["caso4", "caso6"])
def test_plantilla_de_respaldo_es_legible_y_pasa_el_critico(caso: str) -> None:
    resultados = [CASOS[caso]]
    plantilla = chat_service._narrar("evaluar_compra", resultados)
    cuerpo = plantilla.split("\n\n", 1)[1]

    oraciones = [o for o in cuerpo.replace("**", "").split(". ") if o.strip()]
    respuesta = chat_service._presentar_respuesta(
        chat_service._con_sugerencia_final(plantilla, "evaluar_compra", resultados),
        "evaluar_compra",
        resultados,
    )

    assert 1 <= len(oraciones) <= 2
    assert "{" not in plantilla and "[" not in plantilla and "_" not in plantilla
    assert chat_service._criticar_determinista(respuesta, resultados) == []


def test_plantilla_para_seti_y_catan_con_los_campos_reales() -> None:
    seti = chat_service._narrar("evaluar_compra", [CASOS["caso4"]])
    catan = chat_service._narrar("evaluar_compra", [CASOS["caso6"]])

    assert seti.startswith("**SETI: Search for Extraterrestrial Intelligence** aporta a tu")
    assert "Cubre huecos de tu colección: Duración: más de 120 minutos y Peso: pesado." in seti
    assert (
        "El más parecido de tu colección es **King of Tokyo**, con 33% de similitud (distinto)."
        in seti
    )
    assert "Cubre huecos de tu colección: Duración: 61 a 120 minutos, y refuerza" in catan
    assert "con 52% de similitud (parecido)." in catan
    # La tarjeta ya muestra lo que estaba cubierto: la plantilla no lo enumera.
    assert "Ya tenías" not in seti and "Ya tenías" not in catan


def test_textos_deterministas_de_confirmacion_y_no_encontrado_avisan_del_ingles() -> None:
    ambiguo = chat_service._narrar("evaluar_compra", [{"estado": "ambiguo", "candidatos": []}])
    ausente = chat_service._narrar("evaluar_compra", [{"estado": "no_encontrado"}])

    assert ambiguo.startswith("**¿Te refieres a…?**") and AVISO in ambiguo
    assert ausente.startswith("**No encontré ese juego**") and AVISO in ausente


@pytest.mark.asyncio
async def test_candidatos_con_las_listas_reales_de_a1_ponen_primero_la_exacta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    juegos = [
        SimpleNamespace(id="236820", nombre="Mazing", users_rated=900),
        SimpleNamespace(id="234190", nombre="Unstable Unicorns", users_rated=30000),
        SimpleNamespace(id="400366", nombre="Wondrous Creatures", users_rated=7342),
        SimpleNamespace(id="119890", nombre="Agricola: All Creatures", users_rated=9000),
        SimpleNamespace(id="1", nombre="Wingspan", users_rated=60000),
    ]

    class Catalogo:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=[
                        "Wonderful Creatures",
                        "Marvelous Creatures",
                        "Amazing Creatures",
                        "Wondrous Creatures",
                        "Fantastic Creatures",
                    ],
                    identificaciones=["Fantastic Creatures", "Unstable Unicorns", "Wingspan"],
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, candidatos, *_ = await chat_service._resolver_con_traduccion(
        Catalogo(),
        "Criaturas maravillosas",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    ids = [juego.id for juego in candidatos]
    assert estado == "ambiguo"
    assert ids[0] == "400366" and len(ids) <= 3 and len(set(ids)) == len(ids)
    assert "119890" not in ids


MODERN_ART = {
    "estado": "encontrado",
    "veredicto": "parecido_pero_cubre_hueco",
    "juego": {"nombre": "Modern Art"},
    "juego_mas_parecido": {"nombre": "Cartographers"},
    "similitud": {"total": 0.62},
    "similitud_etiqueta": "parecido",
    "faltantes_que_cubre": [],
    "debiles_que_refuerza": ["Mecánicas: Subastas y pujas"],
    "ya_cubiertos": ["Jugadores: 3 a 4"],
}


@pytest.mark.parametrize(
    ("faltantes", "debiles", "esperado"),
    [
        ([], ["Mecánicas: Subastas y pujas"], "pero refuerza tu colección."),
        (["Peso: pesado"], [], "pero cubre huecos."),
        (["Peso: pesado"], ["Mecánicas: Subastas y pujas"], "pero cubre huecos."),
        ([], [], "pero aporta algo a tu colección."),
    ],
)
def test_encabezado_parecido_pero_coincide_con_las_listas(
    faltantes: list[str], debiles: list[str], esperado: str
) -> None:
    resultado = {
        **MODERN_ART,
        "faltantes_que_cubre": faltantes,
        "debiles_que_refuerza": debiles,
    }

    encabezado = chat_service._encabezado_evaluacion(resultado)

    assert encabezado == f"**Modern Art** se parece a un juego tuyo, {esperado}"


def test_plantilla_de_modern_art_no_dice_que_cubre_huecos() -> None:
    plantilla = chat_service._narrar("evaluar_compra", [MODERN_ART])

    assert "pero refuerza tu colección" in plantilla and "pero cubre huecos" not in plantilla
    assert "Cubre huecos" not in plantilla
    assert "Refuerza niveles que tenías débiles: Mecánicas: Subastas y pujas." in plantilla


@pytest.mark.parametrize(
    ("veredicto", "faltantes", "debiles", "esperado"),
    [
        ("aporta", ["Peso: pesado"], [], "aporta a tu colección."),
        ("aporta", [], ["Peso: medio"], "aporta a tu colección."),
        ("aporta", [], [], "es distinto de lo que ya tienes."),
        ("parecido", [], [], "se parece a lo que ya tienes."),
        ("redundante", [], [], "es redundante con tu colección."),
    ],
)
def test_encabezado_de_cada_veredicto_coincide_con_las_listas(
    veredicto: str, faltantes: list[str], debiles: list[str], esperado: str
) -> None:
    resultado = {
        **MODERN_ART,
        "veredicto": veredicto,
        "faltantes_que_cubre": faltantes,
        "debiles_que_refuerza": debiles,
    }

    assert chat_service._encabezado_evaluacion(resultado) == f"**Modern Art** {esperado}"
