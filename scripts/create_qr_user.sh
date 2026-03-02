#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/setup_qr_db.sql"
DB_USER="qr_user"
DB_PASS="Nomeacuerd0"
DB_NAME="qr_produccion"

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "No existe el archivo SQL: ${SQL_FILE}"
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql no esta instalado. Instale PostgreSQL primero."
  exit 1
fi

PG_PORT="${PG_PORT:-}"
if [[ -z "${PG_PORT}" ]] && command -v pg_lsclusters >/dev/null 2>&1; then
  while read -r _ver _cluster port status _owner _rest; do
    if [[ "${status}" == "online" ]]; then
      PG_PORT="${port}"
      break
    fi
  done < <(pg_lsclusters --no-header)
fi
PG_PORT="${PG_PORT:-5432}"

echo "Usando cluster PostgreSQL en puerto ${PG_PORT}"
echo "Creando/actualizando usuario ${DB_USER} y base ${DB_NAME}..."

if [[ "${EUID}" -eq 0 ]]; then
  su - postgres -c "psql -p ${PG_PORT} -v ON_ERROR_STOP=1" < "${SQL_FILE}"
else
  sudo -u postgres psql -p "${PG_PORT}" -v ON_ERROR_STOP=1 < "${SQL_FILE}"
fi

echo "Probando conexion..."
PGPASSWORD="${DB_PASS}" psql -h 127.0.0.1 -p "${PG_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT current_database(), current_user;"

echo "Listo. Si todo salio OK, use estos valores en .env y backend/.env"
echo "DB_USER=${DB_USER}"
echo "DB_PASS=${DB_PASS}"
echo "DB_NAME=${DB_NAME}"
echo "DB_PORT=${PG_PORT}"
