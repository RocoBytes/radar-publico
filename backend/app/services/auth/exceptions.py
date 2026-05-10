"""Excepciones del dominio de autenticación."""


class InvalidCredentialsError(Exception):
    """Credenciales inválidas. Mensaje genérico — regla de oro #4."""


class AccountLockedError(Exception):
    """Cuenta bloqueada por intentos fallidos."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Cuenta bloqueada por {retry_after_seconds}s")


class AccountSuspendedError(Exception):
    """Cuenta suspendida por admin."""


class InvalidTokenError(Exception):
    """Token inválido, expirado o revocado."""


class MustChangePasswordError(Exception):
    """El usuario debe cambiar su contraseña antes de continuar."""


class WeakPasswordError(Exception):
    """La contraseña no cumple la política de seguridad."""
