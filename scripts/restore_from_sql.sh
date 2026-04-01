#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE=""
CLEAN_RESTORE=0
PROMPT_PASS=0
NO_PASS=0

OVERRIDE_DB_USER_SET=0
OVERRIDE_DB_PASS_SET=0
OVERRIDE_DB_HOST_SET=0
OVERRIDE_DB_PORT_SET=0
OVERRIDE_DB_NAME_SET=0

OVERRIDE_DB_USER=""
OVERRIDE_DB_PASS=""
OVERRIDE_DB_HOST=""
OVERRIDE_DB_PORT=""
OVERRIDE_DB_NAME=""

if [[ -f "${ROOT_DIR}/backend/.env" ]]; then
  ENV_FILE="${ROOT_DIR}/backend/.env"
elif [[ -f "${ROOT_DIR}/.env" ]]; then
  ENV_FILE="${ROOT_DIR}/.env"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)
      CLEAN_RESTORE=1
      shift
      ;;
    --prompt-pass)
      PROMPT_PASS=1
      shift
      ;;
    --no-pass)
      NO_PASS=1
      shift
      ;;
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    --user)
      OVERRIDE_DB_USER_SET=1
      OVERRIDE_DB_USER="$2"
      shift 2
      ;;
    --pass)
      OVERRIDE_DB_PASS_SET=1
      OVERRIDE_DB_PASS="$2"
      shift 2
      ;;
    --host)
      OVERRIDE_DB_HOST_SET=1
      OVERRIDE_DB_HOST="$2"
      shift 2
      ;;
    --port)
      OVERRIDE_DB_PORT_SET=1
      OVERRIDE_DB_PORT="$2"
      shift 2
      ;;
    --name)
      OVERRIDE_DB_NAME_SET=1
      OVERRIDE_DB_NAME="$2"
      shift 2
      ;;
    -h|--help)
      echo "Uso: bash scripts/restore_from_sql.sh [--clean] [--prompt-pass] [--no-pass] [--env /ruta/.env] \\
  [--host HOST] [--port PORT] [--user USER] [--pass PASS] [--name DB] /ruta/al/dump.sql"
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ "${DB_USER+x}" ]]; then
  OVERRIDE_DB_USER_SET=1
  OVERRIDE_DB_USER="${DB_USER}"
fi
if [[ "${DB_PASS+x}" ]]; then
  OVERRIDE_DB_PASS_SET=1
  OVERRIDE_DB_PASS="${DB_PASS}"
fi
if [[ "${DB_HOST+x}" ]]; then
  OVERRIDE_DB_HOST_SET=1
  OVERRIDE_DB_HOST="${DB_HOST}"
fi
if [[ "${DB_PORT+x}" ]]; then
  OVERRIDE_DB_PORT_SET=1
  OVERRIDE_DB_PORT="${DB_PORT}"
fi
if [[ "${DB_NAME+x}" ]]; then
  OVERRIDE_DB_NAME_SET=1
  OVERRIDE_DB_NAME="${DB_NAME}"
fi

if [[ -n "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
  else
    echo "No existe el archivo: ${ENV_FILE}"
    exit 1
  fi
fi

DB_USER="${DB_USER:-qr_user}"
DB_PASS="${DB_PASS:-}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-qr_produccion}"

if [[ "${OVERRIDE_DB_USER_SET}" -eq 1 ]]; then
  DB_USER="${OVERRIDE_DB_USER}"
fi
if [[ "${OVERRIDE_DB_PASS_SET}" -eq 1 ]]; then
  DB_PASS="${OVERRIDE_DB_PASS}"
fi
if [[ "${OVERRIDE_DB_HOST_SET}" -eq 1 ]]; then
  DB_HOST="${OVERRIDE_DB_HOST}"
fi
if [[ "${OVERRIDE_DB_PORT_SET}" -eq 1 ]]; then
  DB_PORT="${OVERRIDE_DB_PORT}"
fi
if [[ "${OVERRIDE_DB_NAME_SET}" -eq 1 ]]; then
  DB_NAME="${OVERRIDE_DB_NAME}"
fi

if [[ "${NO_PASS}" -eq 0 ]]; then
  if [[ "${PROMPT_PASS}" -eq 1 ]]; then
    read -r -s -p "Ingrese DB_PASS: " DB_PASS
    echo ""
  elif [[ -z "${DB_PASS}" ]]; then
    read -r -s -p "Ingrese DB_PASS: " DB_PASS
    echo ""
  fi
fi

DUMP_FILE="${1:-}"

if [[ -z "${DUMP_FILE}" ]]; then
  echo "Uso: bash scripts/restore_from_sql.sh /ruta/al/dump.sql"
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "No existe el archivo: ${DUMP_FILE}"
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql no esta instalado. Instale PostgreSQL client primero."
  exit 1
fi

if [[ "${DUMP_FILE}" != *.sql ]]; then
  echo "Este script solo admite dumps .sql."
  exit 1
fi

use_socket=0
if [[ "${NO_PASS}" -eq 1 ]]; then
  if [[ "${DB_HOST}" == "127.0.0.1" || "${DB_HOST}" == "localhost" ]]; then
    use_socket=1
  fi
fi

echo "Restaurando en ${DB_HOST}:${DB_PORT}/${DB_NAME} con usuario ${DB_USER}"
if [[ "${CLEAN_RESTORE}" -eq 1 ]]; then
  echo "Eliminando esquema public actual (CASCADE)..."
  if [[ -n "${DB_PASS}" ]]; then
    PGPASSWORD="${DB_PASS}" \
      psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
      -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
  elif [[ "${use_socket}" -eq 1 ]]; then
    psql -U "${DB_USER}" -d "${DB_NAME}" \
      -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
  else
    psql -w -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
      -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
  fi
fi

if [[ -n "${DB_PASS}" ]]; then
  PGPASSWORD="${DB_PASS}" \
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 -f "${DUMP_FILE}"
elif [[ "${use_socket}" -eq 1 ]]; then
  psql -U "${DB_USER}" -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 -f "${DUMP_FILE}"
else
  psql -w -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 -f "${DUMP_FILE}"
fi

echo "Restore completado."
