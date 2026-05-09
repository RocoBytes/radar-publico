"""Script de validación manual del cliente ChileCompra.

Uso:
    docker compose exec api python -m app.scripts.test_chilecompra

Qué hace:
1. Crea un usuario + empresa de prueba en la BD (vía ORM).
2. Cifra el ticket público y lo asocia a la empresa.
3. Ejecuta una sincronización de licitaciones activas.
4. Reporta: cuántas bajó, cuántos requests usó, tiempo total.
5. Limpia los datos de prueba de la BD.

Ticket público de prueba (no usar en producción):
    F8537A18-6766-4DEF-9E59-426B4FEE2844
"""

import asyncio
import time
import uuid

import structlog

logger = structlog.get_logger()

TICKET_PUBLICO = "F8537A18-6766-4DEF-9E59-426B4FEE2844"


async def main() -> None:
    """Punto de entrada del script de validación."""
    from app.core.encryption import encrypt_ticket
    from app.db.session import AsyncSessionLocal
    from app.models.empresa import Empresa
    from app.models.enums import (
        EmpresaTamano,
        LicitacionEstado,
        TicketStatus,
        UserRole,
        UserStatus,
    )
    from app.models.licitacion import Licitacion
    from app.models.ticket import TicketApi
    from app.models.usuario import Usuario
    from app.services.chilecompra.client import MercadoPublicoClient
    from app.services.chilecompra.enums import EstadoLicitacion

    print("\n" + "=" * 60)
    print("  Radar Público — Validación cliente ChileCompra")
    print("=" * 60)

    # ── Crear datos de prueba ────────────────────────────────────
    print("\n[1/4] Creando datos de prueba en BD...")
    suffix = uuid.uuid4().hex[:6]

    async with AsyncSessionLocal() as session:
        usuario = Usuario(
            email=f"test_script_{suffix}@radarpublico.cl",
            password_hash="$2b$12$placeholder",  # noqa: S106 — placeholder solo en script de prueba
            rol=UserRole.proveedor,
            status=UserStatus.active,
            must_change_password=False,
        )
        session.add(usuario)
        await session.flush()

        empresa = Empresa(
            usuario_id=usuario.id,
            rut=f"76.{suffix[:3]}.{suffix[3:]}-K",
            razon_social=f"Test Script {suffix} SpA",
            regiones_operacion=["Metropolitana de Santiago"],
            tamano=EmpresaTamano.micro,
        )
        session.add(empresa)
        await session.flush()

        ticket_cifrado = encrypt_ticket(TICKET_PUBLICO)
        ticket = TicketApi(
            empresa_id=empresa.id,
            ticket_cifrado=ticket_cifrado,
            ticket_ultimos_4=TICKET_PUBLICO[-4:],
            status=TicketStatus.active,
        )
        session.add(ticket)
        await session.commit()

        empresa_id = empresa.id
        ticket_id = ticket.id
        usuario_id = usuario.id

    print(f"    empresa_id : {empresa_id}")
    print(f"    ticket_id  : {ticket_id}")

    # ── Sincronizar ──────────────────────────────────────────────
    print("\n[2/4] Ejecutando sincronización con API ChileCompra...")
    print(f"    ticket (últimos 4): ***{TICKET_PUBLICO[-4:]}")

    from app.core.encryption import decrypt_ticket

    async with AsyncSessionLocal() as session:
        ticket_obj = await session.get(TicketApi, ticket_id)
        assert ticket_obj is not None
        ticket_plaintext = decrypt_ticket(ticket_obj.ticket_cifrado)

    t_start = time.monotonic()

    async with MercadoPublicoClient() as client:
        response = await client.listar_licitaciones_por_estado(
            estado=EstadoLicitacion.ACTIVAS,
            ticket=ticket_plaintext,
            ticket_id=ticket_id,
            empresa_id=empresa_id,
        )

    del ticket_plaintext  # Limpiar inmediatamente
    elapsed = time.monotonic() - t_start

    # ── Persistir licitaciones ───────────────────────────────────
    print("\n[3/4] Persistiendo licitaciones en BD...")
    nuevas = 0
    errores = 0

    async with AsyncSessionLocal() as session:
        for item in response.Listado:
            try:
                existing = await session.get(Licitacion, item.CodigoExterno)
                if existing is None:
                    session.add(
                        Licitacion(
                            codigo=item.CodigoExterno,
                            nombre=item.Nombre,
                            estado=LicitacionEstado.publicada,
                            estado_codigo=item.CodigoEstado,
                            fecha_cierre=item.FechaCierre,
                        )
                    )
                    nuevas += 1
            except Exception as e:
                errores += 1
                print(f"    ✗ Error persistiendo {item.CodigoExterno}: {e}")
        await session.commit()

    # ── Reporte ──────────────────────────────────────────────────
    print("\n[4/4] Resultados:")
    print(f"    Licitaciones en API  : {response.Cantidad:,}")
    print(f"    Licitaciones nuevas  : {nuevas:,}")
    print(f"    Errores de persist.  : {errores}")
    print(f"    Tiempo de request    : {elapsed:.2f}s")
    print("    Requests API usados  : 1 (listado)")

    # Verificar en BD
    from sqlalchemy import func, select

    async with AsyncSessionLocal() as session:
        total_bd = (
            await session.execute(select(func.count()).select_from(Licitacion))
        ).scalar()
        ultima = (
            await session.execute(select(func.max(Licitacion.fecha_publicacion)))
        ).scalar()

    print(f"\n    Total licitaciones en BD  : {total_bd:,}")
    print(f"    Última fecha_publicacion  : {ultima}")

    # Verificar api_quota_log
    from app.models.api_log import ApiQuotaLog

    async with AsyncSessionLocal() as session:
        logs = (
            await session.execute(
                select(func.count())
                .select_from(ApiQuotaLog)
                .where(ApiQuotaLog.ticket_id == ticket_id)
            )
        ).scalar()
    print(f"    Requests en api_quota_log : {logs}")

    # ── Limpieza ─────────────────────────────────────────────────
    print("\n    Limpiando datos de prueba...")
    async with AsyncSessionLocal() as session:
        usuario_obj = await session.get(Usuario, usuario_id)
        if usuario_obj:
            await session.delete(usuario_obj)
            await session.commit()
    print("    ✓ Datos de prueba eliminados")

    print("\n" + "=" * 60)
    print("  ✅ Validación completada exitosamente")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
