"""Orquestador persistente y determinista del asistente de ludoteca."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.catalogo import _juego_detalle
from app.api.v1.engine import _artefactos, _coleccion, _juego, _niveles
from app.core.config import Settings
from app.db.models import AgentRun, AgentStep, ChatMessage, ChatSession, Game
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
    intent: str
    steps: list[PasoPlan] = Field(default_factory=list)


def _plan_determinista(mensaje: str, game_id: str | None) -> PlanLlm:
    texto = mensaje.lower()
    if any(palabra in texto for palabra in ("ignora", "instrucciones", "prompt", "sistema")):
        return PlanLlm(intent="fuera_de_dominio")
    if any(palabra in texto for palabra in ("regla", "reglamento", "como se juega")):
        return PlanLlm(intent="reglas")
    if any(palabra in texto for palabra in ("vale la pena", "evalu", "redund")) or game_id:
        return PlanLlm(
            intent="evaluar_compra",
            steps=[
                PasoPlan(
                    id="1",
                    tool="evaluar_compra",
                    args={"game_id": game_id} if game_id else {"nombre": mensaje},
                )
            ],
        )
    if any(palabra in texto for palabra in ("que compro", "qué compro", "recomienda", "comprar")):
        numero = re.search(r"\b(\d{1,2})\b", texto)
        n = max(1, min(20, int(numero.group(1)))) if numero else 5
        return PlanLlm(
            intent="que_compro", steps=[PasoPlan(id="1", tool="que_compro", args={"n": n})]
        )
    if any(palabra in texto for palabra in ("falta", "faltan", "cobertura", "hueco")):
        return PlanLlm(intent="que_me_falta", steps=[PasoPlan(id="1", tool="que_me_falta")])
    if any(palabra in texto for palabra in ("saco", "jugamos", "somos", "minutos")):
        numeros = [int(valor) for valor in re.findall(r"\b\d{1,3}\b", texto)]
        args = {
            "jugadores": numeros[0] if numeros else 4,
            "minutos": numeros[1] if len(numeros) > 1 else 60,
        }
        return PlanLlm(
            intent="que_saco_hoy", steps=[PasoPlan(id="1", tool="que_saco_hoy", args=args)]
        )
    if any(palabra in texto for palabra in ("coleccion", "colección", "tengo")) and not game_id:
        return PlanLlm(intent="coleccion", steps=[PasoPlan(id="1", tool="ver_coleccion")])
    return PlanLlm(
        intent="detalle_juego",
        steps=[
            PasoPlan(
                id="1",
                tool="detalle_juego",
                args={"game_id": game_id} if game_id else {"nombre": mensaje},
            )
        ],
    )


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


async def _plan_llm(settings: Settings, mensaje: str, resumen: str) -> PlanLlm | None:
    """Usa Responses.parse solo cuando la configuracion habilita explícitamente el LLM."""
    if not settings.llm_active:
        return None
    from openai import AsyncOpenAI

    cliente = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
    respuesta = await cliente.responses.parse(
        model=settings.llm_model_fast,
        input=(
            "Clasifica una pregunta de ludoteca y crea pasos de tools de solo lectura. "
            f"Tools: {sorted(_TOOLS)}. Coleccion: {resumen}. Pregunta: {mensaje}"
        ),
        text_format=PlanLlm,
    )
    return respuesta.output_parsed


async def _resolver(
    repo: CatalogoRepository, nombre: str | None, game_id: str | None, settings: Settings
) -> tuple[str, tuple[Game, ...]]:
    if game_id:
        juego = await repo.obtener_juego(game_id)
        return ("encontrado", (juego,)) if juego else ("no_encontrado", ())
    juegos = await repo.todos_los_juegos()
    consulta_normalizada = normalizar_nombre(nombre or "")
    incluidos = tuple(
        juego
        for juego in juegos
        if len(normalizar_nombre(juego.nombre)) > 2
        and normalizar_nombre(juego.nombre) in consulta_normalizada
    )
    if len(incluidos) == 1:
        return "encontrado", incluidos
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
        "regla_exacta": exacta,
        "niveles_que_cubre": [nivel.model_dump() for nivel in _niveles(juego, artefactos, huecos)],
    }


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
        return "**Huecos de la colección:** " + (
            "; ".join(faltantes) or "no hay niveles faltantes."
        )
    if intent == "que_compro":
        opciones = [
            f"**{opcion['etiqueta']}**: "
            f"{', '.join(juego['nombre'] for juego in opcion['juegos']) or 'sin candidatos'}"
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


def _criticar(respuesta: str, resultados: list[dict[str, Any]]) -> bool:
    if "redundante" in respuesta.lower() and not any(
        item.get("veredicto") == "redundante" for item in resultados
    ):
        return False
    return not (
        any(item.get("estado") in {"ambiguo", "no_encontrado"} for item in resultados)
        and "Similitud" in respuesta
    )


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
    plan = _validar_plan(
        await _plan_llm(settings, solicitud.mensaje, resumen) if settings.llm_active else None,
        settings.llm_max_plan_steps,
    )
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
    for paso in plan.steps:
        resultado = await _ejecutar_tool(
            paso.tool, paso.args, session, user.id, perfil, request, settings
        )
        resultados.append(resultado)
        pasos_respuesta.append(paso.model_copy(update={"estado": "completado"}))
        session.add(
            AgentStep(
                user_id=user.id, run_id=run.id, agent_name="tool", step_id=paso.id, output=resultado
            )
        )
    answer = _narrar(plan.intent, resultados)
    critic_passed = _criticar(answer, resultados)
    tarjetas = [
        TarjetaChat(tipo=paso.tool, datos=resultado)
        for paso, resultado in zip(plan.steps, resultados, strict=True)
    ]
    candidatos = [
        CandidatoChat(**candidato)
        for resultado in resultados
        for candidato in resultado.get("candidatos", [])
    ]
    run.respuesta_final, run.estado, run.critic_passed, run.terminado_en = (
        answer,
        "completed",
        critic_passed,
        datetime.now(UTC),
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
        llm_used=llm_used,
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
