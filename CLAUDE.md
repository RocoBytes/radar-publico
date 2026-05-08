# CLAUDE.md

> Contexto, convenciones y reglas del proyecto **Radar Público**. Este archivo es leído automáticamente por Claude Code y debe ser consultado por cualquier desarrollador nuevo antes de tocar código.

---

## 1. ¿Qué es Radar Público?

**Radar Público** es una plataforma SaaS B2B de inteligencia comercial sobre el Mercado Público de Chile. Ayuda a empresas proveedoras del Estado a detectar, analizar y postular a licitaciones de forma más eficiente.

**Usuarios objetivo:** empresas chilenas de cualquier rubro que venden al Estado vía Mercado Público. Cobertura nacional (16 regiones).

**Modelo de negocio:** SaaS por suscripción, con cuentas aprovisionadas manualmente por el admin tras recibir pago externo. **No hay self-service signup** ni planes gratuitos en v1.

**Diferenciadores frente a la competencia (LicitaLAB, LicitaPyme):**
- Vista de tres horizontes en navegación principal: pasado (análisis de mercado), presente (oportunidades activas), futuro (anticipación con Plan Anual + patrones de renovación).
- Filtrado multi-capa: UNSPSC estructurado + full-text en español + búsqueda semántica con embeddings.
- Pipeline de seguimiento integrado con generación automática de borradores de propuesta técnica (planeado v2).

**Documentos de referencia obligatorios** antes de implementar cualquier feature:
- `docs/spec.md` — qué construir (epics + user stories con criterios de aceptación)
- `docs/data.md` — modelo de datos completo
- `schema.sql` — source of truth del schema de Postgres
- `docs/roadmap.md` — qué se construye en este sprint
- `README.md` — cómo levantar el entorno local

---

## 2. Stack tecnológico

Usar **exactamente estas versiones**. No actualizar sin discusión previa.

### Backend
- **Python 3.12**
- **FastAPI 0.115** — framework web
- **SQLAlchemy 2.0** (async) + **Alembic 1.13** — ORM y migraciones
- **Pydantic 2.9** — validación y settings
- **PostgreSQL 16** + extensión **pgvector** — base de datos
- **Redis 7** — cache + broker de Celery
- **Celery 5.4** + **Celery Beat** — workers asíncronos y cron
- **httpx** + **tenacity** + **aiolimiter** — cliente HTTP con retries y rate limit
- **pymupdf** + **unstructured** — parseo de PDFs
- **LiteLLM** sobre **Anthropic API** — capa de abstracción de IA
- **Voyage AI** — embeddings (1024 dimensiones)
- **boto3** — Cloudflare R2 (compatible S3)
- **Resend** — email transaccional
- **WhatsApp Business API** vía Twilio o 360Dialog
- **Sentry** — observabilidad de errores
- **structlog** — logging estructurado

### Frontend
- **Next.js 15** (App Router) + **TypeScript 5**
- **TailwindCSS 3** (no v4 hasta que sea estable)
- **shadcn/ui** — componentes
- **TanStack Query 5** — fetching y cache
- **TanStack Table** — tablas complejas (especialmente en panel admin)
- **Zustand** — estado global cliente
- **React Hook Form** + **Zod** — formularios y validación
- **Recharts** — gráficos del dashboard cliente
- **date-fns** — manejo de fechas (NO moment.js)

### Infraestructura
- **Docker** + **Docker Compose** — desarrollo local y despliegue
- **Caddy** — reverse proxy con TLS automático en producción
- **Digital Ocean Droplet** (4 GB RAM mínimo) — hosting de v1
- **Cloudflare R2** — almacenamiento de PDFs y archivos

---

## 3. Estructura del proyecto

