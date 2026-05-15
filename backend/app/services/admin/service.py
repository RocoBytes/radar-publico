"""Servicio de administración de cuentas.

Toda operación aquí queda en eventos_auditoria (regla #14).
Sin PII en logs (regla #12): solo IDs internos.
"""

from datetime import UTC, datetime
import time
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.core.encryption import encrypt_ticket
from app.core.security import generate_temporary_password, hash_password
from app.models.empresa import Empresa
from app.models.enums import TicketStatus, UserRole, UserStatus
from app.models.ticket import TicketApi
from app.models.usuario import Usuario
from app.services.admin.exceptions import (
    CuentaNoEncontradaError,
    CuentaYaExisteError,
    EmpresaNoEncontradaError,
)
from app.services.auth.audit import log_event
from app.services.email import sender as email_sender
from app.services.email.templates import welcome as tpl_welcome

logger = structlog.get_logger()

# Acciones de auditoría propias del módulo admin
_ACTION_CUENTA_CREADA = "admin.cuenta.creada"
_ACTION_CUENTA_SUSPENDIDA = "admin.cuenta.suspendida"
_ACTION_CUENTA_REACTIVADA = "admin.cuenta.reactivada"
_ACTION_TICKET_CARGADO = "admin.ticket.cargado"


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def crear_cuenta(
        self,
        email: str,
        rut: str,
        razon_social: str,
        creado_por_id: uuid.UUID,
    ) -> tuple[Usuario, str]:
        """Crea usuario + empresa en una transacción. Retorna (usuario, temp_password).

        El plaintext de la contraseña temporal solo se retorna una vez para
        mostrarlo en la UI — después ya no es recuperable.
        """
        # Verificar unicidad de email (excluir cuentas eliminadas)
        result = await self._db.execute(
            select(Usuario).where(
                Usuario.email == email,
                Usuario.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is not None:
            raise CuentaYaExisteError("email")

        # Verificar unicidad de RUT en empresas
        result_rut = await self._db.execute(
            select(Empresa).where(Empresa.rut == rut)
        )
        if result_rut.scalar_one_or_none() is not None:
            raise CuentaYaExisteError("rut")

        temp_password = generate_temporary_password()
        password_hash = hash_password(temp_password)

        usuario = Usuario(
            email=email,
            password_hash=password_hash,
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=True,
        )
        self._db.add(usuario)
        await self._db.flush()  # obtiene el id antes de crear la empresa

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=rut,
            razon_social=razon_social,
        )
        self._db.add(empresa)
        await self._db.flush()

        await log_event(
            self._db,
            _ACTION_CUENTA_CREADA,
            usuario_id=creado_por_id,
            recurso_tipo="usuario",
            recurso_id=str(usuario.id),
            info={"creado_usuario_id": str(usuario.id)},
        )

        await self._db.commit()
        await self._db.refresh(usuario)

        # Email fuera de la transacción — un fallo de envío no revierte la cuenta
        try:
            subject, html, text = tpl_welcome.render(
                razon_social=razon_social,
                email=email,
                temp_password=temp_password,
            )
            await email_sender.send_email(
                to=email, subject=subject, html=html, text=text
            )
        except Exception:
            # El log del error lo maneja el sender; la cuenta ya existe
            logger.warning("bienvenida_email_fallido", usuario_id=str(usuario.id))

        return usuario, temp_password

    async def listar_cuentas(
        self,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Usuario], int]:
        """Lista proveedores activos (no eliminados), paginados."""
        base_where = [
            Usuario.rol == UserRole.proveedor,
            Usuario.deleted_at.is_(None),
        ]

        count_result = await self._db.execute(
            select(func.count()).select_from(Usuario).where(*base_where)
        )
        total: int = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self._db.execute(
            select(Usuario)
            .where(*base_where)
            .options(selectinload(Usuario.empresa))
            .order_by(Usuario.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return items, total

    async def obtener_cuenta(self, usuario_id: uuid.UUID) -> Usuario:
        """Carga usuario con empresa y ticket. Lanza si no existe."""
        result = await self._db.execute(
            select(Usuario)
            .where(
                Usuario.id == usuario_id,
                Usuario.deleted_at.is_(None),
            )
            .options(
                selectinload(Usuario.empresa).selectinload(Empresa.ticket),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise CuentaNoEncontradaError
        return usuario

    async def cambiar_estado(
        self,
        usuario_id: uuid.UUID,
        accion: str,
        admin_id: uuid.UUID,
    ) -> Usuario:
        """Suspende o reactiva una cuenta de proveedor."""
        result = await self._db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.deleted_at.is_(None),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise CuentaNoEncontradaError

        if accion == "suspender":
            usuario.status = UserStatus.suspended
            audit_action = _ACTION_CUENTA_SUSPENDIDA
        else:
            usuario.status = UserStatus.active
            audit_action = _ACTION_CUENTA_REACTIVADA

        await log_event(
            self._db,
            audit_action,
            usuario_id=admin_id,
            recurso_tipo="usuario",
            recurso_id=str(usuario_id),
        )

        await self._db.commit()
        await self._db.refresh(usuario)
        return usuario

    async def cargar_ticket(
        self,
        usuario_id: uuid.UUID,
        ticket_plaintext: str,
        admin_id: uuid.UUID,
    ) -> TicketApi:
        """Cifra y persiste (upsert) el ticket de ChileCompra.

        Idempotente: llamar dos veces con el mismo o distinto valor
        actualiza sin duplicar (regla #29 del admin).
        El ticket plaintext nunca se loggea (regla #2 y #12).
        """
        # Cargar usuario + empresa + ticket existente en una sola query
        result = await self._db.execute(
            select(Usuario)
            .where(
                Usuario.id == usuario_id,
                Usuario.deleted_at.is_(None),
            )
            .options(
                selectinload(Usuario.empresa).selectinload(Empresa.ticket),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise CuentaNoEncontradaError

        if usuario.empresa is None:
            raise EmpresaNoEncontradaError

        ticket_cifrado = encrypt_ticket(ticket_plaintext)
        ultimos_4 = ticket_plaintext[-4:]
        ahora = datetime.now(UTC)

        empresa = usuario.empresa
        if empresa.ticket is not None:
            # UPDATE idempotente
            ticket = empresa.ticket
            ticket.ticket_cifrado = ticket_cifrado
            ticket.ticket_ultimos_4 = ultimos_4
            ticket.status = TicketStatus.active
            ticket.cargado_por_admin_id = admin_id
            ticket.cargado_at = ahora
            ticket.updated_at = ahora
        else:
            # INSERT nuevo
            ticket = TicketApi(
                empresa_id=empresa.id,
                ticket_cifrado=ticket_cifrado,
                ticket_ultimos_4=ultimos_4,
                status=TicketStatus.active,
                cargado_por_admin_id=admin_id,
                cargado_at=ahora,
            )
            self._db.add(ticket)

        await log_event(
            self._db,
            _ACTION_TICKET_CARGADO,
            usuario_id=admin_id,
            empresa_id=empresa.id,
            recurso_tipo="ticket",
            recurso_id=str(empresa.id),
        )

        await self._db.commit()
        await self._db.refresh(ticket)
        return ticket

    async def impersonar_cuenta(
        self,
        usuario_id: uuid.UUID,
        admin_id: uuid.UUID,
    ) -> str:
        """Genera token de impersonación (1h) y registra en auditoría."""
        from app.core.security import create_impersonation_token

        result = await self._db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.deleted_at.is_(None),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise CuentaNoEncontradaError

        token = create_impersonation_token(str(usuario.id), str(admin_id))

        await log_event(
            self._db,
            "admin.cuenta.impersonada",
            usuario_id=admin_id,
            recurso_tipo="usuario",
            recurso_id=str(usuario_id),
            info={"impersonado_usuario_id": str(usuario_id)},
        )
        await self._db.commit()

        logger.info("admin_impersonacion", admin_id=str(admin_id), usuario_id=str(usuario_id))
        return token

    async def diagnosticar_ticket(
        self,
        usuario_id: uuid.UUID,
        test_conexion: bool = False,
    ) -> dict[str, Any]:
        """Diagnóstica el ticket ChileCompra de una empresa.

        Si test_conexion=True, hace una llamada real a la API (consume cuota).
        """
        from app.models.api_log import ApiQuotaLog

        result = await self._db.execute(
            select(Usuario)
            .where(
                Usuario.id == usuario_id,
                Usuario.deleted_at.is_(None),
            )
            .options(
                selectinload(Usuario.empresa).selectinload(Empresa.ticket),
            )
        )
        usuario = result.scalar_one_or_none()
        if usuario is None:
            raise CuentaNoEncontradaError

        empresa = usuario.empresa
        if empresa is None or empresa.ticket is None:
            return {
                "tiene_ticket": False,
                "ticket_ultimos_4": None,
                "ticket_status": None,
                "llamadas_hoy": 0,
                "test_ok": None,
                "test_error": None,
                "test_duracion_ms": None,
            }

        ticket_obj = empresa.ticket

        hoy_inicio = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await self._db.execute(
            select(func.count())
            .select_from(ApiQuotaLog)
            .where(
                ApiQuotaLog.ticket_id == ticket_obj.id,
                ApiQuotaLog.created_at >= hoy_inicio,
            )
        )
        llamadas_hoy: int = count_result.scalar_one()

        test_ok: bool | None = None
        test_error: str | None = None
        test_duracion_ms: int | None = None

        if test_conexion:
            from app.core.encryption import decrypt_ticket
            from app.services.chilecompra.client import MercadoPublicoClient
            from app.services.chilecompra.enums import EstadoLicitacion

            try:
                ticket_plaintext = decrypt_ticket(ticket_obj.ticket_cifrado)
                t0 = time.monotonic()
                async with MercadoPublicoClient() as client:
                    await client.listar_licitaciones_por_estado(
                        estado=EstadoLicitacion.ACTIVAS,
                        ticket=ticket_plaintext,
                        ticket_id=ticket_obj.id,
                        empresa_id=empresa.id,
                    )
                test_duracion_ms = int((time.monotonic() - t0) * 1000)
                test_ok = True
            except Exception as exc:
                test_ok = False
                test_error = str(exc)[:300]

        return {
            "tiene_ticket": True,
            "ticket_ultimos_4": ticket_obj.ticket_ultimos_4,
            "ticket_status": ticket_obj.status.value if ticket_obj.status else None,
            "llamadas_hoy": llamadas_hoy,
            "test_ok": test_ok,
            "test_error": test_error,
            "test_duracion_ms": test_duracion_ms,
        }
