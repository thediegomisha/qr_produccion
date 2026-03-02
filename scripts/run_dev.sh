#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${ROOT_DIR}/.venv/bin/python"
STREAMLIT_BIN="${ROOT_DIR}/.venv/bin/streamlit"
BACKEND_LOG="/tmp/qr_backend_dev.log"
BACKEND_PID_FILE="${ROOT_DIR}/.dev_backend.pid"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

port_is_in_use() {
  local port="$1"
  python3 - <<PY
import socket
s = socket.socket()
s.settimeout(0.3)
in_use = s.connect_ex(('127.0.0.1', int('${port}'))) == 0
s.close()
raise SystemExit(0 if in_use else 1)
PY
}

if [[ ! -x "${VENV_PY}" ]]; then
  echo "No se encontro Python en .venv. Cree el entorno primero:"
  echo "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -x "${STREAMLIT_BIN}" ]]; then
  echo "No se encontro Streamlit en .venv. Instale dependencias con requirements.txt"
  exit 1
fi

backend_started_by_script=0

if "${VENV_PY}" - <<'PY' >/dev/null 2>&1
import requests
requests.get('http://127.0.0.1:8000/api/setup/status', timeout=1)
PY
then
  echo "Backend ya esta activo en http://127.0.0.1:8000"
else
  echo "Iniciando backend (uvicorn) en puerto 8000..."
  (
    cd "${ROOT_DIR}/backend"
    exec "${VENV_PY}" -m uvicorn app.main:app --reload --port 8000
  ) >"${BACKEND_LOG}" 2>&1 &

  backend_pid=$!
  echo "${backend_pid}" > "${BACKEND_PID_FILE}"
  backend_started_by_script=1

  "${VENV_PY}" - <<'PY'
import requests
import time

last_error = None
for _ in range(30):
    try:
        r = requests.get('http://127.0.0.1:8000/api/setup/status', timeout=1)
        if r.status_code == 200:
            print('Backend OK')
            break
    except Exception as e:
        last_error = e
    time.sleep(0.3)
else:
    raise SystemExit(f'No se pudo iniciar backend: {last_error}')
PY
fi

cleanup() {
  if [[ "${backend_started_by_script}" -eq 1 && -f "${BACKEND_PID_FILE}" ]]; then
    pid="$(cat "${BACKEND_PID_FILE}")"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${BACKEND_PID_FILE}"
  fi
}

trap cleanup EXIT INT TERM

if port_is_in_use "${STREAMLIT_PORT}"; then
  if [[ "${STREAMLIT_PORT}" == "8501" ]] && ! port_is_in_use "8502"; then
    echo "Puerto 8501 ocupado. Usando 8502 para Streamlit."
    STREAMLIT_PORT="8502"
  else
    echo "El puerto ${STREAMLIT_PORT} ya esta en uso."
    echo "Use otro puerto: STREAMLIT_PORT=8502 bash scripts/run_dev.sh"
    exit 1
  fi
fi

echo "Abriendo frontend en http://localhost:${STREAMLIT_PORT}"
exec "${STREAMLIT_BIN}" run "${ROOT_DIR}/ui_web/streamlit_app.py" --server.port "${STREAMLIT_PORT}"