```
radar-publico/
├── CLAUDE.md                       ← este archivo
├── README.md                       ← cómo levantar el proyecto
├── Makefile                        ← comandos comunes
├── docker-compose.yml              ← stack de desarrollo
├── docker-compose.prod.yml         ← override para producción
├── schema.sql                      ← schema inicial de Postgres
├── .env.example                    ← plantilla de variables
├── docs/
│   ├── spec.md                     ← especificación funcional
│   ├── data.md                     ← modelo de datos documentado
│   ├── roadmap.md                  ← sprints y prioridades
│   ├── architecture.md             ← decisiones arquitectónicas (ADRs)
│   └── runbook.md                  ← operación e incidentes
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                    ← migraciones
│   └── app/
│       ├── main.py                 ← entrypoint FastAPI
│       ├── celery_app.py           ← entrypoint Celery
│       ├── config.py               ← Settings con pydantic-settings
│       ├── api/
│       │   ├── v1/                 ← endpoints del cliente
│       │   └── admin/              ← endpoints del panel admin
│       ├── core/                   ← auth, security, encryption
│       ├── db/
│       │   ├── session.py          ← engine y sessions
│       │   └── base.py
│       ├── models/                 ← SQLAlchemy models (refleja schema.sql)
│       ├── schemas/                ← Pydantic schemas (DTOs)
│       ├── services/               ← lógica de negocio
│       │   ├── chilecompra/        ← cliente de la API + sincronización
│       │   ├── llm/                ← capa de abstracción IA (LiteLLM)
│       │   ├── search/             ← búsqueda multi-capa
│       │   ├── notifications/      ← email, whatsapp, in-app
│       │   ├── pdf/                ← parseo y RAG
│       │   └── pipeline/           ← lógica del pipeline de seguimiento
│       ├── tasks/                  ← Celery tasks
│       ├── scripts/                ← seeds, backfills, utilidades CLI
│       └── tests/
│           ├── unit/
│           ├── integration/
│           └── conftest.py
├── frontend/                       ← app cliente (Next.js)
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/                    ← App Router
│       │   ├── (auth)/             ← login, reset password
│       │   ├── (dashboard)/        ← rutas protegidas
│       │   └── layout.tsx
│       ├── components/
│       │   ├── ui/                 ← shadcn primitives
│       │   └── feature/            ← componentes de dominio
│       ├── lib/
│       │   ├── api.ts              ← cliente HTTP tipado
│       │   ├── auth.ts
│       │   └── utils.ts
│       ├── hooks/
│       ├── stores/                 ← Zustand
│       └── types/
├── frontend-admin/                 ← panel admin (Next.js separado)
│   └── ... (misma estructura)
├── nginx/
│   └── Caddyfile
└── scripts/
    ├── init-db.sh
    └── backup.sh
```

---

## 4. Convenciones de código

### General
- **Idioma:** comentarios y docstrings en **español** (es proyecto chileno y la mayoría del dominio se piensa en español). Identificadores de código en **inglés** (variables, funciones, clases). Nombres del dominio (entidades de negocio) en **español** (ej: `licitacion`, `proveedor`, `pipeline_item`) — la consistencia con el modelo de datos importa más que el inglés purista.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) en español: `feat(auth): agregar reset de contraseña`, `fix(sync): manejar timeout en API ChileCompra`, `docs(spec): aclarar criterios US-3.1`. Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.
- **Branches:** `feat/...`, `fix/...`, `chore/...`. PR siempre a `main` con squash merge.

### Python (backend)
- **Linter:** `ruff` con config en `pyproject.toml`. Correr antes de commitear: `ruff check --fix && ruff format`.
- **Type checker:** `mypy` en modo `strict`. **Sin excepciones** salvo librerías sin stubs.
- **Tipos siempre.** Toda función pública con anotaciones de parámetros y retorno.
- **Async first.** Endpoints, queries, llamadas HTTP — todo asíncrono. Usar `asyncpg` para Postgres, `httpx.AsyncClient` para HTTP.
- **Imports ordenados** automático con ruff (stdlib → terceros → locales).
- **Docstrings estilo Google** para servicios y funciones complejas. Una línea es suficiente para funciones simples.
- **Nombres:**
  - Tablas y columnas: `snake_case` (en español de dominio: `licitaciones`, `fecha_cierre`).
  - Modelos SQLAlchemy: `PascalCase` (`Licitacion`, `OrdenCompra`).
  - Schemas Pydantic: sufijo según uso (`LicitacionCreate`, `LicitacionUpdate`, `LicitacionResponse`).
  - Constantes: `SCREAMING_SNAKE_CASE`.
  - Funciones privadas: prefijo `_`.

