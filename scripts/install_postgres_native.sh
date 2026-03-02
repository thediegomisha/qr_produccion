#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este script requiere privilegios de administrador."
  echo "Uso: sudo bash scripts/install_postgres_native.sh"
  exit 1
fi

echo "[1/6] Instalando PostgreSQL nativo..."
apt-get update
apt-get install -y postgresql postgresql-contrib

echo "[2/6] Habilitando servicio PostgreSQL..."
systemctl enable postgresql
systemctl restart postgresql

PG_PORT="${PG_PORT:-}"
if [[ -z "${PG_PORT}" ]]; then
  while read -r _ver _cluster port status _owner _rest; do
    if [[ "${status}" == "online" ]]; then
      PG_PORT="${port}"
      break
    fi
  done < <(pg_lsclusters --no-header)
fi
PG_PORT="${PG_PORT:-5432}"
echo "Puerto PostgreSQL detectado: ${PG_PORT}"

echo "[3/6] Verificando conflicto de puerto ${PG_PORT} con Docker..."
if command -v docker >/dev/null 2>&1; then
  if docker ps --format '{{.Names}} {{.Ports}}' | grep -q "0.0.0.0:${PG_PORT}->5432/tcp"; then
    echo "Detectado contenedor Docker ocupando puerto ${PG_PORT}."
    echo "Detenga ese contenedor o cambie el puerto de PostgreSQL host antes de continuar."
    exit 1
  fi
fi

echo "[4/6] Creando usuario y base para el proyecto..."
su - postgres -c "psql -p ${PG_PORT} -v ON_ERROR_STOP=1" < "/home/theathoq/proyectos/qr_produccion/scripts/setup_qr_db.sql"

echo "[5/6] Probando conexion local..."
PGPASSWORD='Nomeacuerd0' psql -h 127.0.0.1 -p "${PG_PORT}" -U qr_user -d qr_produccion -c 'SELECT 1;'

echo "[6/6] Listo. PostgreSQL nativo instalado y configurado."
echo "Recuerde actualizar DB_PORT=${PG_PORT} en .env y backend/.env"
