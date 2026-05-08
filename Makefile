# Radar Público — Makefile con comandos comunes
# Uso: make <comando>

.PHONY: help up down restart logs ps build clean shell-api shell-db migrate test deploy

# === Default ===
help:
	@echo "Radar Público — comandos disponibles:"
	@echo ""
	@echo "  Desarrollo:"
	@echo "    up              Levanta todo el stack (background)"
	@echo "    down            Detiene todo (data persiste)"
	@echo "    reset           Detiene y BORRA todos los volúmenes"
	@echo "    restart         Reinicia todo"
	@echo "    logs            Sigue logs de todos los servicios"
	@echo "    logs-api        Sigue logs solo del backend"
	@echo "    logs-worker     Sigue logs solo del worker"
	@echo "    ps              Estado de los servicios"
	@echo ""
	@echo "  Build:"
	@echo "    build           Reconstruye todas las imágenes"
	@echo "    build-api       Reconstruye solo el backend"
	@echo "    build-web       Reconstruye solo el frontend"
	@echo ""
	@echo "  Acceso:"
	@echo "    shell-api       Bash dentro del contenedor api"
	@echo "    shell-db        psql en la base de datos"
	@echo "    shell-redis     redis-cli"
	@echo ""
	@echo "  Base de datos:"
	@echo "    migrate         Ejecuta migraciones de Alembic"
	@echo "    seed            Carga datos de prueba"
	@echo "    backup          Backup de Postgres"
	@echo ""
	@echo "  Producción:"
	@echo "    prod-up         Levanta stack de producción"
	@echo "    prod-down       Detiene stack de producción"
	@echo "    prod-deploy     Pull + rebuild + restart en remoto"

# === Desarrollo ===
up:
	docker compose up -d
	@echo "✓ Stack levantado"
	@echo "  → Frontend:  http://localhost:3000"
	@echo "  → API:       http://localhost:8000"
	@echo "  → API docs:  http://localhost:8000/docs"
	@echo "  → Flower:    http://localhost:5555"
	@echo "  → MailHog:   http://localhost:8025"
	@echo "  → Postgres:  localhost:5432"

down:
	docker compose down

reset:
	@echo "⚠ Esto BORRA todos los datos. Cancela en 5 segundos si no es lo que quieres..."
	@sleep 5
	docker compose down -v
	@echo "✓ Volúmenes eliminados"

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

ps:
	docker compose ps

# === Build ===
build:
	docker compose build

build-api:
	docker compose build api worker beat

build-web:
	docker compose build web

# === Acceso ===
shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U radar -d radar

shell-redis:
	docker compose exec redis redis-cli

# === Base de datos ===
migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	@read -p "Nombre de la migración: " name; \
	docker compose exec api alembic revision --autogenerate -m "$$name"

seed:
	docker compose exec api python -m app.scripts.seed

backup:
	@mkdir -p backups
	@docker compose exec -T postgres pg_dump -U radar radar | gzip > backups/radar-$(shell date +%Y%m%d-%H%M%S).sql.gz
	@echo "✓ Backup creado en backups/"

# === Producción ===
prod-up:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-build:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-logs:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

prod-deploy:
	@echo "Desplegando a producción..."
	git pull origin main
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api alembic upgrade head
	@echo "✓ Despliegue completado"

# === Limpieza ===
clean:
	docker compose down
	docker system prune -f
