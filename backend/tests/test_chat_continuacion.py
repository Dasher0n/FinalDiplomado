"""Continuación de la pregunta pendiente y texto del narrador sin markdown."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ChatSession
from app.services import chat as chat_service
from tests.auth import iniciar_sesion
from tests.test_chat_alias import _alias, _post, _preparar_alias
from tests.test_chat_resolucion_nombres import SETI_ID, entorno  # noqa: F401

NOMBRE_SETI = "SETI: Search for Extraterrestrial Intelligence"


def _planner_de_compra(monkeypatch: pytest.MonkeyPatch) -> None:
    """El planner simulado pide evaluar_compra con el nombre extraído del mensaje."""

    async def planner(_settings: Any, mensaje: str, *_args: Any) -> chat_service.PlanLlm | None:
        nombre = chat_service._extraer_nombre_juego(mensaje)
        if nombre is None or "compra" not in mensaje:
            return None
        paso = chat_service.PasoPlan(id="1", tool="evaluar_compra", args={"nombre": nombre})
        return chat_service.PlanLlm(intent="evaluar_compra", steps=[paso])

    monkeypatch.setattr(chat_service, "_plan_llm", planner)


def _pendiente(sessionmaker: Any, session_id: str) -> str | None:
    async def leer() -> str | None:
        async with sessionmaker() as session:
            chat = await session.scalar(select(ChatSession).where(ChatSession.id == session_id))
            return chat.intent_pendiente if chat else None

    return asyncio.run(leer())


def test_nombre_en_ingles_tras_la_confirmacion_continua_la_evaluacion_y_guarda_el_alias(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    espias, identificaciones = _preparar_alias(monkeypatch, [])
    _planner_de_compra(monkeypatch)
    espias.tools.clear()
    primera = client.post(
        "/api/v1/chat",
        headers=iniciar_sesion(client, "cafe"),
        json={"mensaje": "Buscadores de señales seria buena compra?"},
    ).json()
    assert primera["tarjetas"][0]["datos"]["estado"] == "no_encontrado"
    assert _pendiente(sessionmaker, primera["session_id"]) == "evaluar_compra"
    espias.tools.clear()

    segunda = _post(client, NOMBRE_SETI, "cafe", session_id=primera["session_id"])

    assert segunda["intent"] == "evaluar_compra"
    assert segunda["tarjetas"][0]["datos"]["juego"]["id"] == SETI_ID
    assert "veredicto" in segunda["tarjetas"][0]["datos"]
    assert [tool for tool, _ in espias.tools] == ["evaluar_compra"]
    alias = {a.alias_normalizado: a for a in _alias(sessionmaker)}["buscadores de senales"]
    assert (alias.game_id, alias.origen, alias.profile_id) == (SETI_ID, "ingles", "cafe")
    assert _pendiente(sessionmaker, primera["session_id"]) is None
    identificaciones.clear()

    directa = _post(client, "Buscadores de señales seria buena compra?", "cafe")

    assert identificaciones == []
    assert directa["tarjetas"][0]["datos"]["juego"]["id"] == SETI_ID
    assert "Interpreté «Buscadores de señales» como" in directa["answer"]
    assert "lo confirmaste" not in directa["answer"]


def test_pulsar_un_boton_sigue_guardando_el_alias_como_candidato(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _preparar_alias(monkeypatch, [NOMBRE_SETI])
    _planner_de_compra(monkeypatch)
    primera = _post(client, "Escuchadores de ondas seria buena compra?", "cafe")
    assert [c["id"] for c in primera["candidatos"]] == [SETI_ID]
    # Los IDs viven en los datos de los botones, no en el texto visible.
    assert SETI_ID not in primera["answer"]

    confirmada = _post(
        client, NOMBRE_SETI, "cafe", game_id=SETI_ID, session_id=primera["session_id"]
    )

    assert confirmada["tarjetas"][0]["datos"]["juego"]["id"] == SETI_ID
    alias = {a.alias_normalizado: a for a in _alias(sessionmaker)}["escuchadores de ondas"]
    assert (alias.game_id, alias.origen) == (SETI_ID, "candidato")


def test_una_pregunta_distinta_descarta_la_pendiente(
    entorno: tuple[TestClient, Any],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, sessionmaker = entorno
    _preparar_alias(monkeypatch, [])
    _planner_de_compra(monkeypatch)
    primera = _post(client, "Vigilantes del cielo seria buena compra?", "cafe")
    assert _pendiente(sessionmaker, primera["session_id"]) == "evaluar_compra"

    otra = _post(client, "¿Qué me falta?", "cafe", session_id=primera["session_id"])
    assert otra["intent"] == "que_me_falta"
    assert _pendiente(sessionmaker, primera["session_id"]) is None

    nombre = _post(client, NOMBRE_SETI, "cafe", session_id=primera["session_id"])

    assert nombre["intent"] == "detalle_juego"
    assert "vigilantes del cielo" not in {a.alias_normalizado for a in _alias(sessionmaker)}


@pytest.mark.parametrize(
    ("mensaje", "esperado"),
    [
        ("Wandering Towers", "Wandering Towers"),
        ("  Catan  ", "Catan"),
        ("Wandering Towers sería buena compra", None),
        ("¿Wandering Towers?", None),
        ("háblame de Catan", None),
        ("¿qué me falta", None),
        ("", None),
    ],
)
def test_solo_nombre_distingue_un_nombre_de_otra_intencion(
    mensaje: str, esperado: str | None
) -> None:
    assert chat_service._solo_nombre(mensaje) == esperado


SETI_NARRADOR = (
    "- **Huecos que cubre**: *Duración: más de 120 minutos*, *Peso: pesado*  \n"
    "- **Ya cubiertos**: *Interacción: directa*, *Jugadores: 2*, *Jugadores: 3 a 4*  \n"
    "- **Juego más parecido**: *King of Tokyo* \u2014 Similitud **33%**, "
    "Qué tan parecido: *distinto*"
)
TORRES_NARRADOR = (
    "- **Huecos que cubre**: *Peso: medio*\n"
    "- **Juego más parecido**: *Cartographers* \u2013 Similitud **45%** \u2013 "
    "Qué tan parecido: *parecido*\n"
    "Aporta algo distinto \u2014 sin __repetir__ la colección."
)


@pytest.mark.parametrize("texto", [SETI_NARRADOR, TORRES_NARRADOR])
def test_el_sanitizador_del_narrador_no_deja_markdown_ni_guiones_largos(texto: str) -> None:
    limpio = chat_service._sanear_narrador(texto)

    assert not any(simbolo in limpio for simbolo in ("*", "__", "\u2014", "\u2013"))


def test_el_sanitizador_reemplaza_los_guiones_por_comas() -> None:
    assert chat_service._sanear_narrador("Cartographers \u2013 Similitud 45%") == (
        "Cartographers, Similitud 45%"
    )
    assert (
        chat_service._sanear_narrador("uno\u2014dos y tres\u2014cuatro") == "uno,dos y tres,cuatro"
    )
    assert chat_service._sanear_narrador("**Jugadores: 2**, *Jugadores: 3 a 4*") == (
        "Jugadores: 2, Jugadores: 3 a 4"
    )


def test_solo_el_encabezado_determinista_lleva_negritas() -> None:
    resultado = {
        "estado": "encontrado",
        "veredicto": "aporta",
        "juego": {"nombre": "SETI"},
        "faltantes_que_cubre": ["Peso: pesado"],
    }
    texto = chat_service._con_encabezado(
        chat_service._sanear_narrador("**Cubre** el hueco *Peso: pesado*."),
        "evaluar_compra",
        [resultado],
    )

    assert texto.startswith("**SETI** aporta a tu colección.")
    assert texto.count("**") == 2 and "*Peso" not in texto
