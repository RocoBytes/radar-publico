#!/bin/bash
# Script de inicialización del contenedor Postgres
# Se ejecuta una sola vez en el primer arranque (cuando el volumen está vacío)

set -e

echo "==> Configurando locale es_CL.UTF-8..."
sed -i 's/# es_CL.UTF-8/es_CL.UTF-8/' /etc/locale.gen 2>/dev/null || true
locale-gen es_CL.UTF-8 2>/dev/null || true

echo "==> Postgres inicializado. El schema se carga desde 02-schema.sql"