### TypeScript (frontend)
- **Linter:** ESLint + Prettier con config compartida.
- **Strict mode** en `tsconfig.json`. `noImplicitAny`, `strictNullChecks`, todo activo.
- **Sin `any` salvo casos justificados** (con comentario explicando el motivo).
- **Sin `as` para casts** salvo cuando interactúas con APIs externas y validas con Zod después.
- **Server Components por defecto.** Solo `"use client"` cuando realmente necesites interactividad.
- **Componentes:** `PascalCase`. Hooks: `useCamelCase`. Utilidades: `camelCase`.
- **Una página, un archivo.** No mezclar componentes de página con componentes reutilizables.
- **Imports absolutos** desde `@/` (configurado en `tsconfig.json`).

### SQL
- **Snake case** para nombres de tablas y columnas, siempre.
- **Plurales** para tablas (`licitaciones`, no `licitacion`).
- **PK en `id` UUID v4** para entidades de aplicación. Para entidades de Mercado Público mantener su clave natural (`codigo` para licitaciones, `rut` para proveedores).
- **Timestamps en `timestamptz`** siempre. UTC en BD, conversión en presentación.
- **Foreign keys con `ON DELETE` explícito** según la semántica del negocio.
- **Índices nombrados explícitamente** con prefijo `idx_<tabla>_<columnas>`.
- **Migraciones con Alembic.** Nunca tocar `schema.sql` directamente después del primer release; todo cambio es una migración.

---

## 5. Reglas de oro (no-negociables)

Estas reglas tienen prioridad sobre cualquier sugerencia de implementación. Si una de estas se cruza con un atajo "más rápido", **siempre gana la regla**.

### Seguridad
1. **Nunca commitear `.env`, claves API, tokens o passwords.** Usar `.env.example` como plantilla. Pre-commit hook con `git-secrets` o `gitleaks` activo.
2. **Tickets de ChileCompra siempre cifrados.** Columna `tickets_api.ticket_cifrado` con AES-256 usando `ENCRYPTION_KEY` del entorno. Descifrar solo en memoria al hacer la request, nunca persistir en claro.
3. **Passwords con bcrypt cost factor 12.** Nunca MD5, SHA1, ni "contraseñas débiles aceptables en dev".
4. **Mensajes de error de auth genéricos.** "Credenciales inválidas" — nunca distinguir entre "email no existe" y "password incorrecto" (enumeración de usuarios).
5. **JWT con expiración corta (15 min) + refresh token rotativo (7 días).** Refresh tokens hasheados en BD, revocables individualmente.
6. **Rate limiting obligatorio en login** (5 intentos/15 min por IP) y en endpoints públicos (100 req/min por IP).
7. **CORS estricto.** Solo orígenes explícitos en `CORS_ORIGINS`. Nunca `*` en producción.
8. **MFA obligatorio para cuentas admin.** TOTP mínimo.
9. **Headers de seguridad:** HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
10. **Validación de entrada en todos los endpoints.** Pydantic en backend, Zod en frontend. Nunca confiar en el cliente.

### Privacidad y cumplimiento
11. **Ley 19.628 y 20.575.** Consentimiento explícito en onboarding, política de privacidad publicada, derecho a eliminación implementado.
12. **Sin PII en logs.** No loggear emails, RUTs, nombres, teléfonos. Solo IDs internos.
13. **Sin PII en errores de Sentry.** Configurar `before_send` para sanitizar.
14. **Auditoría de acciones sensibles.** Login, cambio de password, creación/suspensión de cuentas, carga de tickets, impersonación de admin → todo a `eventos_auditoria`.

