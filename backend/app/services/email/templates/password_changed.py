"""Template de confirmación de cambio de contraseña."""


def render() -> tuple[str, str, str]:
    """Retorna (subject, html, plain_text)."""
    subject = "Radar Público — tu contraseña fue cambiada"

    html = """
<html><body>
<h2>Contraseña actualizada</h2>
<p>Tu contraseña en Radar Público fue cambiada exitosamente.</p>
<p>Si no realizaste este cambio, contactá a soporte de inmediato.</p>
</body></html>
""".strip()

    text = (
        "Tu contraseña en Radar Público fue cambiada exitosamente.\n"
        "Si no realizaste este cambio, contactá a soporte de inmediato."
    )

    return subject, html, text
