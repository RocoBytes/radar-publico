"""Tarea Celery: sincronización de detalle completo de licitaciones.

Decisiones de diseño (Sprint 2, 2026-05-11):

1. ARCHIVO SEPARADO: la tarea vive aquí y no en sync_chilecompra.py porque
   no hay precedente de múltiples tareas por archivo en el repo. celery_app.py
   ya tenía reservado "app.tasks.sync_detalle" en comentarios para Sprint 2+.

2. POLÍTICA DE RE-SINCRONIZACIÓN: si detalle_sincronizado_at ya está poblado
   y el hash_contenido del listado no cambió → retornar sin_cambio (regla de
   oro #21 — cache agresivo). Si el hash cambió (estado nuevo, nombre cambiado)
   → re-sincronizar el detalle porque los items/criterios pueden diferir.

3. POLÍTICA 404: la licitación puede haber sido revocada o eliminada en
   ChileCompra después de haberla listado. Se loguea no_encontrada=1, se deja
   detalle_sincronizado_at en NULL y no se eleva la excepción (la tarea debe
   completarse sin reintentos innecesarios para un caso esperado).

Reglas de oro que aplican:
- #2:  Tickets descifrados solo en memoria, nunca persistir en claro.
- #12: Sin PII en logs — nunca loggear el ticket ni datos del organismo.
- #18: Rate limit 5 req/s (lo maneja el cliente HTTP).
- #21: Cache agresivo — no re-consultar si hash no cambió.
- #29: Tarea idempotente — upsert en items/criterios/fechas no duplica filas.
"""

import asyncio
import calendar
import contextlib
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.celery_app import celery_app
from app.core.encryption import decrypt_ticket
from app.models.enums import FechaTipo, LicitacionEstado, TicketStatus
from app.schemas.chilecompra import CompradorAPI
from app.services.chilecompra.client import MercadoPublicoClient
from app.services.chilecompra.enums import EstadoLicitacion
from app.services.chilecompra.exceptions import (
    LicitacionNoEncontradaError,
    MercadoPublicoError,
)

logger = structlog.get_logger()

# Mapeo de campos de la API a valores de FechaTipo.
# Solo los campos con equivalente en el enum de BD.
# Los demás (FechaInicio, FechaFinal, FechaSoporteFisico, etc.) se preservan
# en raw_payload para recuperación futura sin necesitar otra llamada a la API.
_FECHA_MAP: dict[str, FechaTipo] = {
    "FechaCreacion": FechaTipo.creacion,
    "FechaPublicacion": FechaTipo.publicacion,
    "FechaCierre": FechaTipo.cierre,
    "FechaAdjudicacion": FechaTipo.adjudicacion,
    "FechaActoAperturaTecnica": FechaTipo.apertura_tecnica,
    "FechaActoAperturaEconomica": FechaTipo.apertura_economica,
    "FechaVisitaTerreno": FechaTipo.visita_terreno,
    "FechaPubRespuestas": FechaTipo.respuestas,
    "FechaEstimadaFirma": FechaTipo.firma_contrato,
}


