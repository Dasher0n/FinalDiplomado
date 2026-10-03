"""Orquestador persistente y determinista del asistente de ludoteca."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.catalogo import _juego_detalle
from app.api.v1.engine import _artefactos, _coleccion, _juego, _niveles
from app.core.config import Settings
from app.db.models import AgentRun, AgentStep, ChatMessage, ChatSession, Game, ToolCall
from app.engine.motor import (
    buscar_local,
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


class _PasoPlanLlm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str
    args: _ArgsPlanLlm = Field(default_factory=_ArgsPlanLlm)
    depends_on: list[str] = Field(default_factory=list)


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


_TOOL_MANIFEST = {
    "ver_coleccion": {
        "descripcion": "Muestra los juegos de la colección activa.",
        "requeridos": [],
    },
    "detalle_juego": {
        "descripcion": "Muestra la ficha de un juego del catálogo.",
        "requeridos": ["nombre o game_id"],
    },
    "evaluar_compra": {
        "descripcion": "Evalúa redundancia y huecos que cubre un juego.",
        "requeridos": ["nombre o game_id"],
    },
    "que_me_falta": {"descripcion": "Calcula faltantes y debilidades.", "requeridos": []},
    "que_compro": {
        "descripcion": "Propone tres planes por número de juegos.",
        "requeridos": ["n"],
    },
    "que_saco_hoy": {
        "descripcion": "Filtra la colección para jugadores y duración.",
        "requeridos": ["jugadores", "minutos"],
    },
}


def _plan_determinista(mensaje: str, game_id: str | None) -> PlanLlm:
    texto = mensaje.lower()
    consulta = normalizar_nombre(mensaje)
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
    if any(palabra in consulta for palabra in ("vale la pena", "evalu", "redund")) or game_id:
        args = {"game_id": game_id} if game_id else {"nombre": _extraer_nombre_juego(mensaje)}
        return PlanLlm(
            intent="evaluar_compra",
            steps=[PasoPlan(id="1", tool="evaluar_compra", args=args)],
        )
    if any(palabra in consulta for palabra in ("coleccion", "tengo")) and not game_id:
        return PlanLlm(intent="coleccion", steps=[PasoPlan(id="1", tool="ver_coleccion")])
    pregunta_general = re.match(r"^(quien|quienes|cuando|donde|por que)\b", consulta)
    if pregunta_general and len(consulta.split()) >= 4:
        return PlanLlm(intent="fuera_de_dominio")
    args = {"game_id": game_id} if game_id else {"nombre": _extraer_nombre_juego(mensaje)}
    return PlanLlm(
        intent="detalle_juego",
        steps=[PasoPlan(id="1", tool="detalle_juego", args=args)],
    )


def _extraer_nombre_juego(mensaje: str) -> str:
    """Separa el título de juego de la formulación de la pregunta."""
    patrones = (
        r"\b(?:comprar|compra|evaluar|evalúa)\s+(?:el juego\s+)?(?P<nombre>.+?)(?=[,;.!?¿]|$)",
        r"\bvale la pena\s+(?P<nombre>.+?)(?=[,;.!?¿]|$)",
    )
    for patron in patrones:
        coincidencia = re.search(patron, mensaje, re.IGNORECASE)
        if coincidencia:
            nombre = coincidencia.group("nombre").strip(" \t\r\n,;.!?¿¡")
            if nombre:
                return nombre
    return mensaje.strip(" \t\r\n,;.!?¿¡")


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
        if paso.tool in {"detalle_juego", "evaluar_compra"} and not (
            paso.args.get("nombre") or paso.args.get("game_id")
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


async def _plan_llm(settings: Settings, mensaje: str, resumen: str) -> PlanLlm | None:
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
            f"{manifest}\nColección: {resumen}\nPregunta: {mensaje}"
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
    juegos = await repo.todos_los_juegos()
    consulta_normalizada = normalizar_nombre(nombre or "")
    exactos = tuple(
        juego for juego in juegos if normalizar_nombre(juego.nombre) == consulta_normalizada
    )
    if len(exactos) == 1:
        return "encontrado", exactos
    incluidos = tuple(
        juego
        for juego in juegos
        if len(normalizar_nombre(juego.nombre)) > 2
        and normalizar_nombre(juego.nombre) in consulta_normalizada
    )
    variantes = tuple(
        juego
        for juego in juegos
        if normalizar_nombre(juego.nombre).startswith(f"{consulta_normalizada} ")
    )
    if variantes:
        candidatos = tuple({juego.id: juego for juego in (*incluidos, *variantes)}.values())
        return "ambiguo", candidatos[:5]
    if len(incluidos) == 1:
        return "encontrado", incluidos
    if len(incluidos) > 1:
        return "ambiguo", incluidos[:5]
    return buscar_local(
        nombre or "",
        juegos,
        umbral_directo=settings.fuzzy_umbral_directo,
        umbral_ambiguo=settings.fuzzy_umbral_ambiguo,
    )


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
    estado, juegos_resueltos = await _resolver(
        repo, args.get("nombre"), args.get("game_id"), settings
    )
    if estado != "encontrado":
        return {
            "estado": estado,
            "candidatos": [
                {"id": juego.id, "nombre": juego.nombre, "imagen_url": juego.image_url}
                for juego in juegos_resueltos
            ],
        }
    juego = juegos_resueltos[0]
    if nombre == "detalle_juego":
        return {"estado": "encontrado", "juego": _juego_detalle(juego).model_dump(mode="json")}
    sin_candidato = [item for item in coleccion if item.id != juego.id]
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
    resultado = resultados[0] if resultados else {}
    if resultado.get("estado") == "ambiguo":
        return "Encontré varias opciones. Elige el juego exacto para evaluarlo."
    if resultado.get("estado") == "no_encontrado":
        return (
            "No encontré ese juego en el catálogo local. "
            "La búsqueda web no está disponible en esta fase."
        )
    if intent == "evaluar_compra":
        juego, similar = resultado["juego"], resultado.get("juego_mas_parecido")
        texto = f"**{juego['nombre']}**: {resultado['veredicto'].replace('_', ' ')}."
        if similar and resultado.get("similitud"):
            similitud = resultado["similitud"]
            texto += f" Se parece a **{similar['nombre']}** por mecánicas y temática."
            texto += f" Similitud total: {similitud['total']:.2f}."
        return texto
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
        return "Planes por número de juegos:\n\n" + "\n".join(opciones)
    if intent == "que_saco_hoy":
        return "Para esta mesa: " + (
            ", ".join(juego["nombre"] for juego in resultado["juegos"])
            or "no hay juegos que pasen los filtros."
        )
    if intent == "coleccion":
        return f"Tu colección activa tiene {resultado['total']} juegos."
    return f"**{resultado['juego']['nombre']}** está en el catálogo."


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
    return "boardgameprices" in texto and bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", texto))


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
    if "redundante" in respuesta.lower() and not any(
        item.get("veredicto") == "redundante" for item in resultados
    ):
        hallazgos.append("La respuesta llama redundante a un juego sin respaldo de una tool.")
    if _encontrar_banderas(resultados) and "estimad" not in respuesta.lower():
        hallazgos.append("Falta indicar que hay datos estimados.")
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
    retroalimentacion: list[str | dict[str, str]] | None = None,
) -> str:
    """Redacta exclusivamente sobre los resultados serializados de las tools."""
    from openai import AsyncOpenAI

    instrucciones = (
        "Eres el narrador de Wise Dice. Responde en español y markdown breve. "
        "Solo puedes afirmar hechos presentes literalmente en los resultados de las tools. "
        "No uses conocimiento propio para describir jugabilidad, sensaciones, géneros ni "
        "características: están prohibidos términos como eurogame, estructura de turno u "
        "objetivos ocultos si no aparecen en los resultados. No inventes cifras, atributos, "
        "fuentes ni recomendaciones. Para un veredicto, explica su motivo real: si regla_exacta "
        "es reimplementa o misma_linea_de_producto, menciónalo; en otro caso indica similitud "
        "total y los bloques disponibles. Nunca llames afinidad o match a la similitud. En un "
        "plan de compra, presenta A, B y C con su valor cubierto, y solo puedes llamar "
        "recomendada a la opción A. En que_me_falta incluye faltantes y débiles."
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
                "content": json.dumps(resultados, ensure_ascii=False, default=str),
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
    settings: Settings, respuesta: str, resultados: list[dict[str, Any]]
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
                    "Devuelve hallazgos "
                    "con categoria y detalle, usando solo estas categorías: cifra_sin_fuente, "
                    "juego_o_atributo_no_disponible o recomendacion_sin_respaldo. Devuelve ok=true "
                    "solo si todas las afirmaciones están respaldadas. No inventes hallazgos."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"resultados_tools": resultados, "respuesta": respuesta},
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
    resumen = ", ".join(juego.nombre for juego in await _coleccion(session, user, perfil.id))
    plan_llm: PlanLlm | None = None
    if settings.llm_active:
        try:
            plan_llm = await _plan_llm(settings, solicitud.mensaje, resumen)
        except Exception:  # noqa: BLE001
            plan_llm = None
    plan = _validar_plan(plan_llm, settings.llm_max_plan_steps)
    llm_used = plan is not None
    plan = plan or _plan_determinista(solicitud.mensaje, solicitud.game_id)
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
    answer = _narrar(plan.intent, resultados)
    narrator_llm_used = False
    critic_findings: list[str | dict[str, str]] = []
    critic_attempts = 0
    trazas: list[tuple[str, str, dict[str, Any]]] = []
    narrativa_llm_permitida = plan.intent not in {"reglas", "fuera_de_dominio"}
    if settings.llm_active and narrativa_llm_permitida:
        try:
            answer = await _narrar_llm(settings, resultados)
            narrator_llm_used = True
            trazas.append(("narrator", "ok", {"attempt": 0, "llm_used": True}))
        except Exception as error:  # noqa: BLE001
            trazas.append(("narrator", "fallback", {"llm_used": False, "error": str(error)[:300]}))
    else:
        trazas.append(("narrator", "fallback", {"attempt": 0, "llm_used": False}))

    while True:
        deterministic_findings = _criticar_determinista(answer, resultados)
        critic_findings.clear()
        critic_findings.extend(deterministic_findings)
        critic_llm_used = False
        if not deterministic_findings and settings.llm_active and narrativa_llm_permitida:
            try:
                critic_findings.extend(await _criticar_llm(settings, answer, resultados))
                critic_llm_used = True
            except Exception as error:  # noqa: BLE001
                trazas.append(
                    ("critic", "fallback", {"llm_used": False, "error": str(error)[:300]})
                )
        trazas.append(
            (
                "critic",
                "ok" if not critic_findings else "rejected",
                {
                    "attempt": critic_attempts,
                    "llm_used": critic_llm_used,
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
            answer = await _narrar_llm(settings, resultados, critic_findings)
            trazas.append(
                (
                    "narrator",
                    "retry",
                    {"attempt": critic_attempts, "llm_used": True, "feedback": critic_findings},
                )
            )
        except Exception as error:  # noqa: BLE001
            answer = _narrar(plan.intent, resultados)
            narrator_llm_used = False
            trazas.append(("narrator", "fallback", {"llm_used": False, "error": str(error)[:300]}))

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
