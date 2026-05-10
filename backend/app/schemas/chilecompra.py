"""Schemas Pydantic 2 para la API de ChileCompra (Mercado Público).

Reflejan la estructura CRUDA de la API — no el modelo interno de la app.
Los campos usan los nombres originales de la API (PascalCase) para
facilitar el mapeo 1:1 sin transformaciones intermedias.

Estructura de respuesta validada contra la API real (2026-05-09):
  GET /servicios/v1/publico/licitaciones.json
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CompradorAPI(BaseModel):
    """Organismo comprador tal como lo devuelve la API."""

    CodigoOrganismo: str | None = None
    NombreOrganismo: str | None = None
    RutUnidad: str | None = None
    CodigoUnidad: str | None = None
    NombreUnidad: str | None = None
    DireccionUnidad: str | None = None
    ComunaUnidad: str | None = None
    RegionUnidad: str | None = None
    RutUsuario: str | None = None
    CodigoUsuario: str | None = None
    NombreUsuario: str | None = None
    CargoUsuario: str | None = None


class FechasAPI(BaseModel):
    """Bloque de fechas de una licitación. Todos los campos son opcionales."""

    FechaCreacion: datetime | None = None
    FechaCierre: datetime | None = None
    FechaInicio: datetime | None = None
    FechaFinal: datetime | None = None
    FechaPubRespuestas: datetime | None = None
    FechaActoAperturaTecnica: datetime | None = None
    FechaActoAperturaEconomica: datetime | None = None
    FechaPublicacion: datetime | None = None
    FechaAdjudicacion: datetime | None = None
    FechaEstimadaAdjudicacion: datetime | None = None
    FechaSoporteFisico: datetime | None = None
    FechaTiempoEvaluacion: datetime | None = None
    FechaEstimadaFirma: datetime | None = None
    FechaVisitaTerreno: datetime | None = None
    FechaEntregaAntecedentes: datetime | None = None


class ItemListadoAPI(BaseModel):
    """Item de una licitación en el bloque Items.Listado."""

    Correlativo: int | None = None
    CodigoProducto: int | None = None
    CodigoCategoria: str | None = None
    Categoria: str | None = None
    NombreProducto: str | None = None
    Descripcion: str | None = None
    UnidadMedida: str | None = None
    Cantidad: float | None = None
    Adjudicacion: object | None = None


class ItemsAPI(BaseModel):
    """Bloque Items de una licitación."""

    Cantidad: int = 0
    Listado: list[ItemListadoAPI] = Field(default_factory=list)


class LicitacionDetalleAPI(BaseModel):
    """Licitación con detalle completo — respuesta del endpoint ?codigo=XXX."""

    CodigoExterno: str
    Nombre: str
    CodigoEstado: int | None = None
    Estado: str | None = None
    Descripcion: str | None = None
    FechaCierre: datetime | None = None

    # Comprador
    Comprador: CompradorAPI | None = None

    # Clasificación
    CodigoTipo: int | None = None
    Tipo: str | None = None
    TipoConvocatoria: str | None = None
    Modalidad: int | None = None

    # Monto
    Moneda: str | None = None
    MontoEstimado: float | None = None
    VisibilidadMonto: int | None = None

    # Contrato
    EsRenovable: int | None = None  # API devuelve 0/1, no bool
    UnidadTiempoDuracionContrato: int | None = None
    TiempoDuracionContrato: str | None = None
    UnidadTiempoContratoLicitacion: str | None = None

    # Contacto
    NombreResponsablePago: str | None = None
    EmailResponsablePago: str | None = None
    NombreResponsableContrato: str | None = None
    EmailResponsableContrato: str | None = None
    FonoResponsableContrato: str | None = None

    # Fechas (bloque anidado)
    Fechas: FechasAPI | None = None

    # Items
    Items: ItemsAPI | None = None

    # Métricas
    CantidadReclamos: int | None = None
    DiasCierreLicitacion: str | None = None

    @field_validator("EsRenovable", mode="before")
    @classmethod
    def parse_es_renovable(cls, v: object) -> int | None:
        """La API devuelve 0/1 como int. Lo normalizamos para el modelo."""
        if v is None:
            return None
        return int(str(v))


class LicitacionListItemAPI(BaseModel):
    """Licitación en modo listado — respuesta del endpoint ?estado=activas.

    Solo 4 campos — para info completa se necesita el endpoint ?codigo=XXX.
    """

    CodigoExterno: str
    Nombre: str
    CodigoEstado: int
    FechaCierre: datetime | None = None


class LicitacionesResponseAPI(BaseModel):
    """Envelope raíz de la API para endpoints de licitaciones."""

    Cantidad: int = 0
    FechaCreacion: datetime | None = None
    Version: str | None = None
    Listado: list[LicitacionListItemAPI | LicitacionDetalleAPI] = Field(
        default_factory=list
    )


class LicitacionesListadoResponseAPI(BaseModel):
    """Respuesta del endpoint de listado (?estado=activas, ?fecha=ddmmaaaa)."""

    Cantidad: int = 0
    FechaCreacion: datetime | None = None
    Version: str | None = None
    Listado: list[LicitacionListItemAPI] = Field(default_factory=list)


class LicitacionDetalleResponseAPI(BaseModel):
    """Respuesta del endpoint de detalle (?codigo=XXX)."""

    Cantidad: int = 0
    FechaCreacion: datetime | None = None
    Version: str | None = None
    Listado: list[LicitacionDetalleAPI] = Field(default_factory=list)
