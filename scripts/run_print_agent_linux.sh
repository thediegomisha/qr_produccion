#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ -f "${ROOT_DIR}/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/backend/.env"
  set +a
fi

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

export PYTHONPATH="${ROOT_DIR}/backend"

AGENT_TOKEN="${AGENT_TOKEN:-${PRINT_AGENT_TOKEN:-change-me}}"
AGENT_ID="${AGENT_ID:-agent-001}"
AGENT_HOST="${AGENT_HOST:-0.0.0.0}"
AGENT_PORT="${AGENT_PORT:-5000}"

export AGENT_TOKEN
export AGENT_ID

echo "Print Agent -> http://${AGENT_HOST}:${AGENT_PORT}"
echo "AGENT_ID=${AGENT_ID}"
echo "Health check: curl http://127.0.0.1:${AGENT_PORT}/health"

exec "${PYTHON_BIN}" -m uvicorn app.print_agent.agent_app:app --host "${AGENT_HOST}" --port "${AGENT_PORT}"
