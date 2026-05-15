"""Servicio de envío de mensajes WhatsApp vía Twilio REST API.

Usa httpx (ya en requirements) — sin agregar nueva dependencia.

Flujo:
  - Si WHATSAPP_ENABLED=false → raise WhatsAppDeshabilitadoError (no se llama a Twilio).
  - Si credenciales vacías → raise WhatsAppConfigError.
  - En éxito → retorna el message SID de Twilio.

La lógica de "si está deshabilitado, saltar" vive en el caller
(procesar_notificaciones). Este módulo siempre intenta enviar si se llama.
"""

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()

_TWILIO_MESSAGES_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
)


class WhatsAppConfigError(Exception):
    """Credenciales de WhatsApp no configuradas."""


class WhatsAppEnvioError(Exception):
    """Error al enviar mensaje vía Twilio."""


async def send_whatsapp(to_number: str, body: str) -> str:
    """Envía un mensaje WhatsApp. Retorna el Twilio message SID.

    Args:
        to_number: Número destino en formato E.164 (ej: +56912345678).
        body: Cuerpo del mensaje. Debe coincidir con un template aprobado por Meta.

    Returns:
        SID del mensaje creado en Twilio.

    Raises:
        WhatsAppConfigError: Si las credenciales no están configuradas.
        WhatsAppEnvioError: Si Twilio retorna un error HTTP.
    """
    sid = settings.whatsapp_account_sid
    auth_token = settings.whatsapp_auth_token
    from_number = settings.whatsapp_from_number

    if not all([sid, auth_token, from_number]):
        raise WhatsAppConfigError(
            "WHATSAPP_ACCOUNT_SID, WHATSAPP_AUTH_TOKEN o WHATSAPP_FROM_NUMBER no configurados"
        )

    url = _TWILIO_MESSAGES_URL.format(sid=sid)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            auth=(sid, auth_token),
            data={
                "From": f"whatsapp:{from_number}",
                "To": f"whatsapp:{to_number}",
                "Body": body,
            },
        )

    if resp.status_code >= 400:
        raise WhatsAppEnvioError(
            f"Twilio error {resp.status_code}: {resp.text[:300]}"
        )

    message_sid: str = resp.json().get("sid", "")
    logger.info(
        "whatsapp_enviado",
        message_sid=message_sid,
        to_hash=hash(to_number),
    )
    return message_sid
