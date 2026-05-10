"""Servicio de envío de email.

Dev (environment != production): SMTP a MailHog via smtplib en run_in_executor.
Prod: Resend API.
Sin agregar dependencias nuevas — smtplib es stdlib, resend ya está en requirements.
"""

import asyncio
import email.mime.multipart
import email.mime.text
from functools import partial
import smtplib

import resend
import structlog

from app.config import settings

logger = structlog.get_logger()


def _send_smtp_sync(
    to: str,
    subject: str,
    html: str,
    text: str,
) -> None:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(email.mime.text.MIMEText(text, "plain", "utf-8"))
    msg.attach(email.mime.text.MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.sendmail(settings.email_from, [to], msg.as_string())


async def send_email(to: str, subject: str, html: str, text: str) -> None:
    """Envía un email. En dev usa MailHog; en prod usa Resend."""
    if settings.is_production:
        resend.api_key = settings.resend_api_key
        await asyncio.get_event_loop().run_in_executor(
            None,
            partial(
                resend.Emails.send,
                {
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            ),
        )
        logger.info("email_sent_resend", to_hash=hash(to), subject=subject)
    else:
        await asyncio.get_event_loop().run_in_executor(
            None,
            partial(_send_smtp_sync, to, subject, html, text),
        )
        logger.info("email_sent_mailhog", subject=subject)
