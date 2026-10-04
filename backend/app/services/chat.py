"""Orquestador persistente y determinista del asistente de ludoteca."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.catalogo import _juego_detalle
from app.api.v1.engine import _artefactos, _coleccion, _juego, _niveles
from app.core.config import Settings
from app.db.models import AgentRun, AgentStep, ChatMessage, ChatSession, Game, ToolCall
from app.engine.motor import (
    cobertura,
    evaluar_redundancia,
    normalizar_nombre,
    opciones_compra,
    que_saco_hoy,
)
from app.profiles import juego_excluido_del_plan
from app.repositories.catalogo import CatalogoRepository
from app.schemas.chat import CandidatoChat, ChatRespuesta, PasoPlan, TarjetaChat

_TOOLS: set[str] = {
    "ver_coleccion",
    "detalle_juego",
    "evaluar_compra",
    "que_me_falta",
    "que_compro",
    "que_saco_hoy",
}
_FUNCIONES_NO_DISPONIBLES = {
    "comparar",
    "filtrar",
    "modo precio",
    "capturar precio",
    "tarjeta para compartir",
}
_INTENTS = {
    "evaluar_compra",
    "que_me_falta",
    "que_compro",
    "que_saco_hoy",
    "detalle_juego",
    "coleccion",
    "reglas",
    "fuera_de_dominio",
    "general",
}
_REFERENCIAS_GENERICAS = {
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
}
_NOMBRES_NULOS = {"null", "none", "nil", "undefined", "n/a", "na", "desconocido"}


def nombre_valido(valor: object) -> str | None:
    """Limpia un título y descarta valores nulos, genéricos o demasiado cortos."""
    if not isinstance(valor, str):
        return None
    nombre = valor.strip(" \t\r\n\"'«»“”¿?¡!.,:")
    sin_relleno = re.sub(r"[\s\"'«»“”¿?¡!.,:]", "", nombre)
    if not sin_relleno:
        return None
    minusculas = nombre.casefold()
    if minusculas in _NOMBRES_NULOS or minusculas in _REFERENCIAS_GENERICAS:
        return None
    if len(normalizar_nombre(nombre)) < 2:
        return None
    return nombre


class PlanLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    steps: list[PasoPlan] = Field(default_factory=list)


class _ArgsPlanLlm(BaseModel):
    """Argumentos cerrados para impedir que el plan invente parametros de tools."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = None
    game_id: str | None = None
    n: int | None = None
    average_min: float | None = None
    users_rated_min: int | None = None
    ejes_ignorados: list[str] | None = None
    jugadores: int | None = None
    minutos: float | None = None
    edad_minima: int | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        nombre = nombre_valido(valor)
        if nombre is None:
            raise ValueError("nombre debe contener un título de juego válido")
        return nombre


class _PasoPlanLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str
    args: _ArgsPlanLlm = Field(default_factory=_ArgsPlanLlm)
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def exigir_nombre_para_tool_de_juego(self) -> _PasoPlanLlm:
        if self.tool in {"detalle_juego", "evaluar_compra"} and self.args.nombre is None:
            raise ValueError(f"{self.tool} requiere un nombre de juego válido")
        return self


class _PlanRespuestaLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    steps: list[_PasoPlanLlm] = Field(default_factory=list)


class _HallazgoLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoria: Literal[
        "cifra_sin_fuente",
        "juego_o_atributo_no_disponible",
        "recomendacion_sin_respaldo",
    ]
    detalle: str


class _CriticaRespuestaLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    hallazgos: list[_HallazgoLlm] = Field(default_factory=list)


class _TitulosTraducidosLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulos: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("titulos")
    @classmethod
    def limpiar_titulos(cls, valores: list[str]) -> list[str]:
        return [titulo for valor in valores if (titulo := nombre_valido(valor)) is not None]


_TOOL_MANIFEST = {
    "ver_coleccion": {
        "descripcion": "Úsala solo cuando el usuario pide ver o listar su colección. Ejemplo: "
        "'¿qué juegos tengo?'.",
        "requeridos": [],
    },
    "detalle_juego": {
        "descripcion": "Úsala para pedir la ficha de un juego ya poseído o una consulta neutra. "
        "Ejemplo: 'cuéntame de Catan'.",
        "requeridos": ["nombre o game_id"],
    },
    "evaluar_compra": {
        "descripcion": "Úsala si un juego encaja, conviene o es redundante con la colección. "
        "Ejemplo: '¿me conviene Wyrmspan?'.",
        "requeridos": ["nombre o game_id"],
    },
    "que_me_falta": {
        "descripcion": "Úsala para preguntar qué experiencias faltan o son débiles. "
        "Ejemplo: '¿qué me falta?'.",
        "requeridos": [],
    },
    "que_compro": {
        "descripcion": "Úsala para pedir planes de compra por número de juegos. "
        "Ejemplo: 'dame un plan de 3 juegos'.",
        "requeridos": ["n"],
    },
    "que_saco_hoy": {
        "descripcion": "Úsala para elegir qué sacar hoy según jugadores y duración. "
        "Ejemplo: 'somos 6 y tenemos 45 minutos'.",
        "requeridos": ["jugadores", "minutos"],
    },
}
_EJEMPLOS_INTENT = (
    "Evaluar compra: '¿qué tal entraría X?', '¿me conviene X?', '¿vale la pena X?', "
    "'¿debería comprar X?' o '¿y X?'. Cobertura: '¿qué me falta?'. "
    "Plan: 'dame un plan de 3 juegos'. Mesa: 'somos 6 y tenemos 45 minutos'. "
    "Colección: '¿qué juegos tengo?'. Ficha: 'cuéntame de X'."
)


