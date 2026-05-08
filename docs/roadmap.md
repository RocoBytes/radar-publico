# Roadmap — Radar Público

> Plan de implementación de la v1 organizado en sprints de 2 semanas. Este documento referencia user stories del `spec.md` por su ID. Cuando un sprint se replanifica, se edita **solo** este archivo.

**Última actualización:** 2026-05-07
**Sprint actual:** Sprint 0 (preparación)
**Target lanzamiento v1:** Sprint 5 (semana 12)

---

## Filosofía del plan

- **Sprints de 2 semanas.** Cortos para forzar entregas reales y permitir corrección rápida.
- **Cada sprint termina con algo demostrable.** Aunque sea un endpoint funcionando o un workflow incompleto. No "infra invisible" durante 4 semanas.
- **Riesgo técnico al inicio.** La sincronización con ChileCompra es la pieza más arriesgada. Va antes que cualquier feature visual.
- **MVP funcional al sprint 5.** A partir del sprint 6 el sistema ya tiene clientes reales y el roadmap se ajusta según feedback.
- **El panel admin va en paralelo, no después.** Cada sprint agrega lo mínimo del admin que necesitas para operar lo que se construyó. Si dejas el admin para el final, vas a operar por SQL directo durante meses.

---

## Sprint 0 — Preparación (semana 0)

**Objetivo:** entorno listo para empezar a desarrollar el sprint 1 sin fricciones.

**Tareas:**
- [ ] Repo Git inicializado con estructura de carpetas (sección 3 del CLAUDE.md).
- [ ] Docker Compose levantando: postgres, redis, api (hello world), worker (hello world), web (Next.js inicial).
- [ ] Schema inicial cargado en Postgres desde `schema.sql`.
- [ ] Catálogos seed cargados: regiones, comunas, UNSPSC.
- [ ] Variables de entorno documentadas en `.env.example` y `.env` local funcional.
- [ ] Pre-commit hooks configurados (ruff, mypy, eslint, gitleaks).
- [ ] CI básico en GitHub Actions: corre tests y linters en cada PR.
- [ ] Ticket de ChileCompra obtenido (el tuyo personal, para desarrollo).
- [ ] API key de Anthropic generada y validada con un curl.
- [ ] Cuenta de Voyage AI creada para embeddings.
- [ ] Cuenta de Cloudflare R2 con bucket `radar-publico-dev`.
- [ ] Cuenta de Resend con dominio verificado para emails.
- [ ] Sentry proyecto creado.

**Criterio de done:** corres `make up`, accedes a `localhost:3000` (Next.js placeholder) y `localhost:8000/docs` (Swagger vacío). Todos los servicios verde en `make ps`.

**Entregable demostrable:** "el stack levanta limpio en cualquier máquina".

---

## Sprint 1 — Fundamentos: auth + ingesta básica (semanas 1-2)

**Objetivo:** validar el riesgo técnico mayor (sincronización ChileCompra) y tener auth funcional para crear las primeras cuentas.

**User stories del spec:**
- US-2.1 Login
- US-2.2 Logout
- US-2.4 Cambiar contraseña
- US-1.1 (parcial) Crear cuenta de proveedor (versión mínima, solo CLI por ahora)

**Tareas backend:**
- [ ] Modelos SQLAlchemy de las tablas `usuarios`, `empresas`, `tickets_api`, `refresh_tokens` con tests unitarios.
- [ ] Helpers de seguridad: hash bcrypt, generación JWT, cifrado AES-256 para tickets.
- [ ] Endpoint `POST /api/v1/auth/login`.
- [ ] Endpoint `POST /api/v1/auth/logout`.
- [ ] Endpoint `POST /api/v1/auth/refresh`.
- [ ] Endpoint `POST /api/v1/auth/change-password`.
- [ ] Middleware de autenticación con dependencias FastAPI.
- [ ] Rate limiting en `/login` (5 intentos / 15 min por IP).
- [ ] Script CLI `python -m app.scripts.create_user` para aprovisionar cuentas (mientras no hay panel admin).
- [ ] **Cliente HTTP de ChileCompra** en `services/chilecompra/client.py`:
  - [ ] `MercadoPublicoClient` con httpx async, rate limit interno (5 req/s), retries con tenacity, backoff exponencial.
  - [ ] Helpers de formato de fecha `ddmmaaaa`.
  - [ ] Mapeo bidireccional de estados.
  - [ ] Logging a tabla `api_quota_log`.
  - [ ] Tests con respuestas mockeadas (responses guardados en `tests/fixtures/`).
