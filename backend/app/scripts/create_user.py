"""CLI de aprovisionamiento de cuentas (US-1.1).

Uso:
    docker compose exec api python -m app.scripts.create_user \\
        --email cliente@empresa.cl \\
        --rut 76.123.456-7 \\
        --razon-social "Mi Empresa SpA"

El password temporal se imprime UNA SOLA VEZ. Se envía email de bienvenida
capturado por MailHog en desarrollo (http://localhost:8025).
"""

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog

from app.core.security import generate_temporary_password, hash_password
from app.db.session import AsyncSessionLocal
from app.models.empresa import Empresa
from app.models.enums import UserRole, UserStatus
from app.models.eventos_auditoria import AuditAction
from app.models.usuario import Usuario
from app.services.auth.audit import log_event
from app.services.email import sender as email_sender
from app.services.email.templates import welcome as tpl_welcome

logger = structlog.get_logger()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aprovisiona una cuenta de usuario en Radar Público"
    )
    parser.add_argument("--email", required=True, help="Email del usuario")
    parser.add_argument(
        "--rut",
        required=False,
        default="",
        help="RUT de la empresa (requerido para rol proveedor)",
    )
    parser.add_argument(
        "--razon-social",
        required=False,
        default="",
        dest="razon_social",
        help="Razón social (requerida para rol proveedor)",
    )
    parser.add_argument(
        "--rol",
        choices=["proveedor", "admin"],
        default="proveedor",
        help="Rol del usuario (default: proveedor)",
    )
    return parser.parse_args()


async def _create(
    email: str,
    rut: str,
    razon_social: str,
    rol: UserRole,
) -> None:
    temp_password = generate_temporary_password()

    async with AsyncSessionLocal() as session:
        # Verificar duplicados antes de intentar insertar
        existing = await session.execute(select(Usuario).where(Usuario.email == email))
        if existing.scalar_one_or_none():
            print(f"ERROR: El email {email!r} ya existe.", file=sys.stderr)
            sys.exit(1)

        if rol == UserRole.proveedor and rut:
            existing_rut = await session.execute(
                select(Empresa).where(Empresa.rut == rut)
            )
            if existing_rut.scalar_one_or_none():
                print(f"ERROR: El RUT {rut!r} ya está registrado.", file=sys.stderr)
                sys.exit(1)

        user = Usuario(
            email=email,
            password_hash=hash_password(temp_password),
            rol=rol,
            status=UserStatus.active,
            must_change_password=True,
        )
        session.add(user)
        await session.flush()  # obtener user.id antes de crear empresa

        empresa: Empresa | None = None
        if rol == UserRole.proveedor and rut and razon_social:
            empresa = Empresa(
                usuario_id=user.id,
                rut=rut,
                razon_social=razon_social,
            )
            session.add(empresa)

        await log_event(
            session,
            AuditAction.USER_CREATED,
            usuario_id=user.id,
            empresa_id=empresa.id if empresa else None,
            info={"rol": rol.value},
        )

        try:
            await session.commit()
        except IntegrityError as exc:
            print(f"ERROR de integridad: {exc}", file=sys.stderr)
            sys.exit(1)

        # Enviar email de bienvenida (capturado por MailHog en dev)
        nombre_display = razon_social or email
        subject, html, text = tpl_welcome.render(nombre_display, email, temp_password)
        await email_sender.send_email(email, subject, html, text)

    _print_banner(email, temp_password, rol)
    logger.info("user.created", user_id=str(user.id), rol=rol.value)


def _print_banner(email: str, temp_password: str, rol: UserRole) -> None:
    print()
    print("=" * 60)
    print("  CUENTA CREADA EXITOSAMENTE")
    print("=" * 60)
    print(f"  Email : {email}")
    print(f"  Rol   : {rol.value}")
    print(f"  Pass  : {temp_password}")
    print()
    print("  ⚠  ESTE PASSWORD SE MUESTRA UNA SOLA VEZ.")
    print("  El usuario debe cambiarlo al primer ingreso.")
    print("=" * 60)
    print()


def main() -> None:
    args = _parse_args()
    rol = UserRole(args.rol)

    if rol == UserRole.proveedor and (not args.rut or not args.razon_social):
        print(
            "ERROR: --rut y --razon-social son requeridos para rol proveedor.",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(
        _create(
            email=args.email,
            rut=args.rut,
            razon_social=args.razon_social,
            rol=rol,
        )
    )


if __name__ == "__main__":
    main()