def _plan_determinista(
    mensaje: str,
    game_id: str | None,
    juego_en_foco_id: str | None = None,
    intent_pendiente: str | None = None,
) -> PlanLlm:
    texto = mensaje.lower()
    consulta = normalizar_nombre(mensaje)
    titulo_en_ingles = re.match(r"^el nombre en ingl[eé]s es:\s*(.+)$", mensaje, re.IGNORECASE)
    if titulo_en_ingles and intent_pendiente in {"evaluar_compra", "detalle_juego"}:
        nombre = nombre_valido(titulo_en_ingles.group(1))
        if nombre:
            return PlanLlm(
                intent=intent_pendiente,
                steps=[PasoPlan(id="1", tool=intent_pendiente, args={"nombre": nombre})],
            )
    if intent_pendiente in {"evaluar_compra", "detalle_juego"} and re.fullmatch(
        r"[\w\s:,'-]{2,80}", mensaje, re.UNICODE
    ):
        nombre = nombre_valido(mensaje)
        if nombre:
            return PlanLlm(
                intent=intent_pendiente,
                steps=[PasoPlan(id="1", tool=intent_pendiente, args={"nombre": nombre})],
            )
    if any(palabra in texto for palabra in ("ignora", "instrucciones", "prompt", "sistema")):
        return PlanLlm(intent="fuera_de_dominio")
    if any(palabra in texto for palabra in ("regla", "reglamento", "como se juega")):
        return PlanLlm(intent="reglas")

    pide_plan = any(palabra in consulta for palabra in ("que compro", "recomienda", "plan de")) or (
        "comprar" in consulta and any(palabra in consulta for palabra in ("hueco", "juego"))
    )
    if pide_plan:
        numero = re.search(r"\b(\d{1,2})\b", texto)
        n = max(1, min(20, int(numero.group(1)))) if numero else 5
        return PlanLlm(
            intent="que_compro", steps=[PasoPlan(id="1", tool="que_compro", args={"n": n})]
        )
    if any(palabra in consulta for palabra in ("falta", "faltan", "cobertura", "hueco")):
        return PlanLlm(intent="que_me_falta", steps=[PasoPlan(id="1", tool="que_me_falta")])
    if any(palabra in consulta for palabra in ("saco", "jugamos", "somos", "minuto")):
        numeros = [int(valor) for valor in re.findall(r"\b\d{1,3}\b", texto)]
        args: dict[str, Any] = {
            "jugadores": numeros[0] if numeros else 4,
            "minutos": numeros[1] if len(numeros) > 1 else 60,
        }
        return PlanLlm(
            intent="que_saco_hoy", steps=[PasoPlan(id="1", tool="que_saco_hoy", args=args)]
        )
    if (
        any(
            palabra in consulta
            for palabra in (
                "vale la pena",
                "evalu",
                "redund",
                "que tal entraria",
                "me conviene",
                "deberia comprar",
                "buena compra",
                "si lo vendo",
                "se parece",
            )
        )
        or consulta.startswith("y ")
        or game_id
    ):
        nombre = _extraer_nombre_juego(mensaje)
        tiene_nombre = nombre is not None and normalizar_nombre(nombre) != normalizar_nombre(
            mensaje
        )
        args = (
            {"game_id": game_id}
            if game_id
            else ({"nombre": nombre} if tiene_nombre else {"game_id": juego_en_foco_id})
        )
        return PlanLlm(
            intent="evaluar_compra",
            steps=[PasoPlan(id="1", tool="evaluar_compra", args=args)],
        )
    if any(palabra in consulta for palabra in ("coleccion", "tengo")) and not game_id:
        return PlanLlm(intent="coleccion", steps=[PasoPlan(id="1", tool="ver_coleccion")])
    pregunta_general = re.match(r"^(quien|quienes|cuando|donde|por que)\b", consulta)
    if pregunta_general and len(consulta.split()) >= 4:
        return PlanLlm(intent="fuera_de_dominio")
    nombre = _extraer_nombre_juego(mensaje)
    if not game_id and nombre is None:
        return PlanLlm(intent="general")
    args = {"game_id": game_id} if game_id else {"nombre": nombre}
    return PlanLlm(
        intent="detalle_juego",
        steps=[PasoPlan(id="1", tool="detalle_juego", args=args)],
    )


def _extraer_nombre_juego(mensaje: str) -> str | None:
    """Separa el título de juego de la formulación de la pregunta."""
    continuacion = re.match(r"^[¿¡]?\s*y\s+(?P<nombre>.+?)[?!.]*$", mensaje, re.IGNORECASE)
    if continuacion:
        return nombre_valido(continuacion.group("nombre"))
    patrones = (
        r"\b(?:comprar|compra|evaluar|evalúa)\s+(?:el juego\s+)?(?P<nombre>.+?)(?=[,;.!?¿]|$)",
        r"\bvale la pena\s+(?P<nombre>.+?)(?=[,;.!?¿]|$)",
        r"\b(?:qu[eé]\s+tal\s+entrar[ií]a|me\s+conviene|deber[ií]a\s+comprar)\s+(?P<nombre>.+?)(?=\s+(?:en\s+(?:la\s+colecci[oó]n|mi\s+ludoteca)|para\s+mi\s+caf[eé])|[,;.!?¿]|$)",
        r"\b(?P<nombre>.+?)(?=\s+(?:es\s+una\s+buena\s+compra|vale\s+la\s+pena|me\s+conviene)|[,;.!?¿]|$)",
        r"\by\s+(?P<nombre>.+?)(?=[,;.!?¿]|$)",
    )
    for patron in patrones:
        coincidencia = re.search(patron, mensaje, re.IGNORECASE)
        if coincidencia:
            nombre = nombre_valido(coincidencia.group("nombre"))
            if nombre:
                return nombre
    return nombre_valido(mensaje)


def _validar_plan(plan: PlanLlm | None, max_pasos: int) -> PlanLlm | None:
    if plan is None:
        return None
    if plan.intent not in _INTENTS or len(plan.steps) > max_pasos:
        return None
    ids = {paso.id for paso in plan.steps}
    if len(ids) != len(plan.steps):
        return None
    for paso in plan.steps:
        if paso.tool not in _TOOLS or any(
            dependencia not in ids for dependencia in paso.depends_on
        ):
            return None
        if (
            paso.tool in {"detalle_juego", "evaluar_compra"}
            and paso.args.get("game_id") is None
            and nombre_valido(paso.args.get("nombre")) is None
        ):
            return None
        if paso.tool == "que_compro" and not isinstance(paso.args.get("n"), int):
            return None
        if paso.tool == "que_saco_hoy" and not all(
            isinstance(paso.args.get(argumento), (int, float))
            for argumento in ("jugadores", "minutos")
        ):
            return None
    dependencias = {paso.id: set(paso.depends_on) for paso in plan.steps}
    visitados: set[str] = set()
    activos: set[str] = set()

    def tiene_ciclo(paso_id: str) -> bool:
        if paso_id in activos:
            return True
        if paso_id in visitados:
            return False
        activos.add(paso_id)
        if any(tiene_ciclo(dependencia) for dependencia in dependencias[paso_id]):
            return True
        activos.remove(paso_id)
        visitados.add(paso_id)
        return False

    if any(tiene_ciclo(paso.id) for paso in plan.steps):
        return None
    return plan


def _niveles_plan(pasos: list[PasoPlan]) -> list[list[PasoPlan]]:
    pendientes = {paso.id: paso for paso in pasos}
    terminados: set[str] = set()
    niveles: list[list[PasoPlan]] = []
    while pendientes:
        nivel = [
            paso
            for paso in pendientes.values()
            if all(dependencia in terminados for dependencia in paso.depends_on)
        ]
        if not nivel:
            raise ValueError("El plan contiene dependencias no resolubles.")
        niveles.append(nivel)
        for paso in nivel:
            terminados.add(paso.id)
            pendientes.pop(paso.id)
    return niveles


async def _plan_llm(
    settings: Settings, mensaje: str, resumen: str, error_validacion: str | None = None
) -> PlanLlm | None:
    """Usa Responses.parse solo cuando la configuracion habilita explícitamente el LLM."""
    if not settings.llm_active:
        return None
    from openai import AsyncOpenAI

    cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    manifest = "\n".join(
        f"- {nombre}: {detalle['descripcion']} Argumentos requeridos: "
        f"{', '.join(detalle['requeridos']) or 'ninguno'}."
        for nombre, detalle in _TOOL_MANIFEST.items()
    )
    respuesta = await cliente.responses.parse(
        model=settings.llm_model_fast,
        input=(
            "Eres un planificador de una ludoteca. Devuelve solo un plan de tools de solo "
            "lectura. No calcules ni respondas al usuario. Usa exclusivamente este manifiesto:\n"
            f"{manifest}\nFormulaciones naturales: {_EJEMPLOS_INTENT}\n"
            "Para un juego, el argumento nombre debe conservar exactamente el título citado por "
            "la persona, sin traducirlo ni sustituirlo por otro título. "
            f"Contexto de colección e historial reciente: {resumen}\n"
            + (
                f"El intento anterior no fue válido: {error_validacion}. Corrige el plan.\n"
                if error_validacion
                else ""
            )
            + f"Pregunta: {mensaje}"
        ),
        text_format=_PlanRespuestaLlm,
    )
    parsed = respuesta.output_parsed
    if parsed is None:
        return None
    return PlanLlm(
        intent=parsed.intent,
        steps=[
            PasoPlan(
                id=paso.id,
                tool=paso.tool,
                args=paso.args.model_dump(exclude_none=True),
                depends_on=paso.depends_on,
            )
            for paso in parsed.steps
        ],
    )


