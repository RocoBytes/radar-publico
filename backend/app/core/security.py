"""Toolkit de seguridad puro: hashing, JWT y generación de tokens.

Sin estado, sin BD, sin async — facilita tests unitarios y reúso.
Reglas de oro: #3 bcrypt cost 12, #5 JWT 15min + refresh rotativo.
"""

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
import string

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class AccessTokenPayload(BaseModel):
    sub: str
    exp: datetime
    iat: datetime
    type: str


class InvalidTokenError(Exception):
    pass


def hash_password(plaintext: str) -> str:
    return str(_pwd_context.hash(plaintext))


def verify_password(plaintext: str, hashed: str) -> bool:
    return bool(_pwd_context.verify(plaintext, hashed))


def hash_token(plaintext: str) -> str:
    """SHA-256 hex. Usado para almacenar refresh y reset tokens."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Crea JWT HS256 con sub=user_id, exp, iat, type='access'."""
    now = datetime.now(UTC)
    delta = expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + delta,
        "type": "access",
    }
    encoded = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return str(encoded)


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decodifica y valida el JWT. Lanza InvalidTokenError si es inválido."""
    try:
        raw = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        if raw.get("type") != "access":
            raise InvalidTokenError("Tipo de token incorrecto")
        return AccessTokenPayload(**raw)
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


def create_refresh_token() -> tuple[str, str]:
    """Genera un refresh token. Retorna (plaintext, sha256_hex)."""
    plaintext = secrets.token_urlsafe(48)
    return plaintext, hash_token(plaintext)


def generate_reset_token() -> tuple[str, str]:
    """Genera un token de reset de password. Retorna (plaintext, sha256_hex)."""
    plaintext = secrets.token_urlsafe(48)
    return plaintext, hash_token(plaintext)


def generate_temporary_password(length: int = 12) -> str:
    """Genera contraseña temporal cumpliendo la política (regla #3).

    Garantiza al menos: 1 mayúscula, 1 minúscula, 1 dígito, 1 símbolo.
    """
    symbols = "!@#$%^&*"
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(symbols),
    ]
    alphabet = string.ascii_letters + string.digits + symbols
    remaining = [secrets.choice(alphabet) for _ in range(max(0, length - 4))]
    combined = required + remaining
    secrets.SystemRandom().shuffle(combined)
    return "".join(combined)