### Datos y rendimiento
15. **Un ticket por cliente, no compartido.** Cada empresa usa su propio ticket de ChileCompra. Nunca usar un ticket compartido para múltiples clientes (viola TOS y satura cuota).
16. **Backfill desde Datos Abiertos, no desde la API.** Cargas masivas históricas usan los CSVs públicos de `datos-abiertos.chilecompra.cl`. La API solo para datos del día.
17. **Bulk loads en horario nocturno** (22:00–07:00 CLT) por recomendación de ChileCompra.
18. **Rate limit interno antes de llamar la API:** máximo 5-10 req/segundo por ticket. Backoff exponencial ante 429 o 5xx.
19. **Nunca queries N+1.** Si necesitas datos de relaciones, usa `selectinload`/`joinedload` o un único query con joins.
20. **Paginación obligatoria** en todo endpoint que retorne listas. Default 25, máximo 100 por request.
21. **Cache agresivo de detalles de licitación.** Una vez sincronizado el detalle, no volver a consultar a menos que cambie de estado.

### IA
22. **Toda llamada a LLM pasa por la capa de abstracción** (`services/llm/`). Nunca importar `anthropic` directamente desde un endpoint o tarea.
23. **Logging de uso de IA obligatorio** en `llm_usage_log` (provider, modelo, tokens, costo, feature). Sin esto no podemos controlar costos.
24. **Rate limit por cliente en chat IA.** 100 mensajes/día por defecto, ajustable por plan.
25. **Streaming en respuestas largas.** Especialmente chat con bases — primer token < 2 segundos.
26. **Citas obligatorias en chat con bases.** Cada respuesta incluye referencia a chunk_id y página del PDF original.

### Operación
27. **Healthcheck en `/health`** retornando estado de Postgres, Redis y workers.
28. **Backups diarios automáticos** con prueba de restore mensual.
29. **Toda tarea Celery debe ser idempotente.** Si se reintenta, no debe duplicar efectos.
30. **Migraciones siempre reversibles** salvo casos extraordinarios (con justificación en el commit).

---

## 6. Comandos comunes

```bash
# === Levantar entorno ===
make up                  # levanta todo el stack
make down                # detiene
make reset               # detiene y BORRA volúmenes (cuidado)
make logs-api            # logs del backend
make logs-worker         # logs del worker
make ps                  # estado de servicios

# === Acceso ===
make shell-api           # bash dentro del contenedor api
make shell-db            # psql en la base de datos
make shell-redis         # redis-cli

# === Base de datos ===
make migrate                              # aplica migraciones pendientes
make migrate-create                       # crea nueva migración (autogenerate)
make seed                                 # carga datos seed (catálogos UNSPSC, regiones)
make backup                               # backup manual de Postgres

# === Tests y calidad ===
docker compose exec api pytest                          # corre tests
docker compose exec api pytest tests/unit               # solo unitarios
docker compose exec api pytest -k "test_auth"           # filtrados por nombre
docker compose exec api ruff check --fix                # lint con auto-fix
docker compose exec api ruff format                     # format
docker compose exec api mypy app                        # type check
docker compose exec web npm run lint                    # lint frontend
docker compose exec web npm run typecheck               # type check frontend

# === Producción (Digital Ocean) ===
make prod-up                              # levanta prod
make prod-deploy                          # pull + build + restart + migrate
make prod-logs                            # logs combinados
```

---

## 7. Flujo de trabajo

