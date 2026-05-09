"""Enums y mapeos para la API de Mercado Público.

CLAUDE.md §9: mapeo bidireccional centralizado aquí.
Nunca hardcodear estos números fuera de este módulo.

Mapeo de estados:
  En respuesta: número entero (CodigoEstado)
  En query:     string lowercase (estado=activas, estado=publicada, etc.)
"""

import enum


class EstadoLicitacion(enum.Enum):
    """Estado de licitación con mapeo bidireccional código ↔ string de query."""

    # (codigo_api, string_query, estado_interno)
    PUBLICADA = (5, "publicada", "publicada")
    CERRADA = (6, "cerrada", "cerrada")
    DESIERTA = (7, "desierta", "desierta")
    ADJUDICADA = (8, "adjudicada", "adjudicada")
    REVOCADA = (18, "revocada", "revocada")
    SUSPENDIDA = (19, "suspendida", "suspendida")
    # Pseudo-estado para la query de hoy — no tiene código numérico
    ACTIVAS = (None, "activas", "publicada")

    def __init__(
        self, codigo: int | None, query_string: str, estado_interno: str
    ) -> None:
        self.codigo = codigo
        self.query_string = query_string
        self.estado_interno = estado_interno

    @classmethod
    def from_codigo(cls, codigo: int) -> "EstadoLicitacion":
        """Convierte un código numérico de la API al enum."""
        for estado in cls:
            if estado.codigo == codigo:
                return estado
        return cls.PUBLICADA  # fallback seguro para códigos desconocidos

    @classmethod
    def from_query_string(cls, query_string: str) -> "EstadoLicitacion":
        """Convierte el string de query al enum."""
        for estado in cls:
            if estado.query_string == query_string:
                return estado
        raise ValueError(f"Estado de query desconocido: {query_string!r}")


class TipoLicitacion(str, enum.Enum):
    """Tipos de licitación del Mercado Público (Anexo B del spec)."""

    L1 = "L1"
    LE = "LE"
    LP = "LP"
    LS = "LS"
    A1 = "A1"
    B1 = "B1"
    J1 = "J1"
    F1 = "F1"
    E1 = "E1"
    CO = "CO"
    B2 = "B2"
    A2 = "A2"
    D1 = "D1"
    E2 = "E2"
    C2 = "C2"
    C1 = "C1"
    F2 = "F2"
    F3 = "F3"
    G2 = "G2"
    G1 = "G1"
    R1 = "R1"
    CA = "CA"
    SE = "SE"
    LR = "LR"
    DESCONOCIDO = "DESCONOCIDO"

    @classmethod
    def from_string(cls, value: str | None) -> "TipoLicitacion":
        """Convierte string al enum, con fallback seguro."""
        if value is None:
            return cls.DESCONOCIDO
        try:
            return cls(value.upper())
        except ValueError:
            return cls.DESCONOCIDO


class ModalidadCompra(enum.Enum):
    """Modalidad de compra (CodigoTipo en la API)."""

    LICITACION_PUBLICA = (1, "Licitación Pública")
    TRATO_DIRECTO = (2, "Trato Directo")
    CONVENIO_MARCO = (3, "Convenio Marco")
    COMPRA_AGIL = (4, "Compra Ágil")
    DESCONOCIDO = (None, "Desconocido")

    def __init__(self, codigo: int | None, descripcion: str) -> None:
        self.codigo = codigo
        self.descripcion = descripcion

    @classmethod
    def from_codigo(cls, codigo: int | None) -> "ModalidadCompra":
        """Convierte el código numérico al enum."""
        for modalidad in cls:
            if modalidad.codigo == codigo:
                return modalidad
        return cls.DESCONOCIDO
