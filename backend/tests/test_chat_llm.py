"""Pruebas de la capa LLM con fixtures locales y sin acceso de red."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.v1 import chat as chat_api
from app.core.config import Settings
from app.services import chat as chat_service


def _fixture() -> dict[str, Any]:
    return json.loads((Path(__file__).parent / "fixtures" / "llm_chat_saneado.json").read_text())


def test_critic_determinista_rechaza_cifra_fuera_de_las_tools() -> None:
    findings = chat_service._criticar_determinista(
        "La similitud es 99.0.",
        [{"similitud": {"total": 0.7}, "juego": {"nombre": "Wingspan"}}],
    )

    assert findings == ["La cifra 99.0 no aparece en los resultados de las tools."]


@pytest.mark.parametrize(
    ("respuesta", "hallazgo"),
    [
        ("Usa `comparar` para decidir.", "nombres internos entre comillas invertidas"),
        ("Puedo filtrar la colección por precio.", "función que no existe"),
    ],
)
def test_critic_determinista_rechaza_funciones_no_expuestas(respuesta: str, hallazgo: str) -> None:
    findings = chat_service._criticar_determinista(respuesta, [])

    assert any(hallazgo in finding for finding in findings)


def test_critic_determinista_rechaza_identificadores_internos() -> None:
    findings = chat_service._criticar_determinista("Aplica regla_exacta.", [])

    assert any("guion bajo" in finding for finding in findings)


@pytest.mark.parametrize(
    "valor",
    [
        None,
        42,
        "",
        "  ",
        "\" ¿?¡!.,: ' ",
        "null",
        "None",
        "nil",
        "undefined",
        "n/a",
        "na",
        "desconocido",
        "juego",
        "el juego",
        "este juego",
        "ese juego",
        "este",
        "ese",
        "esto",
        "eso",
        "el",
        "lo",
        "x",
    ],
)
def test_nombre_valido_rechaza_valores_nulos_genericos_o_cortos(valor: object) -> None:
    assert chat_service.nombre_valido(valor) is None


@pytest.mark.parametrize(
    "nombre", ["Catan", "SETI", "7 Wonders", "Criaturas maravillosas", "스플렌더"]
)
def test_nombre_valido_conserva_titulos_reales(nombre: str) -> None:
    assert chat_service.nombre_valido(f'  "{nombre}"! ') == nombre


def test_planner_conserva_intencion_al_recibir_nombre_en_ingles() -> None:
    plan = chat_service._plan_determinista(
        "El nombre en inglés es: Wondrous Creatures",
        None,
        None,
        "evaluar_compra",
    )

    assert plan.intent == "evaluar_compra"
    assert plan.steps[0].args == {"nombre": "Wondrous Creatures"}


def test_extraer_nombre_recorta_colas_de_contexto() -> None:
    assert (
        chat_service._extraer_nombre_juego(
            "¿Qué tal entraría Criaturas maravillosas en la colección?"
        )
        == "Criaturas maravillosas"
    )


@pytest.mark.parametrize(
    "mensaje",
    [
        '"Catan" sería una buena compra',
        '"Catan" es buena compra',
        '"Catan" vale la pena',
        'vale la pena "Catan"',
        'qué tal "Catan"',
        'qué tal entraría "Catan" en la colección',
        'cómo entraría "Catan"',
        'debería comprar "Catan"',
        'me conviene "Catan"',
        'conviene comprar "Catan"',
        'háblame de "Catan"',
        'detalle de "Catan"',
        'info de "Catan"',
        "Catan",
    ],
)
def test_extraer_nombre_cubre_formulaciones_de_compra_y_detalle(mensaje: str) -> None:
    assert chat_service._extraer_nombre_juego(mensaje) == "Catan"


@pytest.mark.asyncio
async def test_cadena_respaldo_descarta_nombre_del_planner_no_anclado() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return catan if game_id == "13" else None

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[chat_service.PasoPlan(id="1", tool="evaluar_compra", args={"nombre": "Wyrmspan"})],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿Qué tal Catan?", CatalogoPrueba(), None, None
    )

    assert resuelto.steps[0].args == {"nombre": "Catan"}


@pytest.mark.asyncio
async def test_cadena_respaldo_usa_intencion_pendiente_y_foco() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return catan if game_id == "13" else None

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[chat_service.PasoPlan(id="1", tool="evaluar_compra")],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿sería una buena compra?", CatalogoPrueba(), "13", "evaluar_compra"
    )

    assert resuelto.steps[0].args == {"game_id": "13"}


@pytest.mark.asyncio
async def test_cadena_respaldo_usa_foco_para_referencia_generica() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return catan if game_id == "13" else None

    plan = chat_service._plan_determinista("¿y ese vale la pena?", None, "13")
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿y ese vale la pena?", CatalogoPrueba(), "13", "evaluar_compra"
    )

    assert resuelto.steps[0].args == {"game_id": "13"}


@pytest.mark.asyncio
async def test_cadena_respaldo_prioriza_nombre_del_mensaje_sobre_foco() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return catan if game_id == "13" else None

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[chat_service.PasoPlan(id="1", tool="evaluar_compra", args={"nombre": "Catan"})],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿Vale la pena SETI?", CatalogoPrueba(), "13", "evaluar_compra"
    )

    assert resuelto.steps[0].args == {"nombre": "SETI"}


@pytest.mark.asyncio
async def test_cadena_respaldo_pide_aclaracion_sin_nombre_ni_ancla() -> None:
    class CatalogoPrueba:
        async def obtener_juego(self, _game_id: str) -> None:
            return None

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[chat_service.PasoPlan(id="1", tool="evaluar_compra")],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿sería una buena compra?", CatalogoPrueba(), None, None
    )

    assert resuelto.intent == "general"
    assert resuelto.steps == []
    respuesta = chat_service._narrar(resuelto.intent, [])
    assert respuesta == "¿De qué juego me hablas? Escríbeme su nombre."


@pytest.mark.asyncio
async def test_cadena_respaldo_descarta_game_id_no_anclado() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return catan if game_id == "13" else None

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[chat_service.PasoPlan(id="1", tool="evaluar_compra", args={"game_id": "13"})],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿sería una buena compra?", CatalogoPrueba(), None, None
    )

    assert resuelto.intent == "general"
    assert resuelto.motivo_descarte == "id_no_aceptado"


@pytest.mark.asyncio
async def test_game_id_no_anclado_se_ignora_y_usa_nombre() -> None:
    juegos = {
        "13": SimpleNamespace(id="13", nombre="Catan"),
        "418059": SimpleNamespace(id="418059", nombre="SETI"),
    }

    class CatalogoPrueba:
        async def obtener_juego(self, game_id: str) -> Any:
            return juegos.get(game_id)

    plan = chat_service.PlanLlm(
        intent="evaluar_compra",
        steps=[
            chat_service.PasoPlan(
                id="1", tool="evaluar_compra", args={"game_id": "13", "nombre": "SETI"}
            )
        ],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿Vale la pena SETI?", CatalogoPrueba(), None, None
    )

    assert resuelto.steps[0].args == {"nombre": "SETI"}
    assert resuelto.motivo_descarte == "id_no_aceptado"


@pytest.mark.asyncio
async def test_game_id_de_boton_se_acepta() -> None:
    catan = SimpleNamespace(id="13", nombre="Catan")

    class CatalogoPrueba:
        async def obtener_juego(self, _game_id: str) -> Any:
            return catan

    plan = chat_service.PlanLlm(
        intent="detalle_juego",
        steps=[chat_service.PasoPlan(id="1", tool="detalle_juego", args={"game_id": "13"})],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "Catan", CatalogoPrueba(), None, None, "13"
    )

    assert resuelto.origen_nombre == "boton"
    assert resuelto.nombre_final == "Catan"


@pytest.mark.asyncio
@pytest.mark.parametrize("game_id", ["abc", "999"])
async def test_game_id_no_numerico_o_inexistente_se_descarta(game_id: str) -> None:
    class CatalogoPrueba:
        async def obtener_juego(self, _game_id: str) -> None:
            return None

    plan = chat_service.PlanLlm(
        intent="detalle_juego",
        steps=[chat_service.PasoPlan(id="1", tool="detalle_juego", args={"game_id": game_id})],
    )
    resuelto = await chat_service._aplicar_cadena_respaldo_juego(
        plan, "¿sería una buena compra?", CatalogoPrueba(), None, None
    )

    assert resuelto.intent == "general"
    assert resuelto.motivo_descarte == "id_no_aceptado"


@pytest.mark.asyncio
async def test_herramienta_rechaza_nombre_e_id_vacios() -> None:
    with pytest.raises(ValueError, match="requiere un nombre"):
        await chat_service._ejecutar_tool("detalle_juego", {}, None, "u", None, None, Settings())


@pytest.mark.asyncio
async def test_nombre_inventado_no_se_resuelve_por_coincidencia_aproximada() -> None:
    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [SimpleNamespace(id="1", nombre="EGO", users_rated=100)]

    estado, juegos = await chat_service._resolver(
        CatalogoPrueba(),
        "Juegoinventado123",
        None,
        Settings(llm_enabled=False),
    )

    assert (estado, juegos) == ("no_encontrado", ())


@pytest.mark.asyncio
async def test_resolver_rechaza_consultas_normalizadas_cortas() -> None:
    juego = SimpleNamespace(id="1", nombre="스플렌더: Pokémon", users_rated=100)

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    assert await chat_service._resolver(
        CatalogoPrueba(), "", None, Settings(llm_enabled=False)
    ) == ("no_encontrado", ())
    assert await chat_service._resolver(
        CatalogoPrueba(), ".", None, Settings(llm_enabled=False)
    ) == ("no_encontrado", ())


@pytest.mark.asyncio
async def test_resolver_conserva_titulos_no_latinos_y_no_confunde_consultas() -> None:
    juegos = [
        SimpleNamespace(id="1", nombre="스플렌더: Pokémon", users_rated=100),
        SimpleNamespace(id="2", nombre="Wyrmspan", users_rated=100),
        SimpleNamespace(
            id="3", nombre="SETI: Search for Extraterrestrial Intelligence", users_rated=100
        ),
        SimpleNamespace(id="4", nombre="Catan", users_rated=100),
        SimpleNamespace(id="5", nombre="Brass: Birmingham", users_rated=100),
    ]

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos

    repo = CatalogoPrueba()
    settings = Settings(llm_enabled=False)
    for consulta, esperado in (
        ("스플렌더: Pokémon", "1"),
        ("Wyrmspan", "2"),
        ("SETI", "3"),
        ("Catan", "4"),
        ("Brass Birmingham", "5"),
    ):
        estado, encontrados = await chat_service._resolver(repo, consulta, None, settings)
        assert estado == "encontrado"
        assert encontrados[0].id == esperado

    estado, encontrados = await chat_service._resolver(
        repo, "Creaturas Maravillosas es buena compra?", None, settings
    )
    assert (estado, encontrados) == ("no_encontrado", ())


@pytest.mark.asyncio
async def test_traduccion_simulada_usa_el_nombre_extraido_sin_cola(monkeypatch: Any) -> None:
    juego = SimpleNamespace(id="400366", nombre="Wondrous Creatures", users_rated=7342)
    llamada: dict[str, Any] = {}

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            llamada.update(kwargs)
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=["Wondrous Creatures"], identificaciones=[]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    nombre = chat_service._extraer_nombre_juego(
        "¿Qué tal entraría Criaturas maravillosas en la colección?"
    )
    estado, juegos, interpretado, titulos, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        nombre,
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert estado == "ambiguo"
    assert juegos[0].id == "400366"
    assert interpretado is None
    assert titulos == ["Wondrous Creatures"]
    assert traza == {
        "llm_called": True,
        "traducciones_literales": ["Wondrous Creatures"],
        "identificaciones": [],
        "coincidencias": [{"propuesta": "Wondrous Creatures", "coincidencias": ["400366"]}],
    }
    assert "traducciones literales al inglés" in llamada["input"]


@pytest.mark.asyncio
async def test_planner_llm_recibe_manifest_y_ejemplos_naturales(monkeypatch: Any) -> None:
    llamadas: dict[str, Any] = {}

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            llamadas.update(kwargs)
            parsed = chat_service._PlanRespuestaLlm(
                intent="evaluar_compra",
                steps=[
                    chat_service._PasoPlanLlm(
                        id="1", tool="evaluar_compra", args={"nombre": "SETI"}
                    )
                ],
            )
            return type("Respuesta", (), {"output_parsed": parsed})()

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)

    plan = await chat_service._plan_llm(
        settings, "¿Qué tal entraría SETI en la colección?", "Wingspan"
    )

    assert plan is not None
    assert plan.steps[0].tool == "evaluar_compra"
    prompt = llamadas["input"]
    assert "si un juego encaja, conviene o es redundante" in prompt
    assert "solo cuando el usuario pide ver o listar su colección" in prompt
    assert "¿qué tal entraría X?" in prompt


@pytest.mark.parametrize(
    ("pregunta", "intent", "tool", "args"),
    [
        (
            "Tengo ganas de comprar Wyrmspan, ¿vale la pena?",
            "evaluar_compra",
            "evaluar_compra",
            {"nombre": "Wyrmspan"},
        ),
        ("¿Qué me falta?", "que_me_falta", "que_me_falta", {}),
        (
            "Quiero un plan de 3 juegos para cubrir huecos.",
            "que_compro",
            "que_compro",
            {"n": 3},
        ),
        (
            "Somos 6 y tenemos 45 minutos, ¿qué saco?",
            "que_saco_hoy",
            "que_saco_hoy",
            {"jugadores": 6, "minutos": 45},
        ),
        ("Catan", "detalle_juego", "detalle_juego", {"nombre": "Catan"}),
        ("¿Quién ganó el mundial de fútbol?", "fuera_de_dominio", None, {}),
    ],
)
def test_planner_determinista_resuelve_guion_sin_llm(
    pregunta: str, intent: str, tool: str | None, args: dict[str, Any]
) -> None:
    settings = Settings(llm_enabled=False)
    assert not settings.llm_active

    plan = chat_service._plan_determinista(pregunta, None)

    assert plan.intent == intent
    if tool is None:
        assert plan.steps == []
    else:
        assert len(plan.steps) == 1
        assert plan.steps[0].tool == tool
        assert plan.steps[0].args == args


def test_planner_determinista_usa_el_juego_en_foco_en_una_continuacion() -> None:
    plan = chat_service._plan_determinista("¿sería una buena compra?", None, "123")

    assert plan.intent == "evaluar_compra"
    assert plan.steps[0].args == {"game_id": "123"}


def test_planner_determinista_prioriza_nombre_nuevo_sobre_foco() -> None:
    plan = chat_service._plan_determinista(
        "¿Qué tal entraría Criaturas maravillosas en la colección?", None, "123"
    )

    assert plan.intent == "evaluar_compra"
    assert plan.steps[0].args == {"nombre": "Criaturas maravillosas"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pregunta", "intent", "tool"),
    [
        ("¿Qué tal entraría SETI en la colección?", "evaluar_compra", "evaluar_compra"),
        ("¿Me conviene SETI?", "evaluar_compra", "evaluar_compra"),
        ("¿Vale la pena SETI?", "evaluar_compra", "evaluar_compra"),
        ("¿Debería comprar SETI?", "evaluar_compra", "evaluar_compra"),
        ("¿Y SETI?", "evaluar_compra", "evaluar_compra"),
        ("Quiero ver mi colección", "coleccion", "ver_coleccion"),
        ("¿Qué juegos tengo?", "coleccion", "ver_coleccion"),
        ("¿Qué experiencias me faltan?", "que_me_falta", "que_me_falta"),
        ("¿Dónde tengo huecos?", "que_me_falta", "que_me_falta"),
        ("Dame un plan de 3 juegos", "que_compro", "que_compro"),
        ("Somos 5 y tenemos 60 minutos", "que_saco_hoy", "que_saco_hoy"),
        ("¿Quién ganó el mundial?", "fuera_de_dominio", None),
    ],
)
async def test_planner_y_validacion_resuelven_parafrasis(
    pregunta: str, intent: str, tool: str | None
) -> None:
    seti = SimpleNamespace(id="418059", nombre="SETI: Search for Extraterrestrial Intelligence")

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [seti]

    plan = chat_service._plan_determinista(pregunta, None)
    plan = await chat_service._validar_plan_con_juego(
        plan, pregunta, CatalogoPrueba(), [], Settings(llm_enabled=False)
    )

    assert plan.intent == intent
    if tool is None:
        assert plan.steps == []
    else:
        assert plan.steps[0].tool == tool


@pytest.mark.asyncio
async def test_planner_fallback_resuelve_wyrmspan_por_nombre_extraido() -> None:
    juego = SimpleNamespace(id="410201", nombre="Wyrmspan")

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    settings = Settings(llm_enabled=False)
    plan = chat_service._plan_determinista("Tengo ganas de comprar Wyrmspan, ¿vale la pena?", None)
    estado, juegos = await chat_service._resolver(
        CatalogoPrueba(), plan.steps[0].args["nombre"], None, settings
    )

    assert estado == "encontrado"
    assert [item.id for item in juegos] == ["410201"]


@pytest.mark.asyncio
async def test_resolver_acepta_titulo_antes_de_dos_puntos() -> None:
    juego = SimpleNamespace(
        id="418059", nombre="SETI: Search for Extraterrestrial Intelligence", users_rated=5000
    )
    homonimo = SimpleNamespace(id="999", nombre="Seti", users_rated=900)

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego, homonimo]

    estado, juegos = await chat_service._resolver(
        CatalogoPrueba(), "SETI", None, Settings(llm_enabled=False)
    )

    assert estado == "encontrado"
    assert [item.id for item in juegos] == ["418059"]


@pytest.mark.asyncio
async def test_resolver_traduce_nombre_con_cliente_simulado(monkeypatch: Any) -> None:
    juego = SimpleNamespace(id="1", nombre="Wingspan", users_rated=100)

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(titulos=["Wingspan"])
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, juegos, interpretado, sugerencias, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Alas",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert estado == "ambiguo"
    assert juegos[0].id == "1"
    assert interpretado is None
    assert sugerencias == ["Wingspan"]
    assert traza == {
        "llm_called": True,
        "traducciones_literales": [],
        "identificaciones": ["Wingspan"],
        "coincidencias": [{"propuesta": "Wingspan", "coincidencias": ["1"]}],
    }


@pytest.mark.asyncio
async def test_resolver_traduccion_no_resuelta(monkeypatch: Any) -> None:
    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return []

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(titulos=["Nada"])
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, juegos, interpretado, sugerencias, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Nombre desconocido",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert (estado, juegos, interpretado, sugerencias) == ("no_encontrado", (), None, ["Nada"])
    assert traza == {
        "llm_called": True,
        "traducciones_literales": [],
        "identificaciones": ["Nada"],
        "coincidencias": [{"propuesta": "Nada", "coincidencias": []}],
    }


@pytest.mark.asyncio
async def test_resolver_traduccion_devuelve_sugerencias_cercanas(monkeypatch: Any) -> None:
    juego = SimpleNamespace(id="400366", nombre="Wondrous Creatures", users_rated=7342)

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(titulos=["Wondrous Creature"])
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)

    async def sin_coincidencia(*_args: Any, **_kwargs: Any) -> tuple[str, tuple[Any, ...]]:
        return "no_encontrado", ()

    monkeypatch.setattr(chat_service, "_resolver", sin_coincidencia)
    estado, juegos, interpretado, sugerencias, _ = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Criaturas maravillosas",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert estado == "ambiguo"
    assert [item.id for item in juegos] == ["400366"]
    assert interpretado is None
    assert sugerencias == ["Wondrous Creature"]


@pytest.mark.asyncio
async def test_traduccion_literal_tiene_prioridad_y_no_confunde_fantastic_creatures(
    monkeypatch: Any,
) -> None:
    juegos = [
        SimpleNamespace(id="400366", nombre="Wondrous Creatures", users_rated=7342),
        SimpleNamespace(
            id="119890", nombre="Agricola: All Creatures Big and Small", users_rated=5000
        ),
    ]

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    traducciones_literales=["Wondrous Creatures"],
                    identificaciones=["Fantastic Creatures"],
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, candidatos, _, _, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Criaturas maravillosas",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert estado == "ambiguo"
    assert [juego.id for juego in candidatos] == ["400366"]
    assert traza["traducciones_literales"] == ["Wondrous Creatures"]
    assert traza["identificaciones"] == ["Fantastic Creatures"]


@pytest.mark.asyncio
async def test_identificacion_simulada_muestra_hasta_tres_coincidencias_sin_resolver(
    monkeypatch: Any,
) -> None:
    juegos = [
        SimpleNamespace(id="1", nombre="Wingspan", users_rated=100),
        SimpleNamespace(id="2", nombre="Wyrmspan: Upgrade Pack", users_rated=50),
        SimpleNamespace(id="3", nombre="Root", users_rated=200),
    ]

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output_parsed=chat_service._TitulosTraducidosLlm(
                    titulos=["Wingspan", "Wyrmspan", "Root"]
                )
            )

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, candidatos, _, propuestas, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Pajaros famosos",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert estado == "ambiguo"
    # La coincidencia exacta normalizada va primero; después el puntaje y el orden de la lista.
    assert [juego.id for juego in candidatos] == ["1", "3", "2"]
    assert propuestas == ["Wingspan", "Wyrmspan", "Root"]
    assert traza["coincidencias"] == [
        {"propuesta": "Wingspan", "coincidencias": ["1"]},
        {"propuesta": "Wyrmspan", "coincidencias": ["2"]},
        {"propuesta": "Root", "coincidencias": ["3"]},
    ]


@pytest.mark.asyncio
async def test_resolver_traduccion_se_omite_sin_clave(monkeypatch: Any) -> None:
    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return []

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            pytest.fail("No debe consultar el LLM sin clave.")

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    estado, juegos, interpretado, sugerencias, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(), "Nombre desconocido", None, Settings(llm_enabled=True)
    )

    assert (estado, juegos, interpretado, sugerencias) == ("no_encontrado", (), None, [])
    assert traza is None


@pytest.mark.asyncio
async def test_resolver_traduccion_registra_el_error_del_llm(monkeypatch: Any) -> None:
    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return []

    class Responses:
        async def parse(self, **_kwargs: Any) -> Any:
            raise RuntimeError("fallo de traducción")

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    *_, traza = await chat_service._resolver_con_traduccion(
        CatalogoPrueba(),
        "Criaturas maravillosas",
        None,
        Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True),
    )

    assert traza == {
        "llm_called": True,
        "traducciones_literales": [],
        "identificaciones": [],
        "error": "fallo de traducción",
    }


def test_plantilla_veredicto_muestra_motivo_y_un_solo_emoji() -> None:
    respuesta = chat_service._narrar(
        "evaluar_compra",
        [
            {
                "estado": "encontrado",
                "veredicto": "redundante",
                "juego": {"nombre": "Wyrmspan"},
                "juego_mas_parecido": {"nombre": "Wingspan"},
                "regla_exacta": "misma_linea_de_producto",
            }
        ],
    )

    presentada = chat_service._presentar_respuesta(
        respuesta,
        "evaluar_compra",
        [{"estado": "encontrado", "veredicto": "redundante"}],
    )
    assert presentada.startswith("⚠️ **Wyrmspan** es redundante con tu colección.")
    assert presentada.count("⚠️") == 1
    assert "Comparte línea de producto con **Wingspan**." in presentada


def test_saneador_elimina_negritas_desbalanceadas_por_linea() -> None:
    assert chat_service._sanear_negritas("**Sin cierre\n**Correcto**") == "Sin cierre\n**Correcto**"


def test_formatear_resultados_para_narrador() -> None:
    resultados = [
        {
            "juego": {"peso": 2.345, "precio_usd": 67.5, "fecha_precio": "2026-09-24T23:12:15Z"},
            "similitud": {"total": 0.8342, "mecanicas": 0.6479},
        }
    ]

    assert chat_service._formatear_resultados_narrador(resultados) == [
        {
            "juego": {"peso": "2.3"},
            "similitud": {"total": "83%", "mecanicas": "65%"},
        }
    ]


@pytest.mark.asyncio
async def test_resolver_devuelve_ambiguo_sin_juego_dominante() -> None:
    juegos_catalogo = [
        SimpleNamespace(id="1", nombre="Nova", users_rated=400),
        SimpleNamespace(id="2", nombre="Nova: Expansion", users_rated=300),
    ]

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos_catalogo

    estado, candidatos = await chat_service._resolver(
        CatalogoPrueba(), "Nova", None, Settings(llm_enabled=False)
    )

    assert estado == "ambiguo"
    assert [juego.id for juego in candidatos] == ["1", "2"]


@pytest.mark.asyncio
async def test_validacion_no_fuerza_juego_por_coincidencia_difusa() -> None:
    juego = SimpleNamespace(id="444042", nombre="Alta")

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return [juego]

    plan = chat_service._plan_determinista("¿Qué experiencias me faltan?", None)
    validado = await chat_service._validar_plan_con_juego(
        plan, "¿Qué experiencias me faltan?", CatalogoPrueba(), [], Settings(llm_enabled=False)
    )

    assert validado.intent == "que_me_falta"


@pytest.mark.asyncio
async def test_resolver_prioriza_coincidencia_exacta_sobre_variantes() -> None:
    juegos_catalogo = [
        SimpleNamespace(id="13", nombre="Catan"),
        SimpleNamespace(id="278", nombre="Catan Card Game"),
        SimpleNamespace(id="184842", nombre="Catan Junior"),
    ]

    class CatalogoPrueba:
        async def todos_los_juegos(self) -> list[Any]:
            return juegos_catalogo

    settings = Settings(llm_enabled=False)
    estado, candidatos = await chat_service._resolver(CatalogoPrueba(), "Catan", None, settings)

    assert estado == "encontrado"
    assert [juego.id for juego in candidatos] == ["13"]


@pytest.mark.parametrize(
    ("respuesta", "resultados", "hallazgo"),
    [
        (
            "Wyrmspan es redundante.",
            [{"veredicto": "redundante", "regla_exacta": "reimplementa"}],
            "Falta explicar la regla exacta",
        ),
        (
            "La opción B recomendada tiene valor cubierto.",
            [
                {
                    "opciones": [
                        {"etiqueta": "A", "valor_cubierto": 1},
                        {"etiqueta": "B", "valor_cubierto": 1},
                        {"etiqueta": "C", "valor_cubierto": 1},
                    ]
                }
            ],
            "El plan debe presentar A con su valor cubierto.",
        ),
        (
            "El peso es pesado.",
            [{"juego": {"nivel_peso": "medio"}}],
            "El nivel de peso pesado no aparece en los resultados.",
        ),
        (
            "Faltantes: ninguno.",
            [{"ejes": {"Mecánicas": {"faltantes": [], "debiles": {"Subastas": "Catan"}}}}],
            "La respuesta de cobertura debe incluir faltantes y débiles.",
        ),
    ],
)
def test_critic_determinista_aplica_reglas_nuevas(
    respuesta: str, resultados: list[dict[str, Any]], hallazgo: str
) -> None:
    findings = chat_service._criticar_determinista(respuesta, resultados)

    assert any(hallazgo in finding for finding in findings)


def test_critic_determinista_rechaza_opcion_recomendada_distinta_de_a() -> None:
    resultados = [
        {
            "opciones": [
                {"etiqueta": "A", "valor_cubierto": 1},
                {"etiqueta": "B", "valor_cubierto": 1},
                {"etiqueta": "C", "valor_cubierto": 1},
            ]
        }
    ]
    respuesta = "A valor cubierto. B valor cubierto. C valor cubierto. Opción B recomendada."

    findings = chat_service._criticar_determinista(respuesta, resultados)

    assert "Solo la opción A puede llamarse recomendada." in findings


@pytest.mark.asyncio
async def test_critic_llm_devuelve_hallazgos_estructurados(monkeypatch: Any) -> None:
    llamadas: dict[str, Any] = {}
    hallazgo = chat_service._HallazgoLlm(
        categoria="juego_o_atributo_no_disponible",
        detalle="El narrador menciona una mecánica ausente.",
    )

    class Responses:
        async def parse(self, **kwargs: Any) -> Any:
            llamadas.update(kwargs)
            return type(
                "Respuesta",
                (),
                {
                    "output_parsed": chat_service._CriticaRespuestaLlm(
                        ok=False, hallazgos=[hallazgo]
                    )
                },
            )()

    class Cliente:
        def __init__(self, **_kwargs: Any) -> None:
            self.responses = Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", Cliente)
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    resultados = [{"juego": {"nombre": "Wingspan", "mechanics": ["Draft"]}}]

    findings = await chat_service._criticar_llm(
        settings, "Tiene otra mecánica.", resultados, "¿Qué tal Wingspan?"
    )

    assert findings == [
        {
            "categoria": "juego_o_atributo_no_disponible",
            "detalle": "El narrador menciona una mecánica ausente.",
        }
    ]
    assert llamadas["model"] == settings.llm_model_fast
    assert llamadas["text_format"] is chat_service._CriticaRespuestaLlm
    assert "No uses conocimiento general" in llamadas["input"][0]["content"]
    assert "ante la duda, recházala" in llamadas["input"][0]["content"]
    assert "afirmación descriptiva sobre un juego" in llamadas["input"][0]["content"]
    assert "no contesta la pregunta del usuario" in llamadas["input"][0]["content"]
    assert "¿Qué tal Wingspan?" in llamadas["input"][1]["content"]


def test_chat_reintenta_narrador_y_persiste_critic(
    api_client: TestClient, monkeypatch: Any
) -> None:
    fixture = _fixture()
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    monkeypatch.setattr(chat_api, "settings", settings)

    async def planner(*_args: Any) -> chat_service.PlanLlm:
        return chat_service.PlanLlm.model_validate(fixture["planner"])

    async def narrator(
        _settings: Settings,
        _results: list[dict[str, Any]],
        _pregunta: str,
        feedback: list[str] | None = None,
    ) -> str:
        return fixture["narrador_corregido"] if feedback else fixture["narrador_inicial"]

    async def critic(*_args: Any) -> list[str]:
        return []

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", narrator)
    monkeypatch.setattr(chat_service, "_criticar_llm", critic)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Wingspan?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == (
        "📦 " + fixture["narrador_corregido"] + "\n\nPrecio de referencia: USD 55.00 "
        "(BoardGamePrices, 1 ene 2026).\n\n💡 ¿Quieres simular qué pasaría si lo vendes?"
    )
    assert payload["critic_passed"] is True
    assert payload["critic_attempts"] == 1
    assert payload["llm_used"] is True
    persisted = api_client.get(f"/api/v1/chat/runs/{payload['run_id']}")
    assert persisted.json()["critic_attempts"] == 1
    assert persisted.json()["critic_findings"] == []


def test_chat_aprobado_por_critic_al_primer_intento(
    api_client: TestClient, monkeypatch: Any
) -> None:
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    monkeypatch.setattr(chat_api, "settings", settings)
    llamadas_narrador: list[list[str | dict[str, str]] | None] = []

    async def planner(*_args: Any) -> chat_service.PlanLlm:
        return chat_service.PlanLlm.model_validate(_fixture()["planner"])

    async def narrator(
        _settings: Settings,
        _results: list[dict[str, Any]],
        _pregunta: str,
        feedback: list[str | dict[str, str]] | None = None,
    ) -> str:
        llamadas_narrador.append(feedback)
        return "**Wingspan** aporta a la colección."

    async def critic(*_args: Any) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", narrator)
    monkeypatch.setattr(chat_service, "_criticar_llm", critic)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Wingspan?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["critic_passed"] is True
    assert payload["critic_attempts"] == 0
    assert llamadas_narrador == [None]


def test_chat_usa_plantilla_sin_clave(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(chat_api, "settings", Settings(llm_enabled=True))

    async def no_debe_llamarse(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("No se debe usar el cliente LLM sin clave.")

    monkeypatch.setattr(chat_service, "_plan_llm", no_debe_llamarse)
    monkeypatch.setattr(chat_service, "_narrar_llm", no_debe_llamarse)
    monkeypatch.setattr(chat_service, "_criticar_llm", no_debe_llamarse)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Qué le falta a mi colección?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm_used"] is False
    assert payload["critic_attempts"] == 0
    assert payload["critic_passed"] is True
    assert "Huecos de la colección" in payload["answer"]


def test_chat_fuera_de_dominio_conserva_respuesta_fija(
    api_client: TestClient, monkeypatch: Any
) -> None:
    settings = Settings(openai_api_key=SecretStr("fixture-key"), llm_enabled=True)
    monkeypatch.setattr(chat_api, "settings", settings)

    async def planner(*_args: Any) -> chat_service.PlanLlm:
        return chat_service.PlanLlm(intent="fuera_de_dominio")

    async def no_debe_llamarse(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Un intent fijo no debe llamar narrator ni critic LLM.")

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", no_debe_llamarse)
    monkeypatch.setattr(chat_service, "_criticar_llm", no_debe_llamarse)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Quién ganó el mundial?"})

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "🎲 Mi experiencia se limita al análisis y recomendación de juegos de mesa.\n\n"
        "💡 ¿Quieres evaluar otro juego?"
    )


def test_chat_usa_plantilla_si_se_agotan_los_reintentos(
    api_client: TestClient, monkeypatch: Any
) -> None:
    settings = Settings(
        openai_api_key=SecretStr("fixture-key"), llm_enabled=True, critic_max_retries=1
    )
    monkeypatch.setattr(chat_api, "settings", settings)

    async def planner(*_args: Any) -> chat_service.PlanLlm:
        return chat_service.PlanLlm.model_validate(_fixture()["planner"])

    async def narrator(*_args: Any, **_kwargs: Any) -> str:
        return "**Wingspan**: aporta. Similitud total: 99.0."

    async def critic(*_args: Any) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(chat_service, "_plan_llm", planner)
    monkeypatch.setattr(chat_service, "_narrar_llm", narrator)
    monkeypatch.setattr(chat_service, "_criticar_llm", critic)

    response = api_client.post("/api/v1/chat", json={"mensaje": "¿Vale la pena Wingspan?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["critic_attempts"] == 1
    assert payload["critic_passed"] is True
    assert "99.0" not in payload["answer"]
    assert payload["llm_used"] is True


def test_fixtures_llm_no_contienen_secretos() -> None:
    fixtures = (Path(__file__).parent / "fixtures").glob("*.json")
    for fixture in fixtures:
        text = fixture.read_text()
        assert "Bearer" not in text
        assert "sk-" not in text


def test_fixture_casos_reales_saneado_sin_cabeceras() -> None:
    ruta = Path(__file__).parent / "fixtures" / "chat_casos_reales_saneados.json"
    fixture = json.loads(ruta.read_text())

    assert len(fixture["casos"]) == 6
    assert sum(caso["llamadas_estimadas"] for caso in fixture["casos"]) == 20
    assert all(
        not {"headers", "authorization", "cookie", "set-cookie"}.intersection(
            clave.lower() for clave in caso
        )
        for caso in fixture["casos"]
    )


def test_fixture_catan_registra_ambiguedad_real() -> None:
    ruta = Path(__file__).parent / "fixtures" / "chat_catan_ambiguo_saneado.json"
    fixture = json.loads(ruta.read_text())

    assert fixture["plan_llm"]["steps"][0]["args"] == {"nombre": "Catan"}
    assert fixture["respuesta_final"] == (
        "Encontré varias opciones. Elige el juego exacto para evaluarlo."
    )
    assert fixture["critic_passed"] is True
    assert fixture["critic_attempts"] == 1
    assert {candidato["id"] for candidato in fixture["candidatos"]} == {
        "13",
        "278",
        "282853",
        "67239",
        "125921",
    }


def test_configuracion_usa_modelos_verificados_por_defecto() -> None:
    configuracion = Settings()

    assert configuracion.llm_model == "gpt-5.1"
    assert configuracion.llm_model_fast == "gpt-5.1"
