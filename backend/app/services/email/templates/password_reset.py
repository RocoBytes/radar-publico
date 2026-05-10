"""Template de recuperación de contraseña."""


def render(reset_url: str) -> tuple[str, str, str]:
    """Retorna (subject, html, plain_text)."""
    subject = "Radar Público — recuperación de contraseña"

    html = f"""
<html><body>
<h2>Recuperación de contraseña</h2>
<p>Recibimos una solicitud para restablecer tu contraseña.</p>
<p>Hacé clic en el siguiente enlace (válido por 30 minutos):</p>
<p><a href="{reset_url}">{reset_url}</a></p>
<p>Si no solicitaste este cambio, podés ignorar este mensaje.</p>
</body></html>
""".strip()

    text = (
        "Recuperación de contraseña — Radar Público\n\n"
        "Recibimos una solicitud para restablecer tu contraseña.\n"
        f"Accedé al siguiente enlace (válido por 30 minutos):\n{reset_url}\n\n"
        "Si no solicitaste este cambio, podés ignorar este mensaje."
    )

    return subject, html, text