async def _resolver(
    repo: CatalogoRepository, nombre: str | None, game_id: str | None, settings: Settings
) -> tuple[str, tuple[Game, ...]]:
    if game_id:
        juego = await repo.obtener_juego(game_id)
        return ("encontrado", (juego,)) if juego else ("no_encontrado", ())
    nombre = nombre_valido(nombre)
    if nombre is None:
        return "no_encontrado", ()
    juegos = await repo.todos_los_juegos()
    consulta_normalizada = normalizar_nombre(nombre)
    exactos = tuple(
        juego
        for juego in juegos
        if (titulo_normalizado := normalizar_nombre(juego.nombre))
        and titulo_normalizado == consulta_normalizada
    )
    titulos_cortos = tuple(
        juego
        for juego in juegos
        if (titulo_corto_normalizado := normalizar_nombre(juego.nombre.split(":", maxsplit=1)[0]))
        and titulo_corto_normalizado == consulta_normalizada
    )
    candidatos_directos = tuple({juego.id: juego for juego in (*exactos, *titulos_cortos)}.values())
    if len(candidatos_directos) == 1:
        return "encontrado", candidatos_directos
    if candidatos_directos:
        ordenados = tuple(
            sorted(candidatos_directos, key=lambda juego: juego.users_rated or 0, reverse=True)
        )
        if (ordenados[0].users_rated or 0) >= 5 * (ordenados[1].users_rated or 0):
            return "encontrado", (ordenados[0],)
        return "ambiguo", ordenados[:5]
    return "no_encontrado", ()


async def _resolver_con_traduccion(
    repo: CatalogoRepository, nombre: str | None, game_id: str | None, settings: Settings
) -> tuple[str, tuple[Game, ...], dict[str, str] | None, list[str], dict[str, Any] | None]:
    estado, juegos = await _resolver(repo, nombre, game_id, settings)
    nombre = nombre_valido(nombre)
    if estado != "no_encontrado" or game_id or nombre is None or not settings.llm_active:
        return estado, juegos, None, [], None
    from openai import AsyncOpenAI

    try:
        cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        salida = await cliente.responses.parse(
            model=settings.llm_model_fast,
            input=(
                "Un usuario hispanohablante busca un juego de mesa llamado «"
                + nombre
                + "». ¿Qué juegos de mesa crees que sean, con su título original en inglés? "
                "Dame hasta 3 opciones, de la más a la menos probable. No expliques nada."
            ),
            text_format=_TitulosTraducidosLlm,
        )
        titulos = salida.output_parsed.titulos[:3] if salida.output_parsed else []
    except Exception as error:  # noqa: BLE001
        return (
            estado,
            juegos,
            None,
            [],
            {
                "llm_called": True,
                "titulos": [],
                "error": str(error)[:300],
            },
        )
    juegos_catalogo = await repo.todos_los_juegos()
    candidatos: list[Game] = []
    coincidencias: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for titulo_original in titulos:
        titulo = nombre_valido(titulo_original)
        if titulo is None:
            continue
        consulta = normalizar_nombre(titulo)
        encontrados = [
            juego
            for juego in juegos_catalogo
            if consulta
            in {normalizar_nombre(juego.nombre), normalizar_nombre(juego.nombre.split(":", 1)[0])}
        ]
        if not encontrados and consulta:
            mejor = max(
                (
                    (fuzz.WRatio(consulta, normalizar_nombre(juego.nombre)), juego)
                    for juego in juegos_catalogo
                ),
                default=None,
                key=lambda item: (item[0], item[1].users_rated or 0),
            )
            encontrados = [mejor[1]] if mejor and mejor[0] >= 85 else []
        coincidencias.append(
            {"propuesta": titulo, "coincidencias": [juego.id for juego in encontrados]}
        )
        for juego in encontrados:
            if juego.id not in vistos:
                vistos.add(juego.id)
                candidatos.append(juego)
    traza = {"llm_called": True, "titulos": titulos, "coincidencias": coincidencias}
    return (
        ("ambiguo", tuple(candidatos), None, titulos, traza)
        if candidatos
        else (estado, (), None, titulos, traza)
    )


async def _validar_plan_con_juego(
    plan: PlanLlm,
    mensaje: str,
    repo: CatalogoRepository,
    coleccion: list[Game],
    settings: Settings,
) -> PlanLlm:
    if any(paso.tool in {"evaluar_compra", "detalle_juego"} for paso in plan.steps):
        return plan
    nombre = _extraer_nombre_juego(mensaje)
    if nombre is None:
        return plan
    estado, juegos = await _resolver(repo, nombre, None, settings)
    if estado != "encontrado":
        return plan
    juego = juegos[0]
    consulta_normalizada = normalizar_nombre(nombre)
    titulo_normalizado = normalizar_nombre(juego.nombre.split(":", maxsplit=1)[0])
    if consulta_normalizada not in {normalizar_nombre(juego.nombre), titulo_normalizado}:
        return plan
    en_coleccion = any(item.id == juego.id for item in coleccion)
    tool = "detalle_juego" if en_coleccion else "evaluar_compra"
    intent = "detalle_juego" if en_coleccion else "evaluar_compra"
    return PlanLlm(intent=intent, steps=[PasoPlan(id="1", tool=tool, args={"game_id": juego.id})])


