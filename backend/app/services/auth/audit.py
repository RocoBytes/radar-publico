"""Helper centralizado de auditoría. Sin PII en logs (regla #12)."""

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eventos_auditoria import EventoAuditoria


async def log_event(
    session: AsyncSession,
    accion: str,
    *,
    usuario_id: uuid.UUID | None = None,
    empresa_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    recurso_tipo: str | None = None,
    recurso_id: str | None = None,
    info: dict[str, Any] | None = None,
) -> None:
    evento = EventoAuditoria(
        accion=accion,
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        ip_address=ip,
        user_agent=user_agent,
        recurso_tipo=recurso_tipo,
        recurso_id=recurso_id,
        info=info or {},
    )
    session.add(evento)