- [ ] **Worker de sincronización mínimo:**
  - [ ] Tarea `sync_listado_diario` que consulta `?estado=activas` y persiste licitaciones nuevas (solo info básica, sin detalle aún).
  - [ ] Beat schedule cada 15 minutos.
- [ ] **Backfill desde Datos Abiertos:**
  - [ ] Script `python -m app.scripts.backfill --months 24` que descarga CSVs públicos y carga histórico de licitaciones, OCs y adjudicaciones.
  - [ ] Validar que se cargan al menos 100K licitaciones de los últimos 24 meses.

**Tareas frontend:**
- [ ] Setup Next.js con shadcn/ui, TailwindCSS, TanStack Query.
- [ ] Página de login funcional con React Hook Form + Zod.
- [ ] Página de cambio de contraseña obligatorio (cuando `must_change_password = true`).
- [ ] Layout protegido (redirige a login si no hay sesión).
- [ ] Cliente HTTP tipado con interceptor de refresh token automático.
- [ ] Página placeholder del dashboard (solo "Hola, [empresa]").

**Riesgo a validar este sprint:**
- ✅ La sincronización con ChileCompra funciona sin saturar la cuota.
- ✅ El backfill de Datos Abiertos no truena con datasets grandes.

**Criterio de done:** un usuario creado por CLI puede hacer login, recibe JWT, accede al dashboard placeholder. La BD tiene > 100K licitaciones cargadas. El worker está corriendo y agrega licitaciones nuevas cada 15 minutos.

**Entregable demostrable:** demo de login + dashboard vacío + query SQL mostrando licitaciones del día sincronizadas en tiempo real.

---

## Sprint 2 — Detalle de licitaciones + bases (semanas 3-4)

**Objetivo:** completar el pipeline de ingesta para tener todos los datos necesarios para mostrar al cliente.

**User stories del spec:**
- (No hay US directas; este sprint es infraestructura crítica)

**Tareas backend:**
- [ ] Modelos `licitacion_items`, `criterios_evaluacion`, `licitacion_fechas`.
- [ ] Tarea `sync_detalle_licitacion`: consume cola, llama API por código, persiste detalle completo.
- [ ] Idempotencia y manejo de licitaciones que cambian (re-ingesta con detección por hash).
- [ ] **Scraper de bases (Playwright):**
  - [ ] Worker separado `playwright_scraper` que navega el portal de Mercado Público con el código de licitación.
  - [ ] Descarga de PDFs adjuntos (bases técnicas, administrativas, anexos).
  - [ ] Persistencia de archivos en R2.
  - [ ] Registro de paths en `documentos_bases`.
  - [ ] Manejo de fallas y reintentos.
- [ ] **Parseo de PDFs:**
  - [ ] Servicio `services/pdf/parser.py` con pymupdf primario, unstructured fallback.
  - [ ] Extracción de texto a `documentos_bases.texto_extraido`.
  - [ ] Chunking semántico con overlap.
- [ ] **Embeddings:**
  - [ ] Servicio `services/llm/embeddings.py` con Voyage AI vía LiteLLM.
  - [ ] Tarea `procesa_embeddings_chunks`: genera embeddings de chunks de PDF.
  - [ ] Tarea `procesa_embeddings_licitaciones`: genera embeddings del título + descripción.
  - [ ] Persistencia en `pgvector` con índice HNSW.