async def _ejecutar_tool(
    nombre: str,
    args: dict[str, Any],
    session: AsyncSession,
    user_id: str,
    perfil: Any,
    request: Any,
    settings: Settings,
) -> dict[str, Any]:
    artefactos = _artefactos(request)
    repo = CatalogoRepository(session)
    coleccion = await _coleccion(session, type("Usuario", (), {"id": user_id})(), perfil.id)
    if nombre == "ver_coleccion":
        return {
            "juegos": [_juego_detalle(juego).model_dump(mode="json") for juego in coleccion],
            "total": len(coleccion),
        }
    if nombre == "que_me_falta":
        resultado = cobertura(artefactos, coleccion, perfil.metas)
        return {
            "ejes": {
                eje: {
                    "faltantes": list(valor.faltantes),
                    "debiles": valor.debiles,
                    "cubiertos": list(valor.cubiertos),
                }
                for eje, valor in resultado.ejes.items()
            }
        }
    if nombre == "que_saco_hoy":
        jugadores, minutos = int(args.get("jugadores", 4)), float(args.get("minutos", 60))
        juegos = que_saco_hoy(coleccion, jugadores, minutos, args.get("edad_minima"))
        return {
            "juegos": [
                {
                    **_juego(juego, artefactos).model_dump(mode="json"),
                    "nivel_ajuste": "ideal" if ideal else "funciona",
                }
                for juego, ideal in juegos
            ]
        }
    if nombre == "que_compro":
        candidatos = [
            juego
            for juego in await repo.todos_los_juegos()
            if not juego_excluido_del_plan(perfil.id, juego.nombre, juego.mechanics or [])
        ]
        planes = opciones_compra(
            artefactos,
            coleccion,
            candidatos,
            n=int(args.get("n", 5)),
            modo="juego",
            average_min=float(args.get("average_min", 0)),
            users_rated_min=int(args.get("users_rated_min", settings.users_rated_min)),
            metas=perfil.metas,
        )
        return {
            "opciones": [
                {
                    "etiqueta": etiqueta,
                    "juegos": [
                        _juego(juego, artefactos).model_dump(mode="json") for juego in plan.juegos
                    ],
                    "valor_cubierto": plan.valor_cubierto,
                    "valor_pendiente": plan.valor_pendiente,
                }
                for etiqueta, plan in zip(("A", "B", "C"), planes, strict=True)
            ]
        }
    resolucion = await _resolver_con_traduccion(
        repo, args.get("nombre"), args.get("game_id"), settings
    )
    estado, juegos_resueltos, interpretado_como, sugerencias_traduccion, traza_traduccion = (
        resolucion
    )
    if estado != "encontrado":
        return {
            "estado": estado,
            "candidatos": [
                {"id": juego.id, "nombre": juego.nombre, "imagen_url": juego.image_url}
                for juego in juegos_resueltos
            ],
            "sugerencias_traduccion": sugerencias_traduccion,
            "traza_traduccion": traza_traduccion,
        }
    juego = juegos_resueltos[0]
    if nombre == "detalle_juego":
        return {
            "estado": "encontrado",
            "juego": _juego_detalle(juego).model_dump(mode="json"),
            "ya_en_coleccion": any(item.id == juego.id for item in coleccion),
            "interpretado_como": interpretado_como,
            "sugerencias_traduccion": sugerencias_traduccion,
            "traza_traduccion": traza_traduccion,
        }
    sin_candidato = [item for item in coleccion if item.id != juego.id]
    if any(item.id == juego.id for item in coleccion):
        from app.api.v1.engine import _impacto_cobertura

        return {
            "estado": "encontrado",
            "ya_en_coleccion": True,
            "juego": _juego(juego, artefactos).model_dump(mode="json"),
            "impacto_venta": _impacto_cobertura(
                artefactos, coleccion, sin_candidato, perfil.metas
            ).model_dump(mode="json"),
            "interpretado_como": interpretado_como,
            "sugerencias_traduccion": sugerencias_traduccion,
            "traza_traduccion": traza_traduccion,
        }
    veredicto, cercano, similitud, exacta = evaluar_redundancia(
        artefactos, juego, sin_candidato, perfil.metas
    )
    huecos = {
        (eje, nivel): "faltante"
        for eje, eje_cobertura in cobertura(artefactos, sin_candidato, perfil.metas).ejes.items()
        for nivel in eje_cobertura.faltantes
    }
    return {
        "estado": "encontrado",
        "veredicto": veredicto,
        "juego": _juego(juego, artefactos, huecos).model_dump(mode="json"),
        "juego_mas_parecido": _juego(cercano, artefactos).model_dump(mode="json")
        if cercano
        else None,
        "similitud": similitud.__dict__ if similitud else None,
        "regla_exacta": _motivo_regla_exacta(juego, cercano) if exacta and cercano else None,
        "niveles_que_cubre": [nivel.model_dump() for nivel in _niveles(juego, artefactos, huecos)],
        "interpretado_como": interpretado_como,
        "sugerencias_traduccion": sugerencias_traduccion,
        "traza_traduccion": traza_traduccion,
    }


def _motivo_regla_exacta(juego: Game, parecido: Game) -> str:
    if set(juego.product_line or []) & set(parecido.product_line or []):
        return "misma_linea_de_producto"
    return "reimplementa"


def _narrar(intent: str, resultados: list[dict[str, Any]]) -> str:
    if intent == "reglas":
        return "Las consultas de reglas llegarán en una versión próxima."
    if intent == "fuera_de_dominio":
        return "Mi experiencia se limita al análisis y recomendación de juegos de mesa."
    if intent == "general" and not resultados:
        return "**Necesito el nombre del juego**\n\nEscribe el título que quieres consultar."
    resultado = resultados[0] if resultados else {}
    if resultado.get("estado") == "ambiguo":
        return (
            "**Necesito confirmar el juego**\n\n- 🎲 Encontré títulos parecidos en el catálogo.\n"
            "- Elige una sugerencia o escribe el nombre en inglés.\n\n"
            "💡 ¿Quieres evaluar otro juego?"
        )
    if resultado.get("estado") == "no_encontrado":
        return (
            "**No encontré ese juego**\n\n"
            "- 🎲 No hay una coincidencia segura en el catálogo local.\n"
            "- Escribe el nombre en inglés para intentarlo de nuevo.\n\n"
            "💡 ¿Quieres evaluar otro juego?"
        )
    if intent == "evaluar_compra":
        juego, similar = resultado["juego"], resultado.get("juego_mas_parecido")
        interpretacion = resultado.get("interpretado_como")
        prefijo = (
            f"Interpreté «{interpretacion['buscado']}» como «{interpretacion['resuelto']}».\n\n"
            if interpretacion
            else ""
        )
        if resultado.get("ya_en_coleccion"):
            return (
                prefijo + f"**{juego['nombre']}** ya está en tu colección.\n\n"
                "- 📦 La tarjeta muestra el impacto de simular su venta.\n"
                "- 🧩 Así puedes revisar la cobertura que perderías.\n\n"
                "💡 ¿Quieres simular la venta de otro juego?"
            )
        veredictos = {
            "redundante": "Redundante",
            "parecido_pero_cubre_hueco": "Aporta un hueco",
            "complementario": "Complementario",
        }
        texto = prefijo + f"**{veredictos.get(resultado['veredicto'], 'Evaluado')}**"
        texto += f"\n\n- **{juego['nombre']}** está evaluado para tu colección."
        if resultado.get("regla_exacta") == "misma_linea_de_producto" and similar:
            texto += f"\n- Comparte línea de producto con **{similar['nombre']}**."
        elif resultado.get("regla_exacta") == "reimplementa" and similar:
            texto += f"\n- Reimplementa **{similar['nombre']}**."
        if similar and resultado.get("similitud"):
            similitud = resultado["similitud"]
            texto += f"\n- 🔁 Se parece a **{similar['nombre']}**."
            texto += f"\n- **Similitud total {similitud['total']:.2f}**."
        return texto + "\n\n💡 ¿Quieres evaluar otro juego?"
    if intent == "que_me_falta":
        faltantes = [
            f"{eje}: {', '.join(valor['faltantes'])}"
            for eje, valor in resultado["ejes"].items()
            if valor["faltantes"]
        ]
        debiles = [
            f"{eje}: {', '.join(valor['debiles'])}"
            for eje, valor in resultado["ejes"].items()
            if valor["debiles"]
        ]
        return (
            "**Huecos de la colección**\n\n**Faltantes:** "
            + ("; ".join(faltantes) or "ninguno.")
            + "\n\n**Débiles:** "
            + ("; ".join(debiles) or "ninguno.")
        )
    if intent == "que_compro":
        opciones = [
            f"**{opcion['etiqueta']}**: "
            f"{', '.join(juego['nombre'] for juego in opcion['juegos']) or 'sin candidatos'} "
            f"(valor cubierto: {opcion['valor_cubierto']:.2f})"
            for opcion in resultado["opciones"]
        ]
        return (
            "Planes por número de juegos:\n\n"
            + "\n".join(opciones)
            + "\n\n¿Quieres evaluar uno de estos juegos?"
        )
    if intent == "que_saco_hoy":
        return "Para esta mesa: " + (
            ", ".join(juego["nombre"] for juego in resultado["juegos"])
            or "no hay juegos que pasen los filtros."
        )
    if intent == "coleccion":
        return f"Tu colección activa tiene {resultado['total']} juegos."
    interpretacion = resultado.get("interpretado_como")
    prefijo = (
        f"Interpreté «{interpretacion['buscado']}» como «{interpretacion['resuelto']}».\n\n"
        if interpretacion
        else ""
    )
    en_coleccion = resultado.get("ya_en_coleccion")
    estado = "📦 ya está en tu colección" if en_coleccion else "está disponible en el catálogo"
    return (
        prefijo + f"**{resultado['juego']['nombre']}** {estado}.\n\n"
        "- 🎲 Consulta los datos principales en la tarjeta.\n\n"
        "💡 ¿Quieres evaluar otro juego?"
    )


