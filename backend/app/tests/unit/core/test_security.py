"""Tests unitarios para app.core.security."""

from datetime import UTC, datetime, timedelta
import re
import string
from unittest.mock import patch

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_temporary_password,
    hash_password,
    hash_token,
    verify_password,
)


class TestBcrypt:
    def test_round_trip(self) -> None:
        hashed = hash_password("MiPassword123!")
        assert verify_password("MiPassword123!", hashed)

    def test_verify_falla_con_password_incorrecto(self) -> None:
        hashed = hash_password("MiPassword123!")
        assert not verify_password("OtroPassword456!", hashed)

    def test_hashes_distintos_para_el_mismo_plaintext(self) -> None:
        pw = "MiPassword123!"
        assert hash_password(pw) != hash_password(pw)


class TestJWT:
    def test_encode_decode_round_trip(self) -> None:
        token = create_access_token("test-user-id")
        payload = decode_access_token(token)
        assert payload.sub == "test-user-id"
        assert payload.type == "access"

    def test_decode_falla_token_expirado(self) -> None:
        token = create_access_token("u1", expires_delta=timedelta(seconds=-1))
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)

    def test_decode_falla_con_secret_incorrecto(self) -> None:
        token = create_access_token("u1")
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.jwt_secret = "wrong_secret"
            mock_settings.jwt_algorithm = "HS256"
            with pytest.raises(InvalidTokenError):
                decode_access_token(token)

    def test_decode_falla_con_tipo_incorrecto(self) -> None:
        from jose import jwt

        from app.config import settings

        payload = {
            "sub": "u1",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
            "type": "refresh",  # tipo incorrecto
        }
        token = jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        with pytest.raises(InvalidTokenError, match="Tipo de token incorrecto"):
            decode_access_token(token)


class TestHashToken:
    def test_estable_mismo_input(self) -> None:
        assert hash_token("abc") == hash_token("abc")

    def test_sha256_longitud_correcta(self) -> None:
        result = hash_token("test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_distintos_inputs_distintos_hashes(self) -> None:
        assert hash_token("a") != hash_token("b")


class TestGenerateTemporaryPassword:
    def test_longitud_por_defecto(self) -> None:
        pw = generate_temporary_password()
        assert len(pw) == 12

    def test_longitud_personalizada(self) -> None:
        pw = generate_temporary_password(16)
        assert len(pw) == 16

    def test_tiene_mayuscula(self) -> None:
        for _ in range(20):
            pw = generate_temporary_password()
            assert any(c in string.ascii_uppercase for c in pw)

    def test_tiene_minuscula(self) -> None:
        for _ in range(20):
            pw = generate_temporary_password()
            assert any(c in string.ascii_lowercase for c in pw)

    def test_tiene_digito(self) -> None:
        for _ in range(20):
            pw = generate_temporary_password()
            assert any(c in string.digits for c in pw)

    def test_tiene_simbolo(self) -> None:
        for _ in range(20):
            pw = generate_temporary_password()
            assert any(c in "!@#$%^&*" for c in pw)

    def test_cumple_politica_regex(self) -> None:
        pattern = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,}$")
        for _ in range(50):
            pw = generate_temporary_password()
            assert pattern.match(pw), f"Password no cumple política: {pw!r}"