- [ ] **Catálogos:**
  - [ ] Sincronización de organismos desde API.
  - [ ] Sincronización de proveedores desde Datos Abiertos.

**Tareas frontend:**
- [ ] (Mínimo este sprint, todo el foco en backend.)
- [ ] Refinamiento del layout: sidebar con navegación inicial (Dashboard, Buscar, Configuración).

**Tareas admin (mínimo):**
- [ ] Vista interna en Flower o página admin simple para monitorear estado de jobs.

**Riesgo a validar este sprint:**
- ✅ El scraping de PDFs es estable y no bloquea el portal.
- ✅ Los embeddings se generan dentro del presupuesto de costos esperado.

**Criterio de done:** una licitación cualquiera de los últimos 7 días tiene en BD: detalle completo, items con UNSPSC, criterios de evaluación, fechas, PDFs descargados a R2, chunks con embeddings.

**Entregable demostrable:** consulta SQL `SELECT * FROM licitaciones WHERE codigo = 'XXX'` con todas las relaciones llenas; query semántico `ORDER BY embedding <=> :query` retorna resultados relevantes.

---

## Sprint 3 — Onboarding + búsqueda básica (semanas 5-6)

**Objetivo:** que un cliente nuevo complete onboarding por sí solo y pueda hacer búsquedas con resultados relevantes.

**User stories del spec:**
- US-3.1 Wizard de configuración inicial
- US-3.2 Datos de la empresa
- US-3.4 Definir intereses (rubros)
- US-5.1 Búsqueda libre
- US-5.2 Filtros estructurados (subset: UNSPSC, estado, región, fecha cierre)
- US-5.4 Resultados paginados

**Tareas backend:**
- [ ] Endpoints CRUD de empresa: `GET/PATCH /api/v1/empresas/me`.
- [ ] Endpoints de intereses: `GET/POST/DELETE /api/v1/intereses`.
- [ ] Endpoint de validación de RUT chileno (algoritmo dígito verificador).
- [ ] **Búsqueda multi-capa** en `services/search/`:
  - [ ] Capa UNSPSC: filtro por items con `LIKE 'codigo%'`.
  - [ ] Capa full-text: `tsvector` con configuración `es_unaccent`.
  - [ ] Capa semántica: query por similitud coseno sobre `embedding`.
  - [ ] Combinador con scoring ponderado.
- [ ] Endpoint `GET /api/v1/licitaciones/search` con filtros estructurados, paginación y sorting.
- [ ] Endpoint `POST /api/v1/intereses/sugerir-keywords` que usa Claude para expandir keywords del cliente (opcional, nice-to-have).

**Tareas frontend:**
- [ ] Wizard de onboarding con stepper:
  - [ ] Paso 1: datos de la empresa (form completo con validación de RUT).
  - [ ] Paso 2: instrucciones para conseguir el ticket de ChileCompra (esperar admin para activar).
  - [ ] Paso 3: selector de intereses con árbol UNSPSC (componente custom o react-arborist).
  - [ ] Paso 4: keywords adicionales con autocompletado.
- [ ] Bloqueo del dashboard hasta completar onboarding.
- [ ] Página de búsqueda con:
  - [ ] Input de búsqueda libre.
  - [ ] Sidebar con filtros (UNSPSC, estado, región, fecha cierre).
  - [ ] Lista paginada de resultados con cards.
  - [ ] Estado vacío y de carga.

**Tareas admin (mínimo):**
- [ ] Listado básico de cuentas pendientes de activar (que enviaron datos pero no tienen ticket cargado).

**Criterio de done:** un usuario creado por CLI puede completar el onboarding por sí solo. Una búsqueda "soporte mesa de ayuda" retorna resultados relevantes mezclando matches exactos y semánticos. Los filtros aplicados refinan correctamente.

