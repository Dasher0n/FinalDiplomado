"""API de conversaciones y trazas del agente."""

from fastapi import APIRouter, Request

from app.api.deps import CurrentProfile, CurrentUser, DbSession
from app.core.config import settings
from app.db.models import AgentRun
from app.schemas.chat import ChatRespuesta, ChatSolicitud, RunResumen
from app.services.chat import listar_runs, responder

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatRespuesta)
async def conversar(
    solicitud: ChatSolicitud,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    perfil: CurrentProfile,
) -> ChatRespuesta:
    return await responder(session, request, user, perfil, solicitud, settings)


@router.get("/runs", response_model=list[RunResumen])
async def runs(session: DbSession, user: CurrentUser) -> list[RunResumen]:
    return [
        RunResumen(
            id=run.id,
            session_id=run.session_id,
            pregunta=run.pregunta,
            intent=run.intent,
            estado=run.estado,
            creado_en=run.creado_en.isoformat(),
        )
        for run in await listar_runs(session, user.id)
    ]


@router.get("/runs/{run_id}", response_model=ChatRespuesta)
async def run(run_id: str, session: DbSession, user: CurrentUser) -> ChatRespuesta:
    item = await session.get(AgentRun, run_id)
    if item is None or item.user_id != user.id:
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
