# Decisiones Arquitectónicas — Radar Público

Registro de ADRs (Architecture Decision Records) del proyecto.
Formato: Contexto → Decisión → Consecuencias → Alternativas descartadas.

---

## ADR-001: Autenticación propia con FastAPI

**Estado:** Aceptado  
**Fecha:** 2026-05-09  
**Sprint:** 1

### Contexto

Radar Público requiere autenticación para dos roles: `admin` (operador interno) y `proveedor` (cliente empresa). El modelo de negocio es **invitación-only** — no hay auto-registro. Las cuentas las aprovisiona el admin tras recibir pago externo.

Restricciones relevantes:
- Sin self-service signup
- MFA obligatorio solo para admin (TOTP), no para proveedores en v1
- Stack: FastAPI + Postgres + Redis — ya presentes en el proyecto
- Todas las dependencias de auth (`python-jose`, `passlib`, `redis`) ya estaban en `requirements.txt`

### Decisión

Implementar autenticación propia en FastAPI con:
- **bcrypt cost 12** para passwords (passlib)
- **JWT HS256** de 15 min para access tokens
- **Refresh tokens rotativos** de 7 días, hasheados SHA-256 en `refresh_tokens`
- **Password reset tokens** de 30 min, single-use, en `password_reset_tokens`
- **Rate limiting fixed window** con Redis INCR+EXPIRE (5 req/15 min en login)
- **Lockout a nivel BD** tras 5 intentos fallidos (`locked_until = now() + 30 min`)
- **Auditoría** en `eventos_auditoria` — sin PII, solo user_id

### Consecuencias

**Positivas:**
- Sin dependencia de servicio externo (no hay SPOF externo ni costo adicional)
- Control total sobre el flujo de onboarding y reset
- Compatible con el modelo invitación-only desde el día 1
- Fácil de auditar y adaptar a requerimientos regulatorios chilenos (Ley 19.628)

**Negativas:**
- Mantenemos código de auth propio — mayor responsabilidad de seguridad
- MFA TOTP para admin requiere implementación separada (Sprint 6)
- No hay integración con IdP externo (SAML, OIDC) si se necesita en futuro

### Alternativas descartadas

| Alternativa | Motivo de descarte |
|-------------|-------------------|
| **Clerk** | Diseñado para self-service con planes gratuitos; sobre-ingeniería para modelo invitación-only |
| **Auth.js (NextAuth)** | Orientado a frontend Next.js; no cubre el backend FastAPI de forma nativa |
| **Supabase Auth** | Agrega dependencia de plataforma; complejidad innecesaria dado el stack existente |

---

## ADR-002: Rate limiting fixed window vs sliding window

**Estado:** Aceptado  
**Fecha:** 2026-05-09  
**Sprint:** 1

### Decisión

Fixed window con Redis `INCR` + `EXPIRE` para el endpoint `/auth/login`.

### Justificación

La regla de oro #6 pide "5 intentos / 15 min por IP". El edge case del fixed window (hasta 2× el límite entre ventanas adyacentes) es aceptable porque la segunda línea de defensa — el lockout a nivel BD tras 5 fallos (`locked_until`) — cubre el caso límite. La defensa es en capas, no monolítica en Redis.

Sliding window con `ZSET` agrega precisión que no necesitamos y ~3× el costo de Redis por operación.