def _sugerencia_final(intent: str, resultados: list[dict[str, Any]]) -> str:
    resultado = resultados[0] if resultados else {}
    if resultado.get("ya_en_coleccion"):
        return "💡 ¿Quieres simular qué pasaría si lo vendes?"
    return {
        "evaluar_compra": "💡 ¿Quieres ver qué le falta a tu colección?",
        "que_me_falta": "💡 ¿Armamos un plan de 3 juegos para cubrir esos huecos?",
        "que_compro": "💡 ¿Quieres evaluar otro juego?",
        "que_saco_hoy": "💡 ¿Quieres probar otra mesa?",
        "detalle_juego": "💡 ¿Quieres evaluar otro juego?",
        "coleccion": "💡 ¿Quieres ver qué le falta a tu colección?",
    }.get(intent, "💡 ¿Quieres evaluar otro juego?")


def _con_sugerencia_final(respuesta: str, intent: str, resultados: list[dict[str, Any]]) -> str:
    lineas = [
        linea
        for linea in respuesta.splitlines()
        if not linea.lstrip().startswith("💡") and "?" not in linea and "¿" not in linea
    ]
    return "\n".join(lineas).rstrip() + "\n\n" + _sugerencia_final(intent, resultados)


def _sanear_negritas(respuesta: str) -> str:
    """Evita que una línea con markdown incompleto afecte el resto de la respuesta."""
    return "\n".join(
        linea.replace("**", "") if linea.count("**") % 2 else linea
        for linea in respuesta.splitlines()
    )


def _emoji_resultado(intent: str, resultados: list[dict[str, Any]]) -> str:
    resultado = resultados[0] if resultados else {}
    if resultado.get("estado") in {"no_encontrado", "ambiguo"}:
        return "🎲"
    if resultado.get("ya_en_coleccion"):
        return "📦"
    if resultado.get("veredicto") == "redundante":
        return "⚠️"
    if resultado.get("veredicto") == "parecido":
        return "🔁"
    if resultado.get("veredicto") in {"aporta", "parecido_pero_cubre_hueco", "complementario"}:
        return "✅"
    return {"que_me_falta": "🧩", "que_compro": "🛒"}.get(intent, "🎲")


def _presentar_respuesta(respuesta: str, intent: str, resultados: list[dict[str, Any]]) -> str:
    respuesta = _sanear_negritas(respuesta).strip()
    return (
        f"{_emoji_resultado(intent, resultados)} {respuesta}"
        if respuesta
        else _emoji_resultado(intent, resultados)
    )


