# Guía de Deploy — Radar Público en VPS

> Guía completa para levantar el stack de producción en un VPS (Hostinger u otro proveedor).
> Dominio de referencia: `radarpublico.emgus.cl` · IP: `187.77.230.54`

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Verificar DNS antes de empezar](#2-verificar-dns-antes-de-empezar)
3. [Conectarse al VPS por SSH](#3-conectarse-al-vps-por-ssh)
4. [Instalar Docker y Docker Compose](#4-instalar-docker-y-docker-compose)
5. [Configurar el firewall](#5-configurar-el-firewall)
6. [Clonar el repositorio](#6-clonar-el-repositorio)
7. [Crear el archivo `.env` de producción](#7-crear-el-archivo-env-de-producción)
8. [Primer deploy](#8-primer-deploy)
9. [Seed inicial (solo la primera vez)](#9-seed-inicial-solo-la-primera-vez)
10. [Verificar que todo funciona](#10-verificar-que-todo-funciona)
11. [Deploys futuros](#11-deploys-futuros)
12. [Operaciones comunes](#12-operaciones-comunes)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Requisitos previos

Antes de empezar, asegurate de tener:

- **Acceso SSH** al VPS (usuario `root` o con `sudo`, IP del servidor, contraseña o clave SSH)
- **Registro DNS tipo A** apuntando el dominio a la IP del VPS ya configurado en tu proveedor de dominios
- **El código fuente** en un repositorio Git accesible desde el VPS (GitHub, GitLab, etc.)
- **Las API keys** que el proyecto necesita (Anthropic, Voyage AI, Resend, Cloudflare R2, etc.)

El VPS mínimo recomendado es **4 GB de RAM** por el worker de Playwright (scraper de PDFs, ~1.5 GB de imagen).

---

## 2. Verificar DNS antes de empezar

**Este paso es crítico.** Caddy (el reverse proxy) obtiene el certificado TLS de Let's Encrypt automáticamente al primer request, pero para eso el dominio ya tiene que apuntar a la IP del VPS. Si el DNS no está propagado, el certificado fallará.

Verificá desde tu computadora local:

```bash
# Debe retornar la IP de tu VPS (ej: 187.77.230.54)
nslookup radarpublico.emgus.cl

# Alternativa con dig
dig radarpublico.emgus.cl A +short
```

Si no retorna la IP correcta, esperá a que el DNS propague (puede tardar entre 5 minutos y 48 horas dependiendo del TTL configurado en tu proveedor).

---

## 3. Conectarse al VPS por SSH

```bash
ssh root@187.77.230.54
```

Si usás clave SSH en vez de contraseña:

```bash
ssh -i ~/.ssh/tu_clave_privada root@187.77.230.54
```

Una vez dentro, confirmá el sistema operativo:

```bash
lsb_release -a
# Debe decir Ubuntu 22.04 o similar
```

---

## 4. Instalar Docker y Docker Compose

Docker Compose v2 viene incluido con Docker Desktop y con el script oficial. No instales el paquete `docker-compose` legacy (v1).

```bash
# Actualizar el sistema
apt update && apt upgrade -y

# Instalar dependencias previas
apt install -y curl git

# Instalar Docker usando el script oficial de Docker Inc.
curl -fsSL https://get.docker.com | sh

# Verificar instalación
docker --version
# Docker version 27.x.x, build ...

docker compose version
# Docker Compose version v2.x.x
```

> Si usás un usuario que no es root, agregalo al grupo docker:
> ```bash
> usermod -aG docker $USER
> newgrp docker
> ```

---

## 5. Configurar el firewall

Solo se exponen los puertos 80 (HTTP) y 443 (HTTPS). Caddy se encarga de redirigir HTTP → HTTPS automáticamente. **Nunca expongas el puerto 5432 (Postgres) ni el 6379 (Redis) al exterior.**

```bash
ufw allow 22     # SSH — NO lo olvides o te quedás sin acceso
ufw allow 80     # HTTP (Caddy lo redirige a HTTPS)
ufw allow 443    # HTTPS

ufw enable

# Confirmar estado
ufw status verbose
```

Salida esperada:

```
Status: active
To                         Action      From
--                         ------      ----
22                         ALLOW IN    Anywhere
80                         ALLOW IN    Anywhere
443                        ALLOW IN    Anywhere
```

---

## 6. Clonar el repositorio

```bash
cd /opt
git clone https://github.com/TU_USUARIO/radar-publico.git
cd radar-publico
```

### Si el repositorio es privado

Generá una clave SSH de deploy en el VPS y agregala a GitHub como Deploy Key (solo lectura):

```bash
# En el VPS: generar clave
ssh-keygen -t ed25519 -C "deploy@radarpublico" -f ~/.ssh/deploy_key -N ""

# Mostrar la clave pública para copiarla en GitHub
cat ~/.ssh/deploy_key.pub

# Configurar SSH para usar esa clave con GitHub
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  StrictHostKeyChecking no
EOF
```

Luego en GitHub: **Settings → Deploy keys → Add deploy key** → pegá la clave pública, solo lectura, sin permisos de escritura.

Después cloná con SSH:

```bash
git clone git@github.com:TU_USUARIO/radar-publico.git
cd radar-publico
```

---

## 7. Crear el archivo `.env` de producción

```bash
cp .env.example .env
nano .env
```

### Generar los secrets de seguridad

Antes de editar el `.env`, generá los valores de `JWT_SECRET` y `ENCRYPTION_KEY`:

```bash
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(openssl rand -hex 32)"
```

Copiá esos valores y pegálos en el `.env`. **Nunca los compartas ni los commiteés al repositorio.**

### Contenido completo del `.env`

```bash
# ============================================================
# BASE DE DATOS
# ============================================================
POSTGRES_PASSWORD=cambia_esto_por_un_password_muy_fuerte

# ============================================================
# SEGURIDAD — generados con: openssl rand -hex 32
# ============================================================
JWT_SECRET=PEGAR_OUTPUT_DE_OPENSSL
ENCRYPTION_KEY=PEGAR_OUTPUT_DE_OPENSSL

# ============================================================
# DOMINIO Y CORS
# ============================================================
DOMAIN_APP=radarpublico.emgus.cl
CORS_ORIGINS=https://radarpublico.emgus.cl
NEXT_PUBLIC_API_URL=https://radarpublico.emgus.cl
NEXT_PUBLIC_APP_URL=https://radarpublico.emgus.cl

# ============================================================
# CUENTA ADMIN INICIAL
# ============================================================
ADMIN_EMAIL=admin@tuempresa.cl
ADMIN_PASSWORD=password_admin_muy_fuerte

# ============================================================
# IA (Anthropic + Voyage AI)
# ============================================================
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
LLM_PROVIDER=anthropic

# ============================================================
# EMAIL TRANSACCIONAL (Resend)
# ============================================================
RESEND_API_KEY=re_...

# ============================================================
# ALMACENAMIENTO (Cloudflare R2)
# ============================================================
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET=radar-publico-prod
R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com

# ============================================================
# OBSERVABILIDAD (Sentry) — opcional pero recomendado
# ============================================================
SENTRY_DSN=https://...@o0000.ingest.sentry.io/0000000

# ============================================================
# WHATSAPP — opcional, dejá vacío si no lo usás aún
# ============================================================
WHATSAPP_PROVIDER_API_KEY=
```

> **Variables no opcionales:** `POSTGRES_PASSWORD`, `JWT_SECRET`, `ENCRYPTION_KEY`, `DOMAIN_APP`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
>
> Sin estas el stack no arranca o lo hace en modo inseguro.

---

## 8. Primer deploy

Un solo comando hace todo: build de imágenes, migraciones de BD y levanta los servicios.

```bash
make prod-deploy
```

Lo que hace internamente:

```
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker image prune -f        # elimina imágenes huérfanas (dangling) del build anterior
docker builder prune -f      # limpia el build cache de Docker BuildKit
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**El primer build toma entre 10 y 20 minutos** porque descarga las imágenes base y compila las dependencias (especialmente la imagen de Playwright con Chromium, ~1.5 GB). Los builds siguientes son mucho más rápidos por el caché de Docker.

### Verificar que los contenedores levantaron

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Salida esperada — todos en estado `Up` o `healthy`:

```
NAME                   STATUS
radar_postgres         Up (healthy)
radar_redis            Up (healthy)
radar_api              Up (healthy)
radar_worker           Up
radar_worker_scraper   Up
radar_beat             Up
radar_web              Up
radar_proxy            Up
```

---

## 9. Seed inicial (solo la primera vez)

Cargá los datos de referencia y creá la cuenta admin:

```bash
# Admin + catálogos geográficos (regiones, comunas) + UNSPSC
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python -m app.scripts.seed --admin --catalogos
```

El comando imprime las credenciales del admin si las generó automáticamente. **Guardalas en un lugar seguro.**

> **Importante:** el flag `--dev` crea un usuario de prueba con credenciales hardcodeadas. **Nunca lo uses en producción.**

---

## 10. Verificar que todo funciona

```bash
# Health check del API (debe retornar {"status":"ok",...})
curl https://radarpublico.emgus.cl/health

# Ver logs de todos los servicios en tiempo real
make prod-logs

# Ver logs de un servicio específico
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f proxy
```

Abrí `https://radarpublico.emgus.cl` en el navegador. Caddy ya tiene que haber obtenido el certificado TLS — el candado verde debe aparecer.

---

## 11. Deploys futuros

Cada vez que quieras desplegar nueva versión del código:

```bash
# Desde el VPS, dentro de /opt/radar-publico
make prod-deploy
# Este comando incluye limpieza automática del build cache de Docker
# para evitar la acumulación de imágenes y capas huérfanas en disco.
```

Esto hace `git pull` + rebuild + migraciones + restart. Si no hay cambios en el código (solo en la config), podés hacer solo:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 12. Operaciones comunes

### Ver estado de los servicios

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Acceder a la base de datos

```bash
# Nota: el servicio se llama "postgres", no "db"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
  psql -U radar -d radar
```

### Ejecutar una migración manualmente

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \
  alembic upgrade head
```

### Ver migraciones aplicadas

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \
  alembic current
```

### Reiniciar un servicio específico

```bash
# Reiniciar solo el backend API
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api

# Reiniciar solo el frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart web
```

### Backup manual de la base de datos

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
  pg_dump -U radar radar > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Detener todo el stack

```bash
make prod-down
```

### Detener y borrar volúmenes (reset total — CUIDADO, borra datos)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
```

---

## 13. Troubleshooting

### El certificado TLS no aparece / la página no carga por HTTPS

Verificá que:
1. El DNS ya propagó: `nslookup radarpublico.emgus.cl` devuelve la IP del VPS.
2. Los puertos 80 y 443 están abiertos: `ufw status`.
3. Caddy puede hacer el challenge de Let's Encrypt (necesita puerto 80 libre al inicio).

Ver logs de Caddy:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs proxy
```

### El API retorna 404 en endpoints de empresa

Significa que el usuario logueado no tiene un registro asociado en la tabla `empresas`. Esto pasa cuando se crea un usuario directamente en la BD sin pasar por el panel admin. La solución correcta es crear cuentas siempre a través del endpoint `POST /api/admin/cuentas` que crea el usuario + la empresa en una transacción atómica.

### Error 422 al hacer login

Pydantic valida el campo `email` con `EmailStr`. Dominios con TLDs no estándar como `.local` son rechazados. Usá siempre emails con TLDs válidos (`.cl`, `.com`, `.org`, etc.).

### El contenedor `api` no levanta — error de conexión a Postgres

Esperá a que Postgres esté `healthy` antes de inspeccionar. El `healthcheck` tarda hasta 50 segundos en declararlo listo. Si sigue fallando:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs postgres
```

### Comandos de base de datos ejecutados fuera del contenedor

El nombre correcto del servicio de base de datos en este proyecto es **`postgres`**, no `db`. Siempre:

```bash
# CORRECTO
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U radar -d radar

# INCORRECTO — este error es común
docker compose exec db psql ...
```

### El worker scraper consume demasiada RAM

La imagen de Playwright pesa ~1.5 GB y cada instancia de Chromium consume ~300 MB. Si el VPS tiene menos de 4 GB libres, podés reducir la concurrencia editando `docker-compose.prod.yml`:

```yaml
worker_scraper:
  deploy:
    resources:
      limits:
        memory: 1g
        cpus: '0.5'
```

Y en el `command` del servicio, reducir a `--concurrency=1`.

### Ver todos los logs de una vez

```bash
make prod-logs
# o equivalente:
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

---

*Última actualización: 2026-06-03*
