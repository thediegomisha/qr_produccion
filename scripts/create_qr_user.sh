#!/usr/bin/env bash
set -euo pipefail
# Autenticación del administrador mediante .pgpass o variables estándar de psql.
: "${QR_DB_PASSWORD:?Define QR_DB_PASSWORD con una contraseña nueva}"
export QR_DB_PASSWORD
psql -X -v ON_ERROR_STOP=1 \
  -f "$(dirname "$0")/setup_qr_db.sql"
