import os
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)

# Cargar token y lista de agentes desde variables de entorno de forma segura
TOKEN = os.getenv("AGENT_TOKEN")
_agents_raw = os.getenv("PRINT_AGENTS_JSON", "[]")
try:
    AGENTS: List[Dict[str, Any]] = json.loads(_agents_raw) if _agents_raw else []
    if not isinstance(AGENTS, list):
        logger.warning("PRINT_AGENTS_JSON no es una lista; inicializando lista vacía")
        AGENTS = []
except json.JSONDecodeError as e:
    logger.exception("Error parseando PRINT_AGENTS_JSON: %s", e)
    AGENTS = []


def list_agents() -> List[Dict[str, Any]]:
    return AGENTS


def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    for a in AGENTS:
        if a.get("id") == agent_id:
            return a
    return None


def agent_headers() -> Dict[str, str]:
    headers = {}
    if TOKEN:
        headers["X-Agent-Token"] = TOKEN
    return headers


def agent_printers(agent_id: str, timeout: int = 3) -> List[Dict[str, Any]]:
    """
    Obtiene la lista de impresoras desde el agente.
    Lanza RuntimeError en caso de error (agente no encontrado o fallo de red).
    """
    a = get_agent(agent_id)
    if not a:
        raise RuntimeError(f"Agent with id '{agent_id}' not found")

    base_url = a.get("base_url")
    if not base_url:
        raise RuntimeError(f"Agent '{agent_id}' is missing base_url")

    url = f"{base_url.rstrip('/')}/printers"
    try:
        r = requests.get(url, headers=agent_headers(), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (RequestException, Timeout) as e:
        logger.exception("Error contacting agent '%s' at %s: %s", agent_id, base_url, e)
        raise RuntimeError(f"Failed to contact agent '{agent_id}': {e}")


def enviar_job_agente(agent_id: str, printer: str, raw: str, copies: int = 1, timeout: int = 5) -> Dict[str, Any]:
    """
    Envía un job al agente. Lanza RuntimeError si el agente no existe o si hay error de red.
    """
    a = get_agent(agent_id)
    if not a:
        raise RuntimeError(f"Agent with id '{agent_id}' not found")

    base_url = a.get("base_url")
    if not base_url:
        raise RuntimeError(f"Agent '{agent_id}' is missing base_url")

    url = f"{base_url.rstrip('/')}/jobs"
    payload = {"printer": printer, "raw": raw, "copies": int(copies)}
    try:
        r = requests.post(url, json=payload, headers=agent_headers(), timeout=timeout)
        r.raise_for_status()
        # Si el agente devuelve JSON con detalles del job, lo retornamos; si no, devolvemos estado mínimo
        try:
            return r.json()
        except ValueError:
            return {"status": "ok"}
    except (RequestException, Timeout) as e:
        logger.exception("Error sending job to agent '%s' at %s: %s", agent_id, base_url, e)
        raise RuntimeError(f"Failed to send job to agent '{agent_id}': {e}")
