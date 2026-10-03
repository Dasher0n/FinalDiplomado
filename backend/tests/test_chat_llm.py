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

    findings = await chat_service._criticar_llm(settings, "Tiene otra mecánica.", resultados)

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
    assert payload["answer"] == fixture["narrador_corregido"]
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
        "Mi experiencia se limita al análisis y recomendación de juegos de mesa."
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
