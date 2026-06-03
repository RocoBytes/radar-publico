"""Excepciones del dominio admin."""


class CuentaYaExisteError(Exception):
    """Email o RUT ya está registrado en el sistema."""

    def __init__(self, campo: str) -> None:
        self.campo = campo
        super().__init__(f"Ya existe una cuenta con ese {campo}")


class CuentaNoEncontradaError(Exception):
    """Usuario no encontrado o eliminado."""


class EmpresaNoEncontradaError(Exception):
    """El usuario no tiene empresa asociada."""
