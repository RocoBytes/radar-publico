"""Cifrado AES-256-GCM para tickets de ChileCompra.

Regla de oro #2: tickets siempre cifrados en BD, descifrar solo en memoria.

Implementación:
- Algoritmo: AES-256-GCM (AEAD — cifra y autentica en una operación)
- Clave: 32 bytes leídos de ENCRYPTION_KEY del entorno
- Nonce: 12 bytes aleatorios por cada cifrado (os.urandom)
- Formato en BD: base64url(nonce[12] || ciphertext+tag)
  El nonce siempre ocupa los primeros 12 bytes al decodificar.
- Tag GCM: 16 bytes, incluido al final del ciphertext por AESGCM

Por qué no Fernet: Fernet usa AES-128, no AES-256. CLAUDE.md exige 256.
Por qué GCM y no CBC: GCM autentica el ciphertext (AEAD). CBC sin MAC
manual es propenso a padding oracle attacks.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

# Tamaños fijos del protocolo
_NONCE_SIZE = 12  # bytes — estándar para AES-GCM
_KEY_SIZE = 32  # bytes — AES-256


def _get_key() -> bytes:
    """Deriva la clave de 32 bytes desde ENCRYPTION_KEY del entorno.

    Acepta la clave como string UTF-8 y la convierte a bytes.
    Si tiene menos de 32 bytes, falla explícitamente — nunca padear en silencio.
    """
    raw = settings.encryption_key.encode("utf-8")
    if len(raw) < _KEY_SIZE:
        raise ValueError(
            f"ENCRYPTION_KEY debe tener al menos {_KEY_SIZE} bytes "
            f"(tiene {len(raw)}). Generá una con: openssl rand -base64 32 | head -c 32"
        )
    # Usar exactamente los primeros 32 bytes si es más larga
    return raw[:_KEY_SIZE]


def encrypt_ticket(plaintext: str) -> str:
    """Cifra un ticket de ChileCompra con AES-256-GCM.

    Args:
        plaintext: El ticket en texto claro. Nunca se persiste.

    Returns:
        String base64url con nonce (12 bytes) + ciphertext+tag concatenados.
        Cada llamada produce un resultado distinto (nonce aleatorio).

    Raises:
        ValueError: Si ENCRYPTION_KEY es inválida.
    """
    key = _get_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    # AESGCM.encrypt devuelve ciphertext || tag (tag al final, 16 bytes)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Concatenar nonce + ciphertext+tag y codificar en base64url
    payload = nonce + ciphertext_with_tag
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_ticket(ciphertext_b64: str) -> str:
    """Descifra un ticket de ChileCompra.

    El ticket descifrado solo debe existir en memoria y usarse
    inmediatamente para hacer la request a la API. Nunca persistir.

    Args:
        ciphertext_b64: String base64url producido por encrypt_ticket().

    Returns:
        El ticket en texto claro.

    Raises:
        ValueError: Si el payload está malformado (muy corto).
        cryptography.exceptions.InvalidTag: Si el ciphertext fue alterado
            o la clave es incorrecta. Dejar que suba — el caller decide
            cómo manejarlo.
    """
    key = _get_key()
    payload = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))
    if len(payload) <= _NONCE_SIZE:
        raise ValueError(
            f"Payload cifrado inválido: largo {len(payload)} ≤ nonce size {_NONCE_SIZE}"
        )
    nonce = payload[:_NONCE_SIZE]
    ciphertext_with_tag = payload[_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    # decrypt lanza InvalidTag si la autenticación falla
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    return plaintext_bytes.decode("utf-8")
