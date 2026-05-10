"""Template de bienvenida para cuentas recién aprovisionadas."""


def render(razon_social: str, email: str, temp_password: str) -> tuple[str, str, str]:
    """Retorna (subject, html, plain_text)."""
    subject = "Bienvenido a Radar Público — acceso a tu cuenta"

    html = f"""
<html><body>
<h2>Bienvenido a Radar Público, {razon_social}</h2>
<p>Tu cuenta ha sido creada. Accedé con las siguientes credenciales:</p>
<ul>
  <li><strong>Email:</strong> {email}</li>
  <li><strong>Contraseña temporal:</strong> <code>{temp_password}</code></li>
</ul>
<p>Al ingresar por primera vez deberás cambiar tu contraseña.</p>
<p>Accedé en: <a href="https://radarpublico.cl">radarpublico.cl</a></p>
</body></html>
""".strip()

    text = (
        f"Bienvenido a Radar Público, {razon_social}.\n\n"
        f"Email: {email}\n"
        f"Contraseña temporal: {temp_password}\n\n"
        "Al ingresar por primera vez deberás cambiar tu contraseña.\n"
        "Accedé en: https://radarpublico.cl"
    )

    return subject, html, text