### Para implementar una feature nueva
1. **Leer la US correspondiente** en `docs/spec.md`. Confirmar criterios de aceptación.
2. **Verificar el modelo de datos** en `docs/data.md` — ¿la feature requiere cambios al schema?
3. Si requiere cambios al schema → crear migración con `make migrate-create` y aplicarla.
4. Implementar en el orden: **modelos → schemas → servicios → endpoints → tests → frontend**.
5. **Tests obligatorios** para servicios y endpoints. Cobertura mínima 70% en `services/`.
6. PR con descripción que referencia la US: `feat(auth): implementa US-2.1 login`.
7. Code review (incluso si eres el único dev: pasan 24h y revisas con ojo fresco).

### Antes de cada commit
```bash
# Backend
docker compose exec api ruff check --fix
docker compose exec api ruff format
docker compose exec api mypy app
docker compose exec api pytest

# Frontend
docker compose exec web npm run lint
docker compose exec web npm run typecheck
docker compose exec web npm test
```

Hook pre-commit con `pre-commit` framework configurado en el repo. **No skipear con `--no-verify`** salvo emergencias documentadas.

### Antes de cada deploy a producción
1. Tests pasan.
2. Migraciones probadas en staging (o local con datos de producción anonimizados).
3. Revisar `docs/runbook.md` por si la feature introduce nueva operación.
4. Tag de versión semántica: `v0.x.y`.
5. Deploy con `make prod-deploy`.
6. Verificar `/health` y métricas en Sentry los siguientes 30 minutos.

---

## 8. Cosas que NO se deben hacer

Lista corta de errores comunes que ya se tomó la decisión de evitar:

- ❌ **No agregar nuevas dependencias sin justificación.** Cada librería es deuda. Pregúntate primero: ¿el stdlib lo cubre? ¿una de las que ya tengo lo cubre?
- ❌ **No usar ORMs distintos a SQLAlchemy 2.0** (no Tortoise, no SQLModel para esto, no peewee).
- ❌ **No mezclar SQLAlchemy sync y async** en el mismo flujo. Backend es 100% async.
- ❌ **No usar Tailwind v4** hasta que sea estable y todas sus deps comunes lo soporten.
- ❌ **No cambiar de Next.js App Router a Pages Router** ni mezclar ambos.
- ❌ **No introducir GraphQL.** REST es suficiente y más simple para este alcance.
- ❌ **No agregar Kubernetes** hasta tener al menos 50 clientes activos.
- ❌ **No reescribir el cliente de ChileCompra** para usar otra librería HTTP. `httpx` es la elegida.
- ❌ **No usar `localStorage` para tokens.** Cookies httpOnly + sameSite=Lax.
- ❌ **No subir secretos a GitHub** ni en el código ni en imágenes Docker.
- ❌ **No saltarse el panel admin** para tareas operacionales recurrentes. Si haces una operación 3+ veces por SQL directo, agregar al panel admin.
- ❌ **No exponer `5432`, `6379` o `5555`** en producción. Solo `80` y `443` vía Caddy.
- ❌ **No hacer scrapping del portal Mercado Público desde el contenedor del API.** Esto va en un worker separado con Playwright.
- ❌ **No olvidar `fecha` en formato `ddmmaaaa`** sin separadores al consumir la API ChileCompra. Es la trampa #1.

---

## 9. Particularidades del dominio (importante)

Cosas específicas de Mercado Público de Chile que el código asume y debes respetar:

### Estados de licitación (mapeo dual)
- En la **respuesta** vienen como número entero.
- En la **query** se envían como string lowercase.

| Código | String query | Significado |
|---|---|---|
| 5 | `publicada` | En recepción de ofertas |
| 6 | `cerrada` | En evaluación |
| 7 | `desierta` | Sin ofertas válidas |
| 8 | `adjudicada` | Resuelta |
| 18 | `revocada` | Anulada |
| 19 | `suspendida` | En pausa |
| – | `activas` | (pseudo-estado) Todas las publicadas hoy |

Mapeo en `app/services/chilecompra/enums.py`. Nunca hardcodear estos números fuera de ahí.

