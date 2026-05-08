# Radar Público — Setup Docker

Este directorio contiene todo lo necesario para correr Radar Público localmente con Docker, y para desplegarlo en un Droplet de Digital Ocean.

## Estructura

```
.
├── docker-compose.yml          # Stack completo (desarrollo)
├── docker-compose.prod.yml     # Override para producción
├── .env.example                # Plantilla de variables de entorno
├── Makefile                    # Comandos comunes
├── schema.sql                  # Schema inicial de Postgres (copia de outputs/schema.sql)
├── backend/
│   ├── Dockerfile              # Multi-stage para FastAPI
│   └── requirements.txt        # Dependencias Python
├── frontend/
│   └── Dockerfile              # Multi-stage para Next.js
├── nginx/
│   └── Caddyfile               # Reverse proxy con TLS automático (producción)
└── scripts/
    └── init-db.sh              # Setup inicial de Postgres
```

## Servicios incluidos

| Servicio | Imagen | Puerto local | Para qué sirve |
|---|---|---|---|
| postgres | pgvector/pgvector:pg16 | 5432 | Base de datos principal |
| redis | redis:7-alpine | 6379 | Cache + broker de Celery |
| api | (custom) | 8000 | Backend FastAPI |
| worker | (custom) | – | Celery worker (sync, IA, notif) |
| beat | (custom) | – | Celery beat scheduler (cron) |
| flower | mher/flower | 5555 | UI para monitorear Celery (solo dev) |
| web | (custom) | 3000 | Frontend Next.js |
| mailhog | mailhog/mailhog | 8025 | SMTP local para capturar emails (solo dev) |
| proxy | caddy:2 (solo prod) | 80, 443 | Reverse proxy + TLS |

## Setup inicial (primera vez)

### 1. Pre-requisitos

- Docker Desktop (Mac/Windows) o Docker Engine + Compose plugin (Linux).
- `make` (en Mac viene preinstalado; en Linux: `sudo apt install make`; en Windows: usa WSL2).
- Git.

### 2. Clonar y configurar

```bash
git clone <repo> radar-publico
cd radar-publico
cp .env.example .env
```

Edita `.env` y completa las variables. Las **mínimas obligatorias** para arrancar:

```bash
POSTGRES_PASSWORD=<algo_seguro>
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32 | head -c 32)
ANTHROPIC_API_KEY=sk-ant-...
```

Las demás (Voyage, Resend, R2, Sentry) puedes dejarlas vacías al inicio; los features que dependen de ellas fallarán graciosamente con error claro.

### 3. Levantar el stack

```bash
make up
```

Verás los servicios arrancar. Cuando termine:

- **Frontend:** http://localhost:3000
- **API docs (Swagger):** http://localhost:8000/docs
- **Flower (monitor de jobs):** http://localhost:5555
- **MailHog (emails capturados):** http://localhost:8025

### 4. Inicializar la base de datos

El schema se carga automáticamente en el primer arranque del contenedor de Postgres (porque se monta `schema.sql` en `/docker-entrypoint-initdb.d`). Si quieres correr migraciones de Alembic adicionales:

```bash
make migrate
```

Para cargar datos seed (catálogos UNSPSC, regiones, comunas):

```bash
make seed
```

## Comandos del día a día

```bash
make up              # Levantar todo
make down            # Detener todo (data persiste)
make logs-api        # Ver logs del backend
make shell-api       # Abrir bash en el contenedor del backend
make shell-db        # Abrir psql en la BD
make ps              # Ver estado de los servicios
make restart         # Reiniciar todos los servicios
```

## Desarrollo

### Backend

El código está montado como volumen (`./backend:/app`), así que **los cambios se reflejan al instante** gracias a `--reload` de uvicorn. No tienes que rebuildear nada para iterar.

Para entrar al shell del backend (correr scripts, debug, etc.):

```bash
make shell-api
# Dentro del contenedor:
python -m app.scripts.test_api_chilecompra
```

### Frontend

Igual: el código está montado y Next.js hace hot-reload automático.

### Ver la base de datos

```bash
make shell-db
# Dentro de psql:
\dt              # listar tablas
\d licitaciones  # describir tabla
SELECT count(*) FROM licitaciones;
```

O conectar tu cliente favorito (DBeaver, TablePlus, pgAdmin) a:
- Host: `localhost`
- Port: `5432`
- User: `radar`
- Pass: el de tu .env
- DB: `radar`

### Reset total

Si querés borrar todo y empezar de cero:

```bash
make reset
```

Esto **elimina los volúmenes** (Postgres, Redis y el storage local). Te pedirá confirmación con 5 segundos de gracia.

## Despliegue en Digital Ocean

### Opción A: Droplet único (recomendado para MVP)

Para los primeros 50-100 clientes, un solo Droplet maneja todo el stack tranquilamente.

#### 1. Crear el Droplet

- Distribución: **Ubuntu 24.04 LTS**
- Plan: **Basic Premium AMD** con **4 GB RAM / 2 vCPU / 80 GB SSD** (~24 USD/mes) como mínimo.
  - Justificación: Postgres + workers + IA local consume RAM. Empezar con 2 GB es ajustado.
- Región: **NYC3** o **SFO3** (más cercanas a Chile con buena latencia).
- Autenticación: **SSH key** (no password).
- Habilitar **monitoring** y **backups semanales** desde el panel.