def _add_months(dt: datetime, months: int) -> datetime:
    """Suma N meses a una fecha manejando desborde de días correctamente."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _hash_detalle(payload: dict[str, Any]) -> str:
    """SHA-256 del payload completo del detalle para detectar cambios."""
    content = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


async def _sync_adjudicaciones(
    session: AsyncSession,
    licitacion_codigo: str,
    items: list[Any],
    fechas: Any | None,
) -> None:
    """Pobla adjudicaciones y proveedores desde los items del detalle.

    Acumula el monto total por proveedor (Cantidad x MontoUnitario por ítem)
    antes de insertar. Idempotente: borra las previas de esta licitación primero.
    """
    from decimal import Decimal

    from sqlalchemy import delete as sa_delete

    from app.models.adjudicacion import Adjudicacion
    from app.models.proveedor import Proveedor

    # Acumular total por proveedor (un proveedor puede ganar múltiples ítems)
    por_proveedor: dict[str, dict[str, Any]] = {}
    for item in items:
        adj = item.Adjudicacion
        if adj is None or not adj.RutProveedor:
            continue
        rut = adj.RutProveedor

        monto_item: Decimal | None = None
        if adj.Cantidad is not None and adj.MontoUnitario is not None:
            monto_item = Decimal(str(adj.Cantidad)) * Decimal(str(adj.MontoUnitario))

        if rut not in por_proveedor:
            por_proveedor[rut] = {
                "nombre": adj.NombreProveedor or "",
                "monto_total": Decimal(0) if monto_item is not None else None,
            }
        if monto_item is not None and por_proveedor[rut]["monto_total"] is not None:
            por_proveedor[rut]["monto_total"] += monto_item

    if not por_proveedor:
        return

    fecha_adj = fechas.FechaAdjudicacion if fechas else None

    # Idempotente: borrar adjudicaciones previas para esta licitación
    await session.execute(
        sa_delete(Adjudicacion).where(Adjudicacion.licitacion_codigo == licitacion_codigo)
    )

    for rut, data in por_proveedor.items():
        # Upsert proveedor (catálogo externo — no cascadea)
        proveedor: Proveedor | None = await session.get(Proveedor, rut)
        if proveedor is None:
            session.add(Proveedor(rut=rut, razon_social=data["nombre"]))
        elif data["nombre"]:
            proveedor.razon_social = data["nombre"]

        session.add(
            Adjudicacion(
                licitacion_codigo=licitacion_codigo,
                rut_proveedor=rut,
                monto_adjudicado=data["monto_total"],
                fecha_adjudicacion=fecha_adj,
            )
        )


async def _upsert_organismo(
    session: AsyncSession,
    comprador: CompradorAPI,
) -> None:
    """Upsert del organismo comprador antes de asignar el FK en licitaciones.

    Garantiza que la fila exista en `organismos` para evitar FK violation.
    Si CodigoOrganismo no es parseable como int, retorna sin hacer nada.

    Args:
        session: Sesión async activa (dentro de la transacción principal).
        comprador: Datos del comprador tal como los devuelve la API.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.organismo import Organismo

    try:
        codigo = int(comprador.CodigoOrganismo or "")
    except (ValueError, TypeError):
        return

    nombre = comprador.NombreOrganismo or f"Organismo {codigo}"
    ahora = datetime.now(UTC)

    stmt = (
        pg_insert(Organismo)
        .values(
            codigo_organismo=codigo,
            nombre=nombre,
            rut=comprador.RutUnidad,
            region=comprador.RegionUnidad,
            comuna=comprador.ComunaUnidad,
            direccion=comprador.DireccionUnidad,
            updated_at=ahora,
        )
        .on_conflict_do_update(
            index_elements=["codigo_organismo"],
            set_={
                "nombre": nombre,
                "rut": comprador.RutUnidad,
                "region": comprador.RegionUnidad,
                "comuna": comprador.ComunaUnidad,
                "direccion": comprador.DireccionUnidad,
                "updated_at": ahora,
            },
        )
    )
    await session.execute(stmt)