**Entregable demostrable:** screencast de un usuario nuevo entrando, completando onboarding en < 5 minutos, y haciendo su primera búsqueda con resultados útiles.

---

## Sprint 4 — Dashboard + detalle + pipeline + radares (semanas 7-8)

**Objetivo:** sistema usable de punta a punta para un cliente. Todo el flujo "presente": ver, decidir, trackear.

**User stories del spec:**
- US-4.1 Vista resumen del dashboard
- US-4.2 Gráfico de licitaciones por segmento
- US-4.3 Indicador de salud del sistema
- US-5.3 Búsquedas guardadas (radares)
- US-6.1 Resumen de la licitación
- US-6.2 Bases y documentos (versión read-only sin chat)
- US-6.3 Calendario de la licitación
- US-8.1 Listado de oportunidades
- US-10.1 Estados del pipeline
- US-10.2 Vista pipeline (lista, sin Kanban todavía)
- US-10.3 Notas por licitación

**Tareas backend:**
- [ ] **Sistema de scoring de relevancia:**
  - [ ] Algoritmo en `services/scoring/relevance.py` que combina match UNSPSC + región + keywords + similitud semántica + experiencia con organismo.
  - [ ] Score 0-100 con justificación estructurada en JSON.
  - [ ] Tarea `recalcula_scores` que se dispara al cambiar intereses del cliente.
- [ ] Endpoint `GET /api/v1/dashboard/resumen` con KPIs (oportunidades activas, nuevas hoy, próximas a cerrar, en pipeline).
- [ ] Endpoint `GET /api/v1/dashboard/segmentos` para gráfico por UNSPSC.
- [ ] Endpoint `GET /api/v1/licitaciones/:codigo` con detalle completo.
- [ ] Endpoints de radares: CRUD completo (`GET/POST/PATCH/DELETE /api/v1/radares`).
- [ ] Tarea `ejecuta_radares_diarios` que evalúa cada radar contra licitaciones nuevas y crea entradas en `pipeline_items` con `estado=nueva`.
- [ ] Endpoints del pipeline: `GET /api/v1/pipeline`, `PATCH /api/v1/pipeline/:id` (cambio de estado), `POST /api/v1/pipeline/:id/notas`.

**Tareas frontend:**
- [ ] Dashboard funcional:
  - [ ] Tarjetas KPI con datos reales.
  - [ ] Gráfico de barras por segmento UNSPSC con Recharts.
  - [ ] Lista top 5 oportunidades del día.
  - [ ] Calendario semanal con cierres próximos.
- [ ] Página de detalle de licitación con:
  - [ ] Header con score + justificación.
  - [ ] Tabs: Resumen, Bases (lista de PDFs descargables), Calendario, Inteligencia (vacío por ahora).
  - [ ] Acciones: marcar como interés, descartar, agregar nota.
  - [ ] Link al portal Mercado Público.
- [ ] Página de gestión de radares (crear, editar, activar/desactivar).
- [ ] Página de pipeline con vista lista (Kanban en sprint posterior).
- [ ] Notificaciones in-app básicas (icono de campana en header con unread count).

**Tareas admin:**
- [ ] Listado completo de cuentas (US-1.1 versión completa con UI).
- [ ] Botón "Crear cuenta nueva" con formulario.
- [ ] Vista de carga/validación de tickets (US-1.3 completa).

**Criterio de done:** un cliente nuevo puede entrar, ver oportunidades relevantes en el dashboard, abrir una licitación, leer sus bases, marcarla como interés, agregarle una nota y verla en su pipeline. Todo el flow sin tocar la BD manualmente.

**Entregable demostrable:** **flujo completo de una sesión de un cliente real**, desde login hasta licitación marcada en pipeline. Esto es el MVP usable.

---

## Sprint 5 — Notificaciones + IA chat con bases + analítica básica (semanas 9-10)

**Objetivo:** cerrar el círculo del MVP con las features que generan engagement (alertas) y diferenciación (chat IA con bases).

