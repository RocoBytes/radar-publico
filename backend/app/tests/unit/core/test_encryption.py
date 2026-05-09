"""Tests unitarios para app.core.encryption.

Casos cubiertos:
- Round-trip: cifrar + descifrar devuelve el original.
- IVs únicos: el mismo plaintext produce ciphertexts distintos.
- Falla con clave incorrecta.
- Falla con ciphertext alterado.
- Falla con clave corta.
- Falla con payload malformado.
"""

import base64
import os
from unittest.mock import patch

from cryptography.exceptions import InvalidTag
import pytest

from app.core.encryption import decrypt_ticket, encrypt_ticket


class TestEncryptionRoundTrip:
    """El cifrado y descifrado deben ser inversos perfectos."""

    def test_round_trip_basico(self) -> None:
        ticket = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
        cifrado = encrypt_ticket(ticket)
        assert decrypt_ticket(cifrado) == ticket

    def test_round_trip_ticket_corto(self) -> None:
        ticket = "ABCD"
        assert decrypt_ticket(encrypt_ticket(ticket)) == ticket

    def test_round_trip_caracteres_especiales(self) -> None:
        ticket = "Ñoño-ünicode-€-ñ-2026"
        assert decrypt_ticket(encrypt_ticket(ticket)) == ticket

    def test_round_trip_ticket_largo(self) -> None:
        ticket = "A" * 500
        assert decrypt_ticket(encrypt_ticket(ticket)) == ticket


class TestIVsUnicos:
    """Cada cifrado debe producir un ciphertext distinto (nonce aleatorio)."""

    def test_mismo_plaintext_produce_ciphertexts_distintos(self) -> None:
        ticket = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
        cifrado_1 = encrypt_ticket(ticket)
        cifrado_2 = encrypt_ticket(ticket)
        # Ciphertexts distintos (nonce diferente)
        assert cifrado_1 != cifrado_2
        # Pero ambos descifran al mismo plaintext
        assert decrypt_ticket(cifrado_1) == ticket
        assert decrypt_ticket(cifrado_2) == ticket

    def test_nonces_distintos_en_multiples_cifrados(self) -> None:
        ticket = "test"
        ciphertexts = {encrypt_ticket(ticket) for _ in range(10)}
        # Los 10 deben ser distintos
        assert len(ciphertexts) == 10


class TestClaveIncorrecta:
    """Descifrar con clave incorrecta debe lanzar InvalidTag."""

    def test_falla_con_clave_incorrecta(self) -> None:
        ticket = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
        cifrado = encrypt_ticket(ticket)

        # Descifrar con clave diferente
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = "otra_clave_de_32_bytes_exactos__"
            with pytest.raises(InvalidTag):
                decrypt_ticket(cifrado)

    def test_falla_con_ciphertext_alterado(self) -> None:
        ticket = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
        cifrado = encrypt_ticket(ticket)

        # Decodificar, alterar un byte y re-encodear
        payload = bytearray(base64.urlsafe_b64decode(cifrado))
        payload[-1] ^= 0xFF  # flip del último byte (en el tag GCM)
        cifrado_alterado = base64.urlsafe_b64encode(bytes(payload)).decode()

        with pytest.raises(InvalidTag):
            decrypt_ticket(cifrado_alterado)


class TestValidacionClave:
    """La clave debe tener al menos 32 bytes."""

    def test_falla_con_clave_corta(self) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = "corta"
            with pytest.raises(ValueError, match="32 bytes"):
                encrypt_ticket("cualquier ticket")

    def test_acepta_clave_exactamente_32_bytes(self) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = "A" * 32
            cifrado = encrypt_ticket("ticket")
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = "A" * 32
            assert decrypt_ticket(cifrado) == "ticket"

    def test_acepta_clave_mas_larga_que_32_bytes(self) -> None:
        """Claves más largas se truncan a 32 bytes — comportamiento documentado."""
        clave_larga = "A" * 40
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = clave_larga
            cifrado = encrypt_ticket("ticket")
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.encryption_key = clave_larga
            assert decrypt_ticket(cifrado) == "ticket"


class TestPayloadMalformado:
    """Payloads malformados deben fallar limpiamente."""

    def test_falla_con_payload_vacio(self) -> None:
        payload_vacio = base64.urlsafe_b64encode(b"").decode()
        with pytest.raises(ValueError, match="inválido"):
            decrypt_ticket(payload_vacio)

    def test_falla_con_payload_solo_nonce(self) -> None:
        """Payload con solo nonce (12 bytes) sin ciphertext."""
        solo_nonce = base64.urlsafe_b64encode(os.urandom(12)).decode()
        with pytest.raises(ValueError, match="inválido"):
            decrypt_ticket(solo_nonce)