async def _run(
    codigo: str,
    *,
    skip_engine_dispose: bool = False,
) -> dict[str, int]:
    """Lógica async de sincronización de detalle.

    Obtiene el ticket activo de la primera empresa que lo tenga (en v1
    hay 1:1 empresa-ticket). Verifica cache, llama a la API y persiste
    el detalle completo en una sola transacción.

    skip_engine_dispose: pasar True cuando se llama desde FastAPI (el event
    loop ya existe y el pool está activo). Solo Celery necesita dispose().
    """
    import uuid

    from sqlalchemy import and_, delete, select

    from app.db.session import AsyncSessionLocal, engine

    # Disponer conexiones del pool que quedaron adjuntas al event loop anterior.
    # Cada task Celery corre en su propio asyncio.run() → nuevo event loop.
    # Sin dispose(), asyncpg falla con "Future attached to a different loop".
    if not skip_engine_dispose:
        await engine.dispose()
    from app.models.catalogos import Unspsc
    from app.models.licitacion import (
        Licitacion,
        LicitacionFecha,
        LicitacionItem,
    )
    from app.models.ticket import TicketApi

    stats: dict[str, int] = {
        "nueva": 0,
        "actualizada": 0,
        "sin_cambio": 0,
        "no_encontrada": 0,
        "error": 0,
    }

    # Obtener primer ticket activo (v1 tiene 1:1 empresa-ticket)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                TicketApi.ticket_cifrado,
                TicketApi.id,
                TicketApi.ticket_ultimos_4,
                TicketApi.empresa_id,
            ).where(TicketApi.status == TicketStatus.active)
        )
        row = result.first()

    if row is None:
        logger.warning("sync_detalle_no_tickets", codigo=codigo)
        stats["error"] += 1
        return stats

    ticket_cifrado, ticket_id, ticket_ultimos_4, empresa_id = row

    # Descifrar solo en memoria — regla de oro #2
    try:
        ticket_plaintext = decrypt_ticket(ticket_cifrado)
    except Exception as e:
        logger.error(
            "sync_detalle_ticket_decrypt_failed",
            codigo=codigo,
            error=str(e),
        )
        stats["error"] += 1
        return stats

    inicio = datetime.now(UTC)

    try:
        # Verificar cache agresivo — regla de oro #21
        async with AsyncSessionLocal() as session:
            licitacion: Licitacion | None = await session.get(Licitacion, codigo)

        if licitacion is not None and licitacion.detalle_sincronizado_at is not None:
            # Ya tiene detalle → sin cambio.
            # El hash_contenido refleja el estado básico del listado.
            # sync_listado_diario ya reponerá detalle_sincronizado_at a NULL
            # si el hash del listado cambia, forzando una nueva sincronización.
            logger.debug(
                "sync_detalle_sin_cambio",
                codigo=codigo,
                sincronizado_at=licitacion.detalle_sincronizado_at.isoformat(),
            )
            stats["sin_cambio"] += 1
            return stats

        # Llamar a la API de detalle
        async with MercadoPublicoClient() as client:
            response = await client.obtener_detalle_licitacion(
                codigo=codigo,
                ticket=ticket_plaintext,
                ticket_id=uuid.UUID(str(ticket_id)),
                empresa_id=uuid.UUID(str(empresa_id)),
            )

        detalle = response.Listado[0]
        payload_dict = detalle.model_dump(mode="json")
        nuevo_hash = _hash_detalle(payload_dict)

        # Determinar si es nueva o actualizada
        era_nueva = licitacion is None

        async with AsyncSessionLocal() as session:
            # Obtener o crear la licitación
            lic = await session.get(Licitacion, codigo)

            if lic is None:
                # Crear registro básico + detalle en una sola transacción
                estado_enum = EstadoLicitacion.from_codigo(detalle.CodigoEstado or 5)
                lic = Licitacion(
                    codigo=detalle.CodigoExterno,
                    nombre=detalle.Nombre,
                    estado=LicitacionEstado(estado_enum.estado_interno),
                    estado_codigo=detalle.CodigoEstado,
                )
                session.add(lic)
                await session.flush()  # generar el registro antes de los hijos

            # Actualizar campos de detalle
            lic.descripcion = detalle.Descripcion
            lic.raw_payload = payload_dict
            lic.hash_contenido = nuevo_hash
            lic.detalle_sincronizado_at = datetime.now(UTC)
            lic.updated_at = datetime.now(UTC)

            # Campos del comprador — upsert organismo primero para evitar FK violation
            if detalle.Comprador:
                if detalle.Comprador.CodigoOrganismo:
                    await _upsert_organismo(session, detalle.Comprador)
                    with contextlib.suppress(ValueError, TypeError):
                        lic.codigo_organismo = int(detalle.Comprador.CodigoOrganismo)
                if detalle.Comprador.CodigoUnidad:
                    with contextlib.suppress(ValueError, TypeError):
                        lic.codigo_unidad = int(detalle.Comprador.CodigoUnidad)
                lic.unidad_compra = detalle.Comprador.NombreUnidad
                lic.rut_unidad = detalle.Comprador.RutUnidad
                lic.contacto_nombre = detalle.Comprador.NombreUsuario
                lic.contacto_email = detalle.EmailResponsableContrato

            # Campos de tipo y monto
            if detalle.Tipo:
                lic.tipo = detalle.Tipo[:10]
            if detalle.MontoEstimado is not None:
                lic.monto_estimado = detalle.MontoEstimado
            if detalle.Moneda:
                lic.moneda = detalle.Moneda
            if detalle.EsRenovable is not None:
                lic.es_renovable = bool(detalle.EsRenovable)
            # TipoConvocatoria: "1"=Pública, "2"=Privada
            if detalle.TipoConvocatoria:
                _convocatoria = {"1": "Pública", "2": "Privada"}
                lic.modalidad = _convocatoria.get(
                    str(detalle.TipoConvocatoria), str(detalle.TipoConvocatoria)
                )
            if detalle.FonoResponsableContrato:
                lic.contacto_telefono = detalle.FonoResponsableContrato

            # Duración del contrato → duracion_estimada_meses y fecha_estimada_termino_contrato
            # UnidadTiempoDuracionContrato: 1=días, 2=meses, 3=años (convención ChileCompra)
            if detalle.TiempoDuracionContrato is not None:
                with contextlib.suppress(ValueError, TypeError):
                    tiempo = int(detalle.TiempoDuracionContrato)
                    unidad = detalle.UnidadTiempoDuracionContrato
                    lic.tiempo_contrato = tiempo
                    lic.unidad_tiempo_contrato = unidad

                    if unidad == 1:
                        meses = max(1, round(tiempo / 30))
                    elif unidad == 3:
                        meses = tiempo * 12
                    else:
                        meses = tiempo  # 2=meses o desconocido → asumir meses

                    lic.duracion_estimada_meses = meses

                    fecha_adj = detalle.Fechas.FechaAdjudicacion if detalle.Fechas else None
                    if fecha_adj is not None and meses > 0:
                        lic.fecha_estimada_termino_contrato = _add_months(fecha_adj, meses)

            # Items — delete + insert.
            # Más simple y correcto que upsert parcial cuando el número de
            # items puede cambiar entre sincronizaciones.
            if detalle.Items and detalle.Items.Listado:
                await session.execute(
                    delete(LicitacionItem).where(LicitacionItem.licitacion_codigo == codigo)
                )

                # Precalcular qué códigos UNSPSC existen en la tabla.
                # El catálogo seed solo tiene niveles 2 y 4 dígitos; los items
                # reales usan 8 dígitos. Si el código no existe → None para
                # evitar FK violation (el dato queda en nombre_producto igual).
                codigos_en_items = {
                    str(it.CodigoProducto) for it in detalle.Items.Listado if it.CodigoProducto
                }
                codigos_validos: set[str] = set()
                if codigos_en_items:
                    rows_unspsc = await session.execute(
                        select(Unspsc.codigo).where(Unspsc.codigo.in_(codigos_en_items))
                    )
                    codigos_validos = {r[0] for r in rows_unspsc}

                for item_api in detalle.Items.Listado:
                    numero = item_api.Correlativo or 0
                    unspsc_raw = str(item_api.CodigoProducto) if item_api.CodigoProducto else None
                    unspsc = unspsc_raw if unspsc_raw in codigos_validos else None
                    session.add(
                        LicitacionItem(
                            licitacion_codigo=codigo,
                            numero_item=numero,
                            categoria=item_api.Categoria,
                            unspsc_codigo=unspsc,
                            nombre_producto=item_api.NombreProducto,
                            descripcion=item_api.Descripcion,
                            cantidad=item_api.Cantidad,
                            unidad=item_api.UnidadMedida,
                        )
                    )

            # Fechas — upsert por (licitacion_codigo, tipo)
            if detalle.Fechas:
                fechas_data = detalle.Fechas.model_dump()
                for campo, tipo_enum in _FECHA_MAP.items():
                    valor = fechas_data.get(campo)
                    if valor is None:
                        continue

                    existing_fecha = (
                        await session.execute(
                            select(LicitacionFecha).where(
                                and_(
                                    LicitacionFecha.licitacion_codigo == codigo,
                                    LicitacionFecha.tipo == tipo_enum,
                                )
                            )
                        )
                    ).scalar_one_or_none()

                    if existing_fecha is not None:
                        existing_fecha.fecha = valor
                    else:
                        session.add(
                            LicitacionFecha(
                                licitacion_codigo=codigo,
                                tipo=tipo_enum,
                                fecha=valor,
                            )
                        )

            # Adjudicaciones — poblar cuando la licitación está adjudicada (código 8)
            # Ver CLAUDE.md §9 para el mapeo de códigos de estado.
            if detalle.CodigoEstado == 8 and detalle.Items and detalle.Items.Listado:
                await _sync_adjudicaciones(session, codigo, detalle.Items.Listado, detalle.Fechas)

            await session.commit()

        duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)

        if era_nueva:
            stats["nueva"] += 1
            resultado = "nueva"
        else:
            stats["actualizada"] += 1
            resultado = "actualizada"

        logger.info(
            "sync_detalle_ok",
            codigo=codigo,
            resultado=resultado,
            duracion_ms=duracion_ms,
        )

        # Encolar scraping de bases si aún no se descargaron.
        # Encolar embedding de licitación (cola default, independiente del scraper).
        # Usar send_task para evitar ciclo de import.
        async with AsyncSessionLocal() as session:
            lic_check: Licitacion | None = await session.get(Licitacion, codigo)
        if lic_check is not None and lic_check.bases_descargadas_at is None:
            celery_app.send_task(
                "tasks.scrape_bases.scrape_bases_licitacion",
                args=[codigo],
                queue="scraping",
            )
            logger.debug("scrape_bases_encolado", codigo=codigo)

        # Embedding de la licitación — independiente del scraper
        celery_app.send_task(
            "tasks.embed_licitacion.embed_licitacion",
            args=[codigo],
        )
        logger.debug("embed_licitacion_encolado", codigo=codigo)

    except LicitacionNoEncontradaError:
        # Caso esperado: licitación revocada o eliminada en ChileCompra.
        # No se reintenta — es un 404 semántico, no un error transitorio.
        logger.warning(
            "sync_detalle_no_encontrada",
            codigo=codigo,
        )
        stats["no_encontrada"] += 1

    except MercadoPublicoError as e:
        duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)
        logger.error(
            "sync_detalle_api_error",
            codigo=codigo,
            error=str(e),
            status_code=e.status_code,
            duracion_ms=duracion_ms,
        )
        stats["error"] += 1
        raise  # Re-elevar para que Celery maneje autoretry

    except Exception as e:
        duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)
        logger.error(
            "sync_detalle_error_inesperado",
            codigo=codigo,
            error=str(e),
            duracion_ms=duracion_ms,
        )
        stats["error"] += 1

    finally:
        # Limpiar ticket en texto claro — regla de oro #2
        with contextlib.suppress(NameError):
            del ticket_plaintext

    return stats


