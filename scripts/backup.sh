#!/bin/bash
# Script de backup de Postgres
# Regla de oro #28: backups diarios automáticos con prueba de restore mensual
#
# Uso:
#   ./scripts/backup.sh              → backup local en ./backups/
#   ./scripts/backup.sh --upload     → backup local + subir a R2
#
# En producción, este script se ejecuta diariamente vía cron:
#   0 3 * * * /app/scripts/backup.sh --upload >> /var/log/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILENAME="radar-${TIMESTAMP}.sql.gz"
UPLOAD=${1:-""}

# Crear directorio si no existe
mkdir -p "$BACKUP_DIR"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Iniciando backup..."

# Ejecutar pg_dump dentro del contenedor
docker compose exec -T postgres \
  pg_dump -U radar radar \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

SIZE=$(du -sh "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup creado: ${BACKUP_DIR}/${FILENAME} (${SIZE})"

# Subir a R2 si se solicitó
if [ "$UPLOAD" = "--upload" ]; then
  if [ -z "${R2_BUCKET:-}" ] || [ -z "${R2_ACCESS_KEY:-}" ]; then
    echo "ERROR: R2_BUCKET y R2_ACCESS_KEY deben estar configurados para el upload"
    exit 1
  fi
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Subiendo a R2..."
  # aws s3 cp "${BACKUP_DIR}/${FILENAME}" "s3://${R2_BUCKET}/backups/${FILENAME}" \
  #   --endpoint-url "${R2_ENDPOINT}"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Upload completado (implementar en Sprint 7)"
fi

# Limpiar backups locales con más de 7 días
find "$BACKUP_DIR" -name "radar-*.sql.gz" -mtime +7 -delete
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup completado."