#### 2. Configurar el Droplet

SSH al Droplet y corre:

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Instalar make y git
apt install -y make git ufw

# Configurar firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Crear usuario no-root para correr la app
adduser --disabled-password --gecos "" radar
usermod -aG docker radar
```

#### 3. Configurar DNS

En el panel de tu registrador de dominios o en Digital Ocean DNS, crea registros A:

```
radarpublico.cl       → IP del Droplet
api.radarpublico.cl   → IP del Droplet
```

Espera 5-15 minutos a que propague.

#### 4. Desplegar el código

Como usuario `radar`:

```bash
su - radar
git clone <tu-repo> radar-publico
cd radar-publico

# Configurar .env de producción
cp .env.example .env
nano .env
# Edita con valores de PRODUCCIÓN:
# - POSTGRES_PASSWORD: nuevo, fuerte
# - JWT_SECRET, ENCRYPTION_KEY: nuevos, generados con openssl
# - DOMAIN_APP, DOMAIN_API: tus dominios reales
# - NEXT_PUBLIC_API_URL: https://api.radarpublico.cl
# - NEXT_PUBLIC_APP_URL: https://radarpublico.cl
# - CORS_ORIGINS: https://radarpublico.cl

# Levantar stack de producción
make prod-up

# Caddy obtendrá certificados Let's Encrypt automáticamente al primer request
# Tarda 30-60 segundos la primera vez

# Verificar logs
make prod-logs
```

#### 5. Validar despliegue

- Visita https://radarpublico.cl → debería cargar el frontend.
- Visita https://api.radarpublico.cl/health → debería responder `{"status": "ok"}`.
- Visita https://api.radarpublico.cl/docs → Swagger.

#### 6. Operación

```bash
# Ver logs
make prod-logs

# Backup de Postgres
make backup

# Despliegue de nueva versión (CI/CD manual)
make prod-deploy

# Detener todo (mantenimiento)
make prod-down
```

### Opción B: Postgres administrado + Droplet para apps

Cuando crezcas, conviene mover Postgres a **Digital Ocean Managed Database** (50 USD/mes, 1 GB RAM, backups automáticos diarios).

Cambios:
1. Crear el cluster Managed Database desde el panel.
2. Eliminar el servicio `postgres` del `docker-compose.prod.yml` (o agregarle `profiles: ["never"]`).
3. Actualizar `DATABASE_URL` y `DATABASE_URL_SYNC` en el `.env` con las credenciales del cluster.
4. Importar el schema: `psql <connection-string> < schema.sql`.

### Backups y monitoreo

**Backups automáticos:**

Crea un cron en el Droplet:

```bash
# Como root
crontab -e
# Agregar:
0 3 * * * cd /home/radar/radar-publico && /usr/bin/make backup >> /var/log/radar-backup.log 2>&1
```

Y configura sincronización a R2 o S3 con `aws s3 cp` (te dejo esto como ejercicio: 5 líneas de bash más).

**Monitoreo básico:**

- Activa Digital Ocean Monitoring (gratis con el Droplet).
- Configura Sentry (DSN en `.env`) para errores de aplicación.
- Si quieres logs centralizados, considera agregar `logspout` o `vector.dev` que envíen a Better Stack o Grafana Cloud.

## Troubleshooting

### "Cannot connect to the Docker daemon"
Asegurate de que Docker Desktop esté corriendo (Mac/Windows) o el daemon esté activo (`sudo systemctl start docker` en Linux).

### "Port 5432 is already allocated"
Tienes otra instancia de Postgres corriendo. Detén la otra o cambia el puerto en `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"
```

### Los cambios al schema.sql no se aplican
El schema solo se carga en el **primer arranque** del contenedor (cuando el volumen está vacío). Para forzar la recarga:

```bash
make reset    # Borra el volumen
make up       # Recarga schema
```

### Backend no levanta: "ModuleNotFoundError"
Después de agregar dependencias a `requirements.txt`, hay que rebuildear:

```bash
make build-api
make up
```

### Worker no procesa tareas
Verifica con Flower (http://localhost:5555) que el worker esté conectado al broker. Si no, revisa los logs:

```bash
make logs-worker
```

## Performance tuning (cuando ya tengas tráfico)

- **Postgres**: aumenta `shared_buffers` y `effective_cache_size` editando un `postgres.conf` y montándolo. Para 4 GB RAM total, `shared_buffers=1GB` es razonable.
- **Workers Celery**: aumenta `--concurrency` si la CPU está disponible. Para tareas IO-bound (HTTP, IA), usa `--pool=gevent` con concurrencia más alta.
- **Next.js**: el target `production` ya usa `output: standalone`, que reduce drásticamente el tamaño y mejora el cold start.
- **CDN**: poné Cloudflare delante de tu dominio para cache estático y protección DDoS.

## Migrar a infraestructura más grande

Cuando un solo Droplet no alcance:

1. **App Platform de DO** para correr containers managed (más caro pero menos ops).
2. **Kubernetes (DOKS)** si tienes equipo dedicado.
3. **Workers en Droplets separados** del API (escala independiente).
4. **Réplica de lectura de Postgres** para queries pesadas de analytics.

Pero para los primeros 1-2 años, un Droplet de 4-8 GB con Postgres administrado te alcanza tranquilo.
