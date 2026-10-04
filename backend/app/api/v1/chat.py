"""API de conversaciones y trazas del agente."""

from fastapi import APIRouter, Request

from app.api.deps import CurrentProfile, CurrentUser, DbSession, SesionActual
from app.api.v1.engine import _coleccion
from app.core.config import settings
from app.db.models import AgentRun, ChatSession
from app.schemas.chat import ChatRespuesta, ChatSolicitud, RunResumen, SugerenciasRespuesta
from app.services.chat import listar_runs, responder
from app.services.sugerencias import generar_sugerencias

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatRespuesta)
async def conversar(
    solicitud: ChatSolicitud,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    perfil: CurrentProfile,
    sesion: SesionActual,
) -> ChatRespuesta:
    return await responder(
        session, request, user, perfil, solicitud, settings, usuario_id=sesion.usuario_id
    )


@router.get("/suggestions", response_model=SugerenciasRespuesta)
async def sugerencias(
    session: DbSession, user: CurrentUser, perfil: CurrentProfile
) -> SugerenciasRespuesta:
    """Tres preguntas distintas en cada carga; la de compra evita juegos de la colección activa."""
    coleccion = await _coleccion(session, user, perfil.id)
    return SugerenciasRespuesta(preguntas=generar_sugerencias({juego.id for juego in coleccion}))


@router.get("/runs", response_model=list[RunResumen])
async def runs(session: DbSession, user: CurrentUser, sesion: SesionActual) -> list[RunResumen]:
    return [
        RunResumen(
            id=run.id,
            session_id=run.session_id,
            pregunta=run.pregunta,
            intent=run.intent,
            estado=run.estado,
            creado_en=run.creado_en.isoformat(),
        )
        for run in await listar_runs(session, user.id, sesion.usuario_id)
    ]


@router.get("/runs/{run_id}", response_model=ChatRespuesta)
async def run(
    run_id: str, session: DbSession, user: CurrentUser, sesion: SesionActual
) -> ChatRespuesta:
    item = await session.get(AgentRun, run_id)
    dueno = await session.get(ChatSession, item.session_id) if item and item.session_id else None
    if (
        item is None
        or item.user_id != user.id
        or dueno is None
        or dueno.usuario_id != sesion.usuario_id
    ):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Corrida no encontrada.")
    plan = item.plan or {"steps": []}
    return ChatRespuesta(
        run_id=item.id,
        session_id=item.session_id or "",
        intent=item.intent or "general",
        plan=plan["steps"],
        answer=item.respuesta_final or "",
        critic_passed=item.critic_passed,
        critic_attempts=item.critic_attempts,
        critic_findings=item.critic_findings or [],
        llm_used=bool(item.modelo),
    )
