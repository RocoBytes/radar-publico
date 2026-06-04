"""Script de uso único: carga un ticket en la empresa demo.

Uso:
    TICKET=<valor> docker compose exec api python -m app.scripts.load_ticket_demo

El ticket nunca se loggea ni se persiste en claro (regla de oro #2).
"""

import asyncio
import os
import sys
import uuid

from app.db.session import AsyncSessionLocal
from app.services.admin.service import AdminService



async def main() -> None:
    ticket = os.environ.get("TICKET", "").strip()
    if not ticket:
        print("ERROR: variable TICKET no definida o vacía.", file=sys.stderr)
        sys.exit(1)

    # IDs fijos del entorno de desarrollo seed
    usuario_id = uuid.UUID("104eecf7-3e59-4062-b75d-0674231b750e")  # demo@radarpublico.cl
    admin_id = uuid.UUID("10fce1ce-ea33-41c6-b8a2-af54bdeffd01")  # admin@radarpublico.cl

    async with AsyncSessionLocal() as session:
        svc = AdminService(session)
        ticket_obj = await svc.cargar_ticket(
            usuario_id=usuario_id,
            ticket_plaintext=ticket,
            admin_id=admin_id,
        )
        await session.commit()

    print(
        f"Ticket cargado. Últimos 4: ...{ticket_obj.ticket_ultimos_4}  status: {ticket_obj.status}"
    )


if __name__ == "__main__":
    asyncio.run(main())
