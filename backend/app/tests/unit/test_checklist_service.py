"""Tests unitarios del servicio de checklist documental.

Verifica lógica de negocio de bootstrap_from_analysis con mocks de AsyncSession.
No toca la base de datos real.

Tests:
- test_bootstrap_idempotente: doble llamada no duplica ítems (ON CONFLICT)
- test_bootstrap_sin_analisis: retorna vacío sin error cuando no hay análisis
- test_bootstrap_documentos_vacios: retorna vacío cuando documentos_obligatorios = []
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.models.enums import AnalisisStatus, ChecklistItemEstado, ChecklistItemOrigen
from app.services.pipeline.checklist import bootstrap_from_analysis


def _make_pipeline_item(
    empresa_id: uuid.UUID | None = None,
    licitacion_codigo: str = "LC-TEST-001",
) -> MagicMock:
    item = MagicMock()
    item.id = uuid.uuid4()
    item.empresa_id = empresa_id or uuid.uuid4()
    item.licitacion_codigo = licitacion_codigo
    return item


def _make_analisis(
    documentos_obligatorios: list[Any] | None = None,
    status: AnalisisStatus = AnalisisStatus.listo,
) -> MagicMock:
    analisis = MagicMock()
    analisis.id = uuid.uuid4()
    analisis.licitacion_codigo = "LC-TEST-001"
    analisis.status = status
    analisis.documentos_obligatorios = documentos_obligatorios
    return analisis


def _make_checklist_item(nombre: str = "Doc 1") -> MagicMock:
    item = MagicMock()
    item.id = uuid.uuid4()
    item.pipeline_item_id = uuid.uuid4()
    item.nombre = nombre
    item.descripcion = None
    item.obligatorio = False
    item.estado = ChecklistItemEstado.pendiente
    item.origen = ChecklistItemOrigen.ia_generado
    item.orden = 0
    item.completed_at = None
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    item.created_at = now
    item.updated_at = now
    return item


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    return session


def _scalar_result(value: Any) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def _scalars_result(values: list[Any]) -> MagicMock:
    """Simula execute().scalars().all() retornando una lista."""
    scalars = MagicMock()
    scalars.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = values[0] if values else None
    # rowcount para el INSERT ON CONFLICT
    result.rowcount = 1
    return result


@pytest.mark.asyncio
class TestBootstrapFromAnalysis:
    """Tests para bootstrap_from_analysis con mocks de AsyncSession."""

    async def test_bootstrap_sin_analisis(self) -> None:
        """Cuando no existe análisis para la licitación, retorna lista vacía sin error."""
        empresa_id = uuid.uuid4()
        pipeline_item = _make_pipeline_item(empresa_id=empresa_id)

        session = _make_session()

        call_count = 0

        async def mock_execute(query: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Verificación de ownership — retorna el pipeline_item
                return _scalar_result(pipeline_item)
            elif call_count == 2:
                # Búsqueda de AnalisisBases — no hay análisis
                return _scalar_result(None)
            else:
                # Lista de ítems actuales — vacía
                return _scalars_result([])

        session.execute = mock_execute

        result = await bootstrap_from_analysis(session, pipeline_item.id, empresa_id)

        assert result.creados == 0
        assert result.omitidos == 0
        assert result.items == []

    async def test_bootstrap_documentos_vacios(self) -> None:
        """Cuando análisis existe pero documentos_obligatorios es [], retorna vacío."""
        empresa_id = uuid.uuid4()
        pipeline_item = _make_pipeline_item(empresa_id=empresa_id)
        analisis = _make_analisis(documentos_obligatorios=[])

        session = _make_session()

        call_count = 0

        async def mock_execute(query: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _scalar_result(pipeline_item)
            elif call_count == 2:
                return _scalar_result(analisis)
            else:
                return _scalars_result([])

        session.execute = mock_execute

        result = await bootstrap_from_analysis(session, pipeline_item.id, empresa_id)

        assert result.creados == 0
        assert result.omitidos == 0
        assert result.items == []

    async def test_bootstrap_idempotente(self) -> None:
        """Doble llamada no duplica ítems: ON CONFLICT devuelve rowcount=0 en la segunda.

        Primera llamada: rowcount=1 por cada documento → creados=N.
        Segunda llamada: rowcount=0 por cada documento → omitidos=N, creados=0.
        """
        empresa_id = uuid.uuid4()
        pipeline_item = _make_pipeline_item(empresa_id=empresa_id)
        documentos = [
            {"nombre": "Certificado RSE", "descripcion": "Cert ambiental", "obligatorio": True},
            {"nombre": "Garantía de seriedad", "obligatorio": True},
        ]
        analisis = _make_analisis(documentos_obligatorios=documentos)

        # Items creados después del primer bootstrap
        items_existentes = [
            _make_checklist_item("Certificado RSE"),
            _make_checklist_item("Garantía de seriedad"),
        ]

        # --- Primera llamada: rowcount=1 (inserción exitosa) ---
        session_1 = _make_session()
        call_count_1 = 0
        insert_count_1 = 0

        async def mock_execute_1(query: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count_1, insert_count_1
            call_count_1 += 1
            if call_count_1 == 1:
                return _scalar_result(pipeline_item)
            elif call_count_1 == 2:
                return _scalar_result(analisis)
            else:
                # Primer INSERT o lista final
                query_str = str(query) if hasattr(query, "__str__") else ""
                if "INSERT INTO" in query_str or (hasattr(query, "text") and "INSERT" in str(getattr(query, "text", ""))):
                    insert_count_1 += 1
                    r = MagicMock()
                    r.rowcount = 1  # inserción exitosa
                    return r
                # Lista final de ítems
                return _scalars_result(items_existentes)

        session_1.execute = mock_execute_1

        result_1 = await bootstrap_from_analysis(session_1, pipeline_item.id, empresa_id)

        # Primera llamada debe reportar creados=2
        assert result_1.creados == 2
        assert result_1.omitidos == 0

        # --- Segunda llamada: rowcount=0 (ON CONFLICT DO NOTHING activo) ---
        session_2 = _make_session()
        call_count_2 = 0

        async def mock_execute_2(query: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count_2
            call_count_2 += 1
            if call_count_2 == 1:
                return _scalar_result(pipeline_item)
            elif call_count_2 == 2:
                return _scalar_result(analisis)
            else:
                query_str = str(query) if hasattr(query, "__str__") else ""
                if "INSERT INTO" in query_str or (hasattr(query, "text") and "INSERT" in str(getattr(query, "text", ""))):
                    r = MagicMock()
                    r.rowcount = 0  # conflicto — DO NOTHING
                    return r
                return _scalars_result(items_existentes)

        session_2.execute = mock_execute_2

        result_2 = await bootstrap_from_analysis(session_2, pipeline_item.id, empresa_id)

        # Segunda llamada debe reportar omitidos=2, creados=0
        assert result_2.creados == 0
        assert result_2.omitidos == 2
        # La lista de ítems es la misma — no se duplicó
        assert len(result_2.items) == len(items_existentes)