**User stories del spec:**
- US-3.5 Configurar notificaciones (parcial: email + in-app, sin WhatsApp todavía)
- US-2.3 Recuperar contraseña
- US-6.4 Inteligencia de la licitación (versión básica)
- US-6.5 Chat con bases (asistente IA)
- US-7.1 Análisis de mercado por rubro (versión básica)
- US-7.2 Histórico de precios
- US-11.1 Notificaciones por email
- US-11.3 Centro de notificaciones in-app
- US-12.1 Editar perfil de empresa
- US-12.2 Editar intereses y radares
- US-12.5 Preferencias de notificaciones

**Tareas backend:**
- [ ] **Sistema de notificaciones:**
  - [ ] Cola en tabla `notificaciones`.
  - [ ] Worker `procesa_notificaciones` que toma pendientes y envía por canal.
  - [ ] Provider de email con Resend (servicios, plantillas básicas con MJML o React Email).
  - [ ] Eventos que generan notificaciones: nueva oportunidad alta relevancia, recordatorio cierre 24h y 6h antes, cambio de estado en pipeline.
- [ ] **Reset de contraseña:**
  - [ ] Endpoint `POST /api/v1/auth/forgot-password`.
  - [ ] Endpoint `POST /api/v1/auth/reset-password`.
  - [ ] Plantilla de email con link único válido 30 minutos.
- [ ] **Chat IA con bases (RAG):**
  - [ ] Endpoint `POST /api/v1/licitaciones/:codigo/chat` (streaming con SSE).
  - [ ] Servicio que recupera chunks relevantes con búsqueda vectorial sobre `documento_chunks`.
  - [ ] Prompt engineering en `services/llm/prompts/chat_bases.py`.
  - [ ] Citas con referencias a `documento_id` + página.
  - [ ] Persistencia en `conversaciones_ia` y `conversacion_mensajes`.
  - [ ] Logging en `llm_usage_log`.
  - [ ] Rate limit: 100 mensajes/día por empresa.
- [ ] **Inteligencia básica de licitación:**
  - [ ] Histórico del organismo (cuántas licitaciones similares, montos típicos).
  - [ ] Top proveedores que han ganado en rubros similares.
- [ ] **Analítica básica:**
  - [ ] Endpoint `GET /api/v1/analytics/mercado` con métricas agregadas filtradas por UNSPSC + fecha + región.
  - [ ] Endpoint `GET /api/v1/analytics/precios` con histórico de adjudicaciones.

**Tareas frontend:**
- [ ] Página de configuración con tabs: Empresa, Intereses, Notificaciones, Cambiar contraseña.
- [ ] Página de "olvidé mi contraseña" + página de reset.
- [ ] Componente de chat IA en el detalle de licitación (drawer lateral o sección dedicada).
- [ ] Streaming de respuestas con SSE.
- [ ] Renderizado de citas con popover que muestra el chunk citado.
- [ ] Página "Pasado" con vista de análisis de mercado y precios históricos.
- [ ] Centro de notificaciones in-app con dropdown desde el header.

**Tareas admin:**
- [ ] Dashboard admin con KPIs y banda de alertas críticas (versión inicial).
- [ ] Vista de costos de IA por cliente.

**Criterio de done:** cliente recibe email cuando aparece oportunidad relevante. Puede preguntar a la IA "¿pide boleta de garantía?" y recibe respuesta con cita al PDF. Puede consultar histórico de precios de servicios similares.

**Entregable demostrable:** **MVP completo lanzable**. Un cliente real puede usar el sistema sin asistencia y derivar valor desde el día uno.

> 🚀 **Hito: lanzamiento de v1 a primeros 3-5 clientes pagos.** Sprints 6-8 ya son evolución sobre clientes reales.

---

## Sprint 6 — Admin completo + WhatsApp + futuro básico (semanas 11-12)