@celery_app.task(  # type: ignore[untyped-decorator]
    name="tasks.sync_detalle.sync_detalle_licitacion",
    bind=True,
    autoretry_for=(MercadoPublicoError,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def sync_detalle_licitacion(self: Any, codigo: str) -> dict[str, int]:
    """Sincroniza el detalle completo de una licitación desde ChileCompra.

    Disparada automáticamente por sync_listado_diario para cada licitación
    nueva o modificada. Implementa el patrón lista → detalle obligatorio.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.

    Returns:
        Dict con contadores: nueva, actualizada, sin_cambio, no_encontrada, error.
    """
    logger.info("sync_detalle_start", codigo=codigo)
    return asyncio.run(_run(codigo))


async def _encolar_pendientes(limit: int) -> dict[str, int]:
    """Busca licitaciones sin detalle y encola hasta `limit` tasks individuales."""
    from app.db.session import AsyncSessionLocal
    from app.models.licitacion import Licitacion

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Licitacion.codigo)
            .where(Licitacion.detalle_sincronizado_at.is_(None))
            .order_by(Licitacion.fecha_publicacion.desc().nullslast())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

    codigos = [r[0] for r in rows]
    for codigo in codigos:
        sync_detalle_licitacion.apply_async(args=[codigo], queue="celery")

    logger.info(
        "sync_detalles_pendientes_encolados",
        total=len(codigos),
        limit=limit,
    )
    return {"encoladas": len(codigos)}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="tasks.sync_detalle.sync_detalles_pendientes",
    bind=True,
    acks_late=True,
    max_retries=0,
)
def sync_detalles_pendientes(self: Any, limit: int = 500) -> dict[str, int]:
    """Encola el detalle de licitaciones aún no sincronizadas.

    Diseñada para correr en ventana nocturna (22:00-07:00 CLT).
    Encola hasta `limit` tareas por corrida — con el rate limit interno
    de 1 req/s en el worker, 500 tasks ≈ 8 minutos de proceso.
    Con 9 horas de ventana nocturna y corridas cada hora se pueden
    procesar hasta ~4.500 licitaciones sin tocar la cuota diurna.
    """
    logger.info("sync_detalles_pendientes_start", limit=limit)
    return asyncio.run(_encolar_pendientes(limit))