### Cuota de la API
- **10.000 requests/día por ticket.** No negociable.
- Patrón obligatorio: **lista → detalle**. La consulta por fecha o estado devuelve info básica; el detalle completo requiere segunda llamada por código.
- **Las bases técnicas en PDF NO están en la API.** Hay que descargarlas por scrapping del portal de Mercado Público con Playwright.

### Formato de fecha
- API ChileCompra: `ddmmaaaa` sin separadores (ej: `07052026` para 7 de mayo de 2026).
- BD interna: `timestamptz` UTC.
- UI cliente: zona horaria America/Santiago.
- Helper canónico en `app/services/chilecompra/utils.py:format_fecha_api()`. Usar siempre.

### Una empresa = un usuario = un ticket
- En v1 no soportamos multi-usuario por empresa.
- Si un cliente quiere asociar otra empresa, se crea otra cuenta separada con su propio ticket.
- El modelo de datos **ya** soporta multi-usuario (vía tabla pivot pendiente para v2), pero la lógica actual asume 1:1.

### UNSPSC
- Catálogo jerárquico: 2/4/6/8 dígitos.
- El filtrado por rubro se hace sobre `licitacion_items.unspsc_codigo`, no sobre la licitación completa (una licitación puede combinar rubros).
- El catálogo UNSPSC se carga una vez en seed inicial. No se modifica en runtime.

### Cobertura
- Cobertura nacional desde día 1. Las 16 regiones de Chile.
- Catálogo de regiones y comunas en seed. No se modifican.

---

## 10. Referencias y enlaces

### Documentación oficial
- API ChileCompra: https://www.chilecompra.cl/api/
- Datos Abiertos: https://datos-abiertos.chilecompra.cl
- Portal Mercado Público: https://www.mercadopublico.cl
- Documentación API endpoints: documentar en `docs/architecture.md` cuando se descubran particularidades.

### Stack
- FastAPI: https://fastapi.tiangolo.com
- SQLAlchemy 2.0 async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- pgvector: https://github.com/pgvector/pgvector
- Anthropic API: https://docs.claude.com
- LiteLLM: https://docs.litellm.ai
- shadcn/ui: https://ui.shadcn.com

### Cumplimiento legal Chile
- Ley 19.628: https://www.bcn.cl/leychile/navegar?idNorma=141599
- Ley 20.575: https://www.bcn.cl/leychile/navegar?idNorma=1024292

---

## 11. Notas para Claude (LLM asistiendo en desarrollo)

Si estás leyendo esto como Claude Code o asistente IA durante el desarrollo:

- **Siempre consulta `docs/spec.md`** antes de implementar una feature. Las user stories tienen criterios de aceptación que deben respetarse.
- **No inventes endpoints, modelos o estructuras** que no estén documentadas. Si falta documentación, **pregunta al humano** antes de avanzar.
- **No alucines columnas de BD.** Verifica `schema.sql` o `docs/data.md` antes de escribir queries.
- **Respeta las versiones del stack.** No sugieras "mejor usa la última versión de X".
- **Sigue las convenciones de naming** de la sección 4 sin excepción.
- **Las reglas de oro de la sección 5 son inviolables.** Si una sugerencia tuya las rompe, repiénsalo.
- **Para cambios al schema**, siempre proponer migración Alembic, nunca editar `schema.sql` directamente.
- **Para llamadas a IA**, siempre usar la capa de abstracción en `services/llm/`, nunca importar `anthropic` directo.
- **Para llamadas a la API ChileCompra**, siempre usar el cliente en `services/chilecompra/`, nunca `httpx` directo.
- **Si encuentras inconsistencias** entre este archivo y otro doc, **reportalas explícitamente** al humano antes de proceder.
- **Idioma de respuesta**: español por defecto (proyecto chileno). Código en inglés con dominio en español.

---

*Última actualización: 2026-05-07. Versionar este archivo cuando cambien decisiones arquitectónicas.*