**Objetivo:** cubrir lo que el panel admin debería haber tenido y agregar la vista "Futuro" con plan anual y renovaciones.

**User stories del spec:**
- US-1.2 Suspender o eliminar cuenta
- US-1.4 Monitorear consumo de cuota
- US-3.3 Validación e ingreso del ticket (UI completa)
- US-9.1 Plan anual de compras
- US-9.2 Renovaciones detectadas
- US-11.2 Notificaciones por WhatsApp
- US-12.3 Estado del ticket de ChileCompra
- US-12.4 Cambiar contraseña (versión completa con confirmación)

**Tareas backend:**
- [ ] **Plan anual:**
  - [ ] Backfill de planes anuales desde Datos Abiertos.
  - [ ] Tarea `sync_plan_anual` mensual.
  - [ ] Matching de líneas del plan con licitaciones reales cuando se publican.
  - [ ] Endpoint `GET /api/v1/futuro/plan-anual` filtrado por intereses.
- [ ] **Renovaciones detectadas:**
  - [ ] Cálculo de `fecha_estimada_termino_contrato` en post-sincronización.
  - [ ] Endpoint `GET /api/v1/futuro/renovaciones` con licitaciones adjudicadas vencidas en próximos 6 meses.
  - [ ] Tarea que detecta renovaciones próximas y crea notificaciones tipo `oportunidad_futura`.
- [ ] **WhatsApp:**
  - [ ] Integración con Twilio o 360Dialog para WhatsApp Business API.
  - [ ] Plantillas pre-aprobadas (registro previo con Meta — fuera del código).
  - [ ] Validación de número con OTP en onboarding.
  - [ ] Provider de WhatsApp en sistema de notificaciones.
- [ ] **Endpoints admin completos:**
  - [ ] CRUD completo de cuentas.
  - [ ] Endpoint para impersonation con auditoría.
  - [ ] Endpoint para diagnóstico de tickets (probar ticket, ver consumo).

**Tareas frontend (cliente):**
- [ ] Página "Futuro" con tabs: Plan Anual y Renovaciones.
- [ ] Configuración de WhatsApp con flow de validación OTP.
- [ ] Mejoras en el detalle de licitación: agregar pestaña "Inteligencia" con análisis completo.

**Tareas frontend (admin):**
- [ ] Frontend admin separado (`frontend-admin/`).
- [ ] Dashboard admin completo con todos los widgets.
- [ ] Listado de cuentas con filtros y búsqueda.
- [ ] Detalle de cliente con tabs (General, Ticket, Actividad).
- [ ] Botón "Login como cliente" (impersonation) con banner permanente.
- [ ] Bandeja de solicitudes de ticket pendientes.
- [ ] Vista de tickets activos con monitoreo de cuota.
- [ ] Diagnóstico de ticket individual.
- [ ] Auditoría con filtros.
- [ ] MFA TOTP para cuentas admin.

**Criterio de done:** operación 100% por panel admin (sin SQL directo). Cliente recibe WhatsApp en cierres críticos. Vista "Futuro" muestra renovaciones próximas relevantes.

**Entregable demostrable:** semana operacional completa sin intervención técnica de tu parte. Solo gestionas desde el panel admin.

---

## Sprint 7 — Hardening + analítica avanzada + UX (semanas 13-14)

**Objetivo:** pulir lo que está construido. El MVP funciona; ahora hay que hacerlo robusto, rápido y agradable.

**User stories del spec:**
- US-7.3 Análisis de competidor
- US-9.3 Patrones estacionales
- US-10.3 Archivos en pipeline (subida)

**Tareas:**
- [ ] **Optimización de performance:**
  - [ ] Análisis de queries lentos con `EXPLAIN ANALYZE` y agregar índices faltantes.
  - [ ] Cache con Redis de queries pesados (top licitaciones del día, KPIs del dashboard).
  - [ ] Lazy loading e infinite scroll en listas largas.
