#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE=""
INCLUDE_GLOBALS=0
OUT_FILE=""

DB_USER_DEFAULT="qr_user"
DB_PASS_DEFAULT=""
DB_HOST_DEFAULT="127.0.0.1"
DB_PORT_DEFAULT="5432"
DB_NAME_DEFAULT="qr_produccion"

OVERRIDE_DB_HOST=""
OVERRIDE_DB_PORT=""
OVERRIDE_DB_USER=""
OVERRIDE_DB_PASS=""
OVERRIDE_DB_NAME=""

usage() {
  echo "Uso: bash scripts/backup_to_sql.sh [--globals] [--env /ruta/.env] \\\n+  [--host HOST] [--port PORT] [--user USER] [--pass PASS] [--name DB] [output.sql]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --globals)
      INCLUDE_GLOBALS=1
      shift
      ;;
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    --host)
      OVERRIDE_DB_HOST="$2"
      shift 2
      ;;
    --port)
      OVERRIDE_DB_PORT="$2"
      shift 2
      ;;
    --user)
      OVERRIDE_DB_USER="$2"
      shift 2
      ;;
    --pass)
      OVERRIDE_DB_PASS="$2"
      shift 2
      ;;
    --name)
      OVERRIDE_DB_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "${OUT_FILE}" ]]; then
        OUT_FILE="$1"
        shift
      else
        echo "Argumento desconocido: $1"
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "${ENV_FILE}" ]]; then
  if [[ -f "${ROOT_DIR}/backend/.env" ]]; then
    ENV_FILE="${ROOT_DIR}/backend/.env"
  elif [[ -f "${ROOT_DIR}/.env" ]]; then
    ENV_FILE="${ROOT_DIR}/.env"
  fi
fi

if [[ -n "${ENV_FILE}" && -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

DB_USER="${DB_USER:-${DB_USER_DEFAULT}}"
DB_PASS="${DB_PASS:-${DB_PASS_DEFAULT}}"
DB_HOST="${DB_HOST:-${DB_HOST_DEFAULT}}"
DB_PORT="${DB_PORT:-${DB_PORT_DEFAULT}}"
DB_NAME="${DB_NAME:-${DB_NAME_DEFAULT}}"

if [[ -n "${OVERRIDE_DB_HOST}" ]]; then
  DB_HOST="${OVERRIDE_DB_HOST}"
fi
if [[ -n "${OVERRIDE_DB_PORT}" ]]; then
  DB_PORT="${OVERRIDE_DB_PORT}"
fi
if [[ -n "${OVERRIDE_DB_USER}" ]]; then
  DB_USER="${OVERRIDE_DB_USER}"
fi
if [[ -n "${OVERRIDE_DB_PASS}" ]]; then
  DB_PASS="${OVERRIDE_DB_PASS}"
fi
if [[ -n "${OVERRIDE_DB_NAME}" ]]; then
  DB_NAME="${OVERRIDE_DB_NAME}"
fi

if [[ -z "${DB_PASS}" ]]; then
  read -r -s -p "Ingrese DB_PASS: " DB_PASS
  echo ""
fi

if [[ -z "${OUT_FILE}" ]]; then
  timestamp="$(date +%Y%m%d_%H%M%S)"
  OUT_FILE="${ROOT_DIR}/backups/${DB_NAME}_${timestamp}.sql"
fi

OUT_DIR="$(dirname "${OUT_FILE}")"
mkdir -p "${OUT_DIR}"

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump no esta instalado. Instale PostgreSQL client primero."
  exit 1
fi

if [[ "${INCLUDE_GLOBALS}" -eq 1 ]] && ! command -v pg_dumpall >/dev/null 2>&1; then
  echo "pg_dumpall no esta instalado. Instale PostgreSQL client primero."
  exit 1
fi

echo "Generando backup de ${DB_HOST}:${DB_PORT}/${DB_NAME} en ${OUT_FILE}"
if [[ "${INCLUDE_GLOBALS}" -eq 1 ]]; then
  globals_file="${OUT_FILE%.sql}.globals.sql"
  echo "Incluyendo roles/privilegios globales en ${globals_file}"
  if ! PGPASSWORD="${DB_PASS}" \
    pg_dumpall -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" \
    --globals-only -f "${globals_file}"; then
    echo "No se pudieron exportar roles globales."
    echo "Requiere superusuario o rol con permisos para pg_authid."
  fi
fi

PGPASSWORD="${DB_PASS}" \
  pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" \
  -F p -f "${OUT_FILE}" "${DB_NAME}"

echo "Backup completado."