def _formatear_resultados_narrador(resultados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meses = {
        "Jan": "ene",
        "Feb": "feb",
        "Mar": "mar",
        "Apr": "abr",
        "May": "may",
        "Jun": "jun",
        "Jul": "jul",
        "Aug": "ago",
        "Sep": "sep",
        "Oct": "oct",
        "Nov": "nov",
        "Dec": "dic",
    }

    def recorrer(valor: Any, clave: str | None = None, es_similitud: bool = False) -> Any:
        if isinstance(valor, dict):
            return {
                nombre: recorrer(item, nombre, es_similitud or nombre == "similitud")
                for nombre, item in valor.items()
            }
        if isinstance(valor, list):
            return [recorrer(item, clave, es_similitud) for item in valor]
        if clave == "precio_usd" and isinstance(valor, (int, float)):
            return f"USD {valor:.2f}"
        if clave == "fecha_precio" and isinstance(valor, str):
            try:
                fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
                texto = fecha.strftime("%-d %b %Y").replace(".", "")
                for origen, destino in meses.items():
                    texto = texto.replace(origen, destino)
                return texto
            except ValueError:
                return valor
        if clave == "peso" and isinstance(valor, (int, float)):
            return f"{valor:.1f}"
        if (
            es_similitud
            and clave in {"total", "mecanicas", "ocasion", "interaccion", "tematica"}
            and isinstance(valor, (int, float))
        ):
            return f"{valor:.2f}"
        return valor

    return [recorrer(resultado) for resultado in resultados]


def _valores(resultados: list[dict[str, Any]]) -> list[Any]:
    valores: list[Any] = []

    def recorrer(valor: Any) -> None:
        if isinstance(valor, dict):
            for item in valor.values():
                recorrer(item)
        elif isinstance(valor, list):
            for item in valor:
                recorrer(item)
        else:
            valores.append(valor)

    for resultado in resultados:
        recorrer(resultado)
    return valores


def _encontrar_banderas(resultados: list[dict[str, Any]]) -> bool:
    banderas = {
        "weight_imputado",
        "weight_pocos_votos",
        "duracion_imputada",
        "jugadores_imputados",
    }

    def recorrer(valor: Any) -> bool:
        if isinstance(valor, dict):
            return any(clave in banderas and item is True for clave, item in valor.items()) or any(
                recorrer(item) for item in valor.values()
            )
        if isinstance(valor, list):
            return any(recorrer(item) for item in valor)
        return False

    return any(recorrer(resultado) for resultado in resultados)


def _fuentes_web(resultados: list[dict[str, Any]]) -> set[str]:
    fuentes: set[str] = set()

    def recorrer(valor: Any) -> None:
        if isinstance(valor, dict):
            for clave, item in valor.items():
                if clave in {"fuentes", "url", "source_url"}:
                    recorrer_fuente(item)
                recorrer(item)
        elif isinstance(valor, list):
            for item in valor:
                recorrer(item)

    def recorrer_fuente(valor: Any) -> None:
        if isinstance(valor, str) and valor.startswith(("https://", "http://")):
            fuentes.add(valor)
        elif isinstance(valor, dict):
            for item in valor.values():
                recorrer_fuente(item)
        elif isinstance(valor, list):
            for item in valor:
                recorrer_fuente(item)

    for resultado in resultados:
        recorrer(resultado)
    return fuentes


def _origen_web(resultados: list[dict[str, Any]]) -> bool:
    return any(valor == "web" for valor in _valores(resultados))


def _numeros_permitidos(resultados: list[dict[str, Any]]) -> list[float]:
    permitidos: list[float] = []

    def registrar(valor: Any) -> None:
        if isinstance(valor, bool):
            return
        if isinstance(valor, (int, float)):
            permitidos.append(float(valor))
        elif isinstance(valor, str):
            for numero in re.findall(r"(?<![\w.])-?\d+(?:[.,]\d+)?", valor):
                permitidos.append(float(numero.replace(",", ".")))

    def recorrer(valor: Any) -> None:
        if isinstance(valor, dict):
            for clave, item in valor.items():
                registrar(clave)
                recorrer(item)
        elif isinstance(valor, list):
            for item in valor:
                recorrer(item)
        else:
            registrar(valor)

    for resultado in resultados:
        recorrer(resultado)
    return permitidos


def _precio_tiene_fuente(respuesta: str) -> bool:
    texto = respuesta.lower()
    if "precio que capturaste" in texto:
        return True
    tiene_fecha = re.search(r"\b20\d{2}-\d{2}-\d{2}\b|\b\d{1,2}\s+[a-záéíóú]+\s+20\d{2}\b", texto)
    return "boardgameprices" in texto and bool(tiene_fecha)


def _valores_de_clave(resultados: list[dict[str, Any]], clave: str) -> set[str]:
    valores: set[str] = set()

    def recorrer(valor: Any) -> None:
        if isinstance(valor, dict):
            for nombre, item in valor.items():
                if nombre == clave and isinstance(item, str):
                    valores.add(item.lower())
                recorrer(item)
        elif isinstance(valor, list):
            for item in valor:
                recorrer(item)

    for resultado in resultados:
        recorrer(resultado)
    return valores


def _criticar_niveles(respuesta: str, resultados: list[dict[str, Any]]) -> list[str]:
    hallazgos: list[str] = []
    patrones = {
        "peso": (
            r"\bpeso(?:\s*/\s*complejidad)?\s*(?:es|:)?\s*(ligero|medio|pesado)",
            "nivel_peso",
        ),
        "interacción": (
            r"\binteracci[oó]n\s*(?:es|:)?\s*(directa|indirecta|ninguna)",
            "nivel_interaccion",
        ),
        "duración": (
            r"\bduraci[oó]n\s*(?:es|:)?\s*(corta|media|larga)",
            "nivel_duracion",
        ),
    }
    texto = respuesta.lower()
    for etiqueta, (patron, clave) in patrones.items():
        permitidos = _valores_de_clave(resultados, clave)
        if not permitidos:
            continue
        for valor in re.findall(patron, texto):
            if valor not in permitidos:
                hallazgos.append(f"El nivel de {etiqueta} {valor} no aparece en los resultados.")
                break
    return hallazgos


def _criticar_determinista(respuesta: str, resultados: list[dict[str, Any]]) -> list[str]:
    """Aplica las reglas de transparencia antes de gastar una llamada del critic."""
    hallazgos: list[str] = []
    if re.search(r"`[^`]+`", respuesta):
        hallazgos.append(
            "La respuesta no puede mencionar nombres internos entre comillas invertidas."
        )
    if any(funcion in respuesta.lower() for funcion in _FUNCIONES_NO_DISPONIBLES):
        hallazgos.append(
            "La respuesta menciona una función que no existe en el manifiesto de tools."
        )
    if re.search(r"\b[\wáéíóúñ]+_[\wáéíóúñ]+\b", respuesta, re.IGNORECASE):
        hallazgos.append("La respuesta no puede mostrar identificadores internos con guion bajo.")
    preguntas = [linea for linea in respuesta.splitlines() if "?" in linea or "¿" in linea]
    if any(not linea.lstrip().startswith("💡") for linea in preguntas):
        hallazgos.append(
            "Solo la sugerencia final determinista puede hacer una pregunta de seguimiento."
        )
    if "redundante" in respuesta.lower() and not any(
        item.get("veredicto") == "redundante" for item in resultados
    ):
        hallazgos.append("La respuesta llama redundante a un juego sin respaldo de una tool.")
    if _encontrar_banderas(resultados) and "estimad" not in respuesta.lower():
        hallazgos.append("Falta indicar que hay datos estimados.")
    for item in resultados:
        interpretado = item.get("interpretado_como")
        texto_interpretacion = (
            f"Interpreté «{interpretado['buscado']}» como «{interpretado['resuelto']}»"
            if interpretado
            else ""
        )
        if texto_interpretacion and texto_interpretacion not in respuesta:
            hallazgos.append("Falta explicar cómo se interpretó el título en español.")
    fuentes = _fuentes_web(resultados)
    if _origen_web(resultados) and (
        "web" not in respuesta.lower() or not any(fuente in respuesta for fuente in fuentes)
    ):
        hallazgos.append("Falta indicar el origen web y citar una fuente.")
    menciona_precio = re.search(r"(?:\$\s*\d|\b\d+(?:[.,]\d+)?\s*(?:usd|dólares))", respuesta, re.I)
    if menciona_precio and not _precio_tiene_fuente(respuesta):
        hallazgos.append(
            "Todo precio debe incluir BoardGamePrices con fecha o indicar que lo capturaste."
        )
    if any(item.get("estado") in {"ambiguo", "no_encontrado"} for item in resultados) and any(
        palabra in respuesta.lower()
        for palabra in ("veredicto", "similitud", "redundante", "aporta")
    ):
        hallazgos.append(
            "No se puede presentar una evaluación para un resultado ambiguo o no encontrado."
        )
    for item in resultados:
        if item.get("regla_exacta") and not any(
            frase in respuesta.lower()
            for frase in ("reimplement", "línea de producto", "linea de producto")
        ):
            hallazgos.append(
                "Falta explicar la regla exacta por reimplementación o línea de producto."
            )
        if "opciones" in item:
            for opcion in item["opciones"]:
                etiqueta = opcion["etiqueta"]
                if etiqueta not in respuesta or not re.search(
                    rf"{re.escape(etiqueta)}[^\n]*valor cubierto", respuesta, re.I
                ):
                    hallazgos.append(f"El plan debe presentar {etiqueta} con su valor cubierto.")
                    break
            recomendada = re.search(r"opci[oó]n\s+([ABC])\s+recomendad", respuesta, re.I)
            if recomendada and recomendada.group(1).upper() != "A":
                hallazgos.append("Solo la opción A puede llamarse recomendada.")
        if "ejes" in item and (
            "faltantes" not in respuesta.lower() or "débiles" not in respuesta.lower()
        ):
            hallazgos.append("La respuesta de cobertura debe incluir faltantes y débiles.")
    hallazgos.extend(_criticar_niveles(respuesta, resultados))

    permitidos = _numeros_permitidos(resultados)
    for numero in re.findall(r"(?<![\w.])-?\d+(?:[.,]\d+)?%?", respuesta):
        valor = float(numero.rstrip("%").replace(",", "."))
        candidatos = [valor] if not numero.endswith("%") else [valor, valor / 100]
        if not any(
            any(
                abs(candidato - permitido) <= max(0.01, abs(permitido) * 0.015)
                for permitido in permitidos
            )
            for candidato in candidatos
        ):
            hallazgos.append(f"La cifra {numero} no aparece en los resultados de las tools.")
            break
    return hallazgos


async def _narrar_llm(
    settings: Settings,
    resultados: list[dict[str, Any]],
    pregunta: str = "",
    retroalimentacion: list[str | dict[str, str]] | None = None,
) -> str:
    """Redacta exclusivamente sobre los resultados serializados de las tools."""
    from openai import AsyncOpenAI

    instrucciones = (
        "Eres el narrador de Wise Dice. Responde en español y markdown breve, sin emojis. "
        "La primera línea "
        "debe contener la respuesta o veredicto principal en negrita, seguida de dos a cuatro "
        "viñetas cortas y una última línea que proponga solo una acción del "
        "manifiesto: evaluar otro juego, ver qué falta, plan de compra, modo mesa o simular venta. "
        "No uses emojis. Usa negritas solo para juegos, el veredicto y números clave, con una "
        "negrita como máximo por viñeta. No pegues URLs. No enumeres mecánicas o categorías "
        "crudas: si hace falta, "
        "usa familias en español. Para detalle_juego, limita el texto al resumen: la tarjeta "
        "contiene portada, datos, precio y enlace. Si aparece interpretado_como, escribe siempre "
        "Interpreté «X» como «Y». "
        "Solo puedes afirmar hechos presentes literalmente en los resultados de las tools. "
        "No uses conocimiento propio para describir jugabilidad, sensaciones, géneros ni "
        "características: están prohibidos términos como eurogame, estructura de turno u "
        "objetivos ocultos si no aparecen en los resultados. No inventes cifras, atributos, "
        "fuentes ni recomendaciones. Para un veredicto, explica su motivo real: si regla_exacta "
        "es reimplementa o misma_linea_de_producto, menciónalo; en otro caso indica similitud "
        "total y los bloques disponibles. Nunca llames afinidad o match a la similitud. En un "
        "plan de compra, presenta A, B y C con su valor cubierto, y solo puedes llamar "
        "recomendada a la opción A. En que_me_falta incluye faltantes y débiles. Nunca menciones "
        "funciones que no estén en el manifiesto de tools, nombres internos entre comillas "
        "invertidas, ni precio o presupuesto salvo que el resultado incluya ese precio. Si los "
        "resultados no responden la pregunta, dilo en una línea y haz una sola pregunta concreta."
    )
    if retroalimentacion:
        hallazgos = [
            hallazgo
            if isinstance(hallazgo, str)
            else f"{hallazgo.get('categoria', 'hallazgo')}: {hallazgo.get('detalle', '')}"
            for hallazgo in retroalimentacion
        ]
        instrucciones += " Corrige estos incumplimientos: " + " ".join(hallazgos)
    cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    respuesta = await cliente.responses.create(
        model=settings.llm_model,
        input=[
            {"role": "system", "content": instrucciones},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "pregunta": pregunta,
                        "resultados_tools": _formatear_resultados_narrador(resultados),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        temperature=settings.llm_temperature,
        max_output_tokens=1200,
    )
    texto = (respuesta.output_text or "").strip()
    if not texto:
        raise ValueError("El narrador LLM devolvió una respuesta vacía.")
    return texto


async def _criticar_llm(
    settings: Settings, respuesta: str, resultados: list[dict[str, Any]], pregunta: str = ""
) -> list[dict[str, str]]:
    """Segunda barrera: detecta solo afirmaciones sin respaldo de las tools."""
    from openai import AsyncOpenAI

    cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    salida = await cliente.responses.parse(
        model=settings.llm_model_fast,
        input=[
            {
                "role": "system",
                "content": (
                    "Eres el critic de Wise Dice. Contrasta cada afirmación de la respuesta "
                    "con los resultados de las tools. Revisa cifras sin fuente, mecánicas o "
                    "atributos "
                    "ausentes, juegos no incluidos y recomendaciones sin respaldo. No uses "
                    "conocimiento general: que un juego o atributo sea conocido no es evidencia. "
                    "Una comparación o descripción solo está respaldada si los resultados "
                    "contienen esa información. Una recomendación solo está respaldada si se "
                    "limita a los juegos y razones que una tool devuelve. Si una afirmación no se "
                    "puede vincular a los resultados, crea un hallazgo; ante la duda, recházala. "
                    "Marca cualquier afirmación descriptiva sobre un juego que no figure en los "
                    "resultados de las tools, incluida jugabilidad, sensaciones o características. "
                    "Marca también si la respuesta no contesta la pregunta del usuario. "
                    "Devuelve hallazgos "
                    "con categoria y detalle, usando solo estas categorías: cifra_sin_fuente, "
                    "juego_o_atributo_no_disponible o recomendacion_sin_respaldo. Devuelve ok=true "
                    "solo si todas las afirmaciones están respaldadas. No inventes hallazgos."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "pregunta": pregunta,
                        "resultados_tools": resultados,
                        "respuesta": respuesta,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        text_format=_CriticaRespuestaLlm,
    )
    critica = salida.output_parsed
    if critica is None:
        raise ValueError("El critic LLM devolvió una respuesta vacía.")
    hallazgos = [hallazgo.model_dump() for hallazgo in critica.hallazgos]
    if critica.ok:
        return []
    return hallazgos or [
        {
            "categoria": "recomendacion_sin_respaldo",
            "detalle": "El critic LLM rechazó la respuesta sin más detalle.",
        }
    ]


async def responder(
    session: AsyncSession, request: Any, user: Any, perfil: Any, solicitud: Any, settings: Settings
) -> ChatRespuesta:
    chat_session = (
        await session.get(ChatSession, solicitud.session_id) if solicitud.session_id else None
    )
    if chat_session is None:
        chat_session = ChatSession(user_id=user.id, titulo=solicitud.mensaje[:120])
        session.add(chat_session)
        await session.flush()
    coleccion_activa = await _coleccion(session, user, perfil.id)
    ultimos_runs = (
        await session.scalars(
            select(AgentRun)
            .where(AgentRun.session_id == chat_session.id)
            .order_by(AgentRun.creado_en.desc())
            .limit(3)
        )
    ).all()
    historial = "; ".join(
        f"{run.pregunta} [{run.intent or 'sin intent'}]" for run in reversed(ultimos_runs)
    )
    resumen = (
        ", ".join(juego.nombre for juego in coleccion_activa) + f". Últimos turnos: {historial}"
    )
    es_continuacion_en_ingles = bool(
        re.match(r"^el nombre en ingl[eé]s es:\s*.+$", solicitud.mensaje, re.IGNORECASE)
    )
    plan_llm: PlanLlm | None = None
    planner_error: str | None = None
    planner_llm_used = False
    planner_reintentado = False
    if settings.llm_active and not es_continuacion_en_ingles:
        try:
            plan_llm = await _plan_llm(settings, solicitud.mensaje, resumen)
            planner_llm_used = plan_llm is not None
            if (
                plan_llm is not None
                and _validar_plan(plan_llm, settings.llm_max_plan_steps) is None
            ):
                planner_reintentado = True
                planner_error = (
                    "El plan debe incluir un nombre de juego válido o un game_id válido."
                )
                plan_llm = await _plan_llm(settings, solicitud.mensaje, resumen, planner_error)
                planner_llm_used = planner_llm_used or plan_llm is not None
        except ValueError as error:
            planner_reintentado = True
            planner_error = str(error)[:300]
            try:
                plan_llm = await _plan_llm(settings, solicitud.mensaje, resumen, planner_error)
                planner_llm_used = planner_llm_used or plan_llm is not None
            except Exception as retry_error:  # noqa: BLE001
                planner_error = str(retry_error)[:300]
                plan_llm = None
        except Exception as error:  # noqa: BLE001
            planner_error = str(error)[:300]
            plan_llm = None
    plan = _validar_plan(plan_llm, settings.llm_max_plan_steps)
    llm_used = plan is not None
    plan = plan or _plan_determinista(
        solicitud.mensaje,
        solicitud.game_id,
        chat_session.juego_en_foco_id,
        chat_session.intent_pendiente,
    )
    if _validar_plan(plan, settings.llm_max_plan_steps) is None:
        plan = PlanLlm(intent="general")
    plan = await _validar_plan_con_juego(
        plan,
        solicitud.mensaje,
        CatalogoRepository(session),
        coleccion_activa,
        settings,
    )
    run = AgentRun(
        user_id=user.id,
        session_id=chat_session.id,
        pregunta=solicitud.mensaje,
        intent=plan.intent,
        plan={"steps": [paso.model_dump() for paso in plan.steps]},
        modelo=settings.llm_model_fast if llm_used else None,
    )
    session.add_all(
        [
            run,
            ChatMessage(
                user_id=user.id,
                session_id=chat_session.id,
                role="user",
                contenido=solicitud.mensaje,
            ),
        ]
    )
    await session.flush()
    await session.commit()  # El plan queda durable antes de cualquier tool.
    if settings.llm_active and not es_continuacion_en_ingles:
        session.add(
            AgentStep(
                user_id=user.id,
                run_id=run.id,
                agent_name="planner",
                estado="fallback" if planner_error else "ok",
                output={
                    "llm_used": planner_llm_used,
                    "modelo": settings.llm_model_fast,
                    "reintentado": planner_reintentado,
                },
                error_mensaje=planner_error,
            )
        )
    resultados: list[dict[str, Any]] = []
    pasos_respuesta: list[PasoPlan] = []
    for nivel in _niveles_plan(plan.steps):
        for paso in nivel:
            resultado = await _ejecutar_tool(
                paso.tool, paso.args, session, user.id, perfil, request, settings
            )
            resultados.append(resultado)
            pasos_respuesta.append(paso.model_copy(update={"estado": "completado"}))
            session.add_all(
                [
                    AgentStep(
                        user_id=user.id,
                        run_id=run.id,
                        agent_name="tool",
                        step_id=paso.id,
                        output=resultado,
                    ),
                    ToolCall(
                        user_id=user.id,
                        run_id=run.id,
                        step_id=paso.id,
                        tool_name=paso.tool,
                        argumentos=paso.args,
                        resultado=resultado,
                    ),
                ]
            )
            traza_traduccion = resultado.get("traza_traduccion")
            if isinstance(traza_traduccion, dict):
                session.add(
                    AgentStep(
                        user_id=user.id,
                        run_id=run.id,
                        agent_name="translation",
                        estado="fallback" if traza_traduccion.get("error") else "ok",
                        output={"modelo": settings.llm_model_fast, **traza_traduccion},
                        error_mensaje=traza_traduccion.get("error"),
                    )
                )
    answer = _narrar(plan.intent, resultados)
    narrator_llm_used = False
    critic_findings: list[str | dict[str, str]] = []
    critic_attempts = 0
    trazas: list[tuple[str, str, dict[str, Any]]] = []
    narrativa_llm_permitida = plan.intent not in {"reglas", "fuera_de_dominio"}
    if settings.llm_active and narrativa_llm_permitida:
        try:
            answer = await _narrar_llm(settings, resultados, solicitud.mensaje)
            narrator_llm_used = True
            trazas.append(
                ("narrator", "ok", {"attempt": 0, "llm_used": True, "modelo": settings.llm_model})
            )
        except Exception as error:  # noqa: BLE001
            trazas.append(
                (
                    "narrator",
                    "fallback",
                    {"llm_used": False, "modelo": settings.llm_model, "error": str(error)[:300]},
                )
            )
    else:
        trazas.append(("narrator", "fallback", {"attempt": 0, "llm_used": False}))

    while True:
        answer = _presentar_respuesta(
            _con_sugerencia_final(answer, plan.intent, resultados), plan.intent, resultados
        )
        deterministic_findings = _criticar_determinista(answer, resultados)
        critic_findings.clear()
        critic_findings.extend(deterministic_findings)
        critic_llm_used = False
        if not deterministic_findings and settings.llm_active and narrativa_llm_permitida:
            try:
                critic_findings.extend(
                    await _criticar_llm(settings, answer, resultados, solicitud.mensaje)
                )
                critic_llm_used = True
            except Exception as error:  # noqa: BLE001
                trazas.append(
                    (
                        "critic",
                        "fallback",
                        {
                            "llm_used": False,
                            "modelo": settings.llm_model_fast,
                            "error": str(error)[:300],
                        },
                    )
                )
        trazas.append(
            (
                "critic",
                "ok" if not critic_findings else "rejected",
                {
                    "attempt": critic_attempts,
                    "llm_used": critic_llm_used,
                    "modelo": settings.llm_model_fast,
                    "findings": critic_findings,
                },
            )
        )
        if not critic_findings:
            break
        if not narrator_llm_used:
            break
        if critic_attempts >= settings.critic_max_retries:
            answer = _narrar(plan.intent, resultados)
            answer = _presentar_respuesta(
                _con_sugerencia_final(answer, plan.intent, resultados), plan.intent, resultados
            )
            narrator_llm_used = False
            critic_findings.clear()
            critic_findings.extend(_criticar_determinista(answer, resultados))
            trazas.append(
                (
                    "narrator",
                    "fallback",
                    {
                        "attempt": critic_attempts,
                        "llm_used": False,
                        "reason": "critic_retries_exhausted",
                    },
                )
            )
            break
        critic_attempts += 1
        try:
            answer = await _narrar_llm(settings, resultados, solicitud.mensaje, critic_findings)
            trazas.append(
                (
                    "narrator",
                    "retry",
                    {
                        "attempt": critic_attempts,
                        "llm_used": True,
                        "modelo": settings.llm_model,
                        "feedback": critic_findings,
                    },
                )
            )
        except Exception as error:  # noqa: BLE001
            answer = _narrar(plan.intent, resultados)
            narrator_llm_used = False
            trazas.append(
                (
                    "narrator",
                    "fallback",
                    {"llm_used": False, "modelo": settings.llm_model, "error": str(error)[:300]},
                )
            )

    critic_passed = not critic_findings
    tarjetas = [
        TarjetaChat(tipo=paso.tool, datos=resultado)
        for paso, resultado in zip(plan.steps, resultados, strict=True)
    ]
    candidatos = [
        CandidatoChat(**candidato)
        for resultado in resultados
        for candidato in resultado.get("candidatos", [])
    ]
    sugerir_nombre_ingles = any(
        resultado.get("estado") in {"ambiguo", "no_encontrado"}
        and resultado.get("traza_traduccion") is not None
        for resultado in resultados
    )
    for resultado in resultados:
        juego = resultado.get("juego")
        if isinstance(juego, dict) and isinstance(juego.get("id"), str):
            chat_session.juego_en_foco_id = juego["id"]
    if any(resultado.get("estado") in {"ambiguo", "no_encontrado"} for resultado in resultados):
        chat_session.intent_pendiente = plan.intent
    elif any(resultado.get("estado") == "encontrado" for resultado in resultados):
        chat_session.intent_pendiente = None
    run.respuesta_final = answer
    run.estado = "completed"
    run.critic_passed = critic_passed
    run.critic_attempts = critic_attempts
    run.critic_findings = [
        {"mensaje": finding} if isinstance(finding, str) else finding for finding in critic_findings
    ] or None
    run.modelo = settings.llm_model if narrator_llm_used else None
    run.terminado_en = datetime.now(UTC)
    session.add_all(
        [
            AgentStep(
                user_id=user.id,
                run_id=run.id,
                agent_name=agent_name,
                estado=estado,
                output=output,
                error_mensaje=output.get("error"),
            )
            for agent_name, estado, output in trazas
        ]
    )
    session.add(
        ChatMessage(
            user_id=user.id,
            session_id=chat_session.id,
            role="assistant",
            contenido=answer,
            agent_run_id=run.id,
            meta={"tarjetas": [tarjeta.model_dump() for tarjeta in tarjetas]},
        )
    )
    await session.commit()
    return ChatRespuesta(
        run_id=run.id,
        session_id=chat_session.id,
        intent=plan.intent,
        plan=pasos_respuesta,
        answer=answer,
        tarjetas=tarjetas,
        candidatos=candidatos,
        sugerir_nombre_ingles=sugerir_nombre_ingles,
        critic_passed=critic_passed,
        critic_attempts=critic_attempts,
        critic_findings=run.critic_findings or [],
        llm_used=narrator_llm_used or llm_used,
    )


async def listar_runs(session: AsyncSession, user_id: str) -> list[AgentRun]:
    return list(
        (
            await session.scalars(
                select(AgentRun)
                .where(AgentRun.user_id == user_id)
                .order_by(AgentRun.creado_en.desc())
            )
        ).all()
    )