- [ ] **Hardening de seguridad:**
  - [ ] Audit de dependencias con `pip-audit` y `npm audit`.
  - [ ] Penetration test básico (al menos OWASP top 10).
  - [ ] Rotación de secrets (JWT_SECRET, ENCRYPTION_KEY) con runbook.
  - [ ] Headers de seguridad completos en producción.
- [ ] **Analítica avanzada:**
  - [ ] Buscador de competidores por RUT/razón social.
  - [ ] Vista de competidor: licitaciones ganadas, organismos, evolución temporal.
  - [ ] Heatmap de patrones estacionales (organismo × mes).
- [ ] **UX refinement:**
  - [ ] Vista Kanban del pipeline con drag-and-drop.
  - [ ] Subida de archivos al pipeline (con R2 + previews).
  - [ ] Atajos de teclado en búsqueda y dashboard.
  - [ ] Estados vacíos ilustrados y útiles.
  - [ ] Loading skeletons en todas las vistas.
- [ ] **Mobile responsive completo.**
- [ ] **Observabilidad:**
  - [ ] Dashboards de Sentry para errores por feature.
  - [ ] Métricas de PostHog para funnels de conversión.
  - [ ] Alertas configuradas para anomalías.
- [ ] **Documentación:**
  - [ ] `docs/runbook.md` con incidentes comunes y cómo resolverlos.
  - [ ] `docs/architecture.md` con ADRs (al menos 5 decisiones importantes documentadas).
  - [ ] Guía de usuario para clientes (puede ser Notion público o landing).

**Criterio de done:** los 5 primeros clientes están usando el sistema sin problemas significativos durante 2 semanas continuas. NPS interno > 7.

**Entregable demostrable:** métricas de uso reales: tasa de adjudicación de los clientes vs su histórico, número de oportunidades detectadas, sesiones por usuario.

---

## Sprint 8 — Crecimiento + automatización + preparar v2 (semanas 15-16)

**Objetivo:** automatizar lo que ya funciona y preparar la base para las features de v2 (generación de propuestas).

**Tareas:**
- [ ] **Automatización de aprovisionamiento:**
  - [ ] Integración con pasarela de pago (Flow, Khipu o Mercado Pago).
  - [ ] Aprovisionamiento semi-automático tras pago confirmado (admin solo aprueba el ticket).
  - [ ] Plantillas de email de bienvenida más pulidas.
- [ ] **Onboarding asistido por IA:**
  - [ ] Asistente que en el wizard sugiere keywords óptimas dado el giro de la empresa.
  - [ ] Análisis automático de licitaciones pasadas del cliente (si las pega como ejemplos) para inferir intereses.
- [ ] **Mejoras al matching:**
  - [ ] Aprendizaje de feedback: si el cliente descarta repetidamente cierto tipo de oportunidad, ajustar el score.
  - [ ] Detección de organismos preferidos del cliente.
- [ ] **Preparación de v2:**
  - [ ] Spike técnico: prototipo de generación de borrador de propuesta técnica.
  - [ ] Modelo de datos extendido (`plantillas_propuesta`, `propuestas_generadas`).
  - [ ] Diseño de UX del flow de generación.
- [ ] **Operación:**
  - [ ] Backups automatizados a R2 con retención.
  - [ ] Verificación semanal automática de restore.
  - [ ] Runbook de incidentes probado en simulacro.
- [ ] **Marketing:**
  - [ ] Landing page (Next.js separado o en el mismo monorepo).
  - [ ] Casos de éxito de los primeros clientes.
  - [ ] Contenido SEO sobre licitaciones.

**Criterio de done:** primer cliente que llega y se aprovisiona prácticamente solo (con tu aprobación al final). v2 con plan de implementación claro.

**Entregable demostrable:** sistema en piloto automático para flujos comunes. Tu tiempo se libera para vender y diseñar v2.

---

## Después del Sprint 8 — V2

A partir del sprint 9 entra v2 según el spec. Las prioridades dependerán del feedback de los primeros 10-15 clientes, pero el orden tentativo es:

**v2.1 — Generación de propuesta técnica (sprints 9-11)**
- Gran diferenciador frente a LicitaLAB.
- Requiere: plantillas, contexto del cliente expandido, agente conversacional especializado, control de versiones del borrador.

**v2.2 — Multi-usuario por empresa (sprints 12-13)**
- Para clientes con equipos. Roles: admin de empresa, editor, lector.
- Refactor del modelo de datos: agregar tabla pivot `usuario_empresa_roles`.

**v2.3 — Integraciones (sprints 14-15)**
- Google Drive, Notion, WhatsApp Business avanzado.
- Webhooks para clientes que quieran integrar a sus propios CRMs.

**v2.4 — API pública (sprint 16+)**
- Para clientes empresariales que quieren consumir desde sus sistemas.

---

## Convenciones del roadmap

### Estados de un sprint
- `📋 Planificado` — fechas confirmadas pero no ha empezado.
- `🚧 En curso` — sprint activo.
- `✅ Completado` — closeout realizado.
- `⏸ Pausado` — empezó pero se detuvo.

### Cómo se modifica este archivo
- Si una US se mueve de un sprint a otro: se actualiza solo aquí, no en `spec.md`.
- Si una US cambia de definición: se actualiza el `spec.md`, este archivo solo referencia el ID.
- Al cerrar un sprint, agregar al final del documento una sección `## Retrospectiva sprint N` con: qué se completó, qué quedó pendiente, lecciones aprendidas.

### Estimación
- Cada sprint asume **2 semanas, full-time, un solo desarrollador** (tú).
- Si trabajas part-time (10-20h/semana), **dobla los plazos**.
- Si suma una segunda persona, no esperes que vaya el doble de rápido — la coordinación cuesta. Espera 1.5x.

### Definition of Ready (antes de empezar un sprint)
- [ ] User stories con criterios de aceptación claros.
- [ ] Modelo de datos definido (sin necesitar migración mayor durante el sprint).
- [ ] Dependencias técnicas resueltas (APIs externas accesibles, cuentas creadas).
- [ ] Mockups o wireframes para features visuales nuevas.

### Definition of Done (al cerrar un sprint)
- [ ] Tests unitarios e integración pasando.
- [ ] Cobertura de tests > 70% en `services/`.
- [ ] Code review ejecutado (incluso con `git diff` fresco al día siguiente).
- [ ] Deploy a staging exitoso.
- [ ] Documentación actualizada (`spec.md`, `data.md`, `CLAUDE.md` si aplica).
- [ ] Demo grabado o sesión de demo en vivo.

---

## Riesgos identificados y mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| API ChileCompra cambia formato sin aviso | Baja | Alto | Tests de integración semanales contra la API real, alertas en errores 4xx/5xx |
| Saturación de cuota por backfill mal ejecutado | Media | Medio | Backfill obligatorio desde Datos Abiertos, no API |
| Costos de IA disparados por uso abusivo | Media | Alto | Rate limit por cliente, alertas de costo, monitoreo en `llm_usage_log` |
| LicitaLAB lanza feature equivalente antes que tú | Alta | Medio | Velocidad de iteración + ángulo diferenciador (chat con bases + futuro) |
| Cliente espera "todo perfecto" desde día 1 | Alta | Medio | Comunicar que es MVP, recoger feedback, lanzar mejoras semanales |
| Scraper de PDFs bloqueado por Mercado Público | Media | Alto | User-agents rotativos, delays entre requests, fallback a parseo desde URLs públicas |
| Dependencia de un solo desarrollador (tú) | Alta | Crítico | Documentación impecable, runbook detallado, considerar segundo dev al sprint 6 |

---

*Este roadmap se revisa al cierre de cada sprint. Última revisión: 2026-05-07.*
