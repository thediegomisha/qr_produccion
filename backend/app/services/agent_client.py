import os
import json
import base64
import logging
from urllib.parse import urlsplit
from fastapi import HTTPException
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger(__name__)

# Token (soporta ambos nombres)
TOKEN = os.getenv("PRINT_AGENT_TOKEN") or os.getenv("AGENT_TOKEN")

# URL directa (recomendado para “dinámico”)
DEFAULT_AGENT_URL = os.getenv("PRINT_AGENT_URL")

# Fallback por lista de agentes
_agents_raw = os.getenv("PRINT_AGENTS_JSON", "[]")
try:
    AGENTS: List[Dict[str, Any]] = json.loads(_agents_raw)
    if not isinstance(AGENTS, list):
        AGENTS = []
except Exception:
    AGENTS = []


def _headers(agent_token: Optional[str] = None) -> Dict[str, str]:
    h: Dict[str, str] = {"Content-Type": "application/json"}
    token = (agent_token or TOKEN or "").strip()
    if token:
        h["X-Agent-Token"] = token
    return h


def _resolve_agent_url(agent_url: Optional[str] = None, agent_id: Optional[str] = None) -> str:
    # 1) URL explícita (desde UI)
    if agent_url:
        candidate = agent_url.rstrip("/")
        allowed = {str(a.get("base_url", "")).rstrip("/") for a in AGENTS}
        allowed.add((DEFAULT_AGENT_URL or "").rstrip("/"))
        allowed.update(
            value.strip().rstrip("/")
            for value in os.getenv("PRINT_AGENT_ALLOWED_URLS", "").split(",") if value.strip()
        )
        parsed = urlsplit(candidate)
        if (
            candidate not in allowed or parsed.scheme not in ("http", "https")
            or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment
        ):
            raise HTTPException(400, "Agente de impresión no autorizado en el servidor")
        return candidate

    # 2) URL por env
    if DEFAULT_AGENT_URL:
        return DEFAULT_AGENT_URL.rstrip("/")

    # 3) Buscar por agent_id en PRINT_AGENTS_JSON
    if agent_id:
        for a in AGENTS:
            if a.get("id") == agent_id and a.get("base_url"):
                return str(a["base_url"]).rstrip("/")
        raise RuntimeError(f"Agent with id '{agent_id}' not found")

    # 4) Primer agente disponible
    if AGENTS and AGENTS[0].get("base_url"):
        return str(AGENTS[0]["base_url"]).rstrip("/")

    raise RuntimeError("No agent configured. Set PRINT_AGENT_URL or PRINT_AGENTS_JSON.")


def enviar_job_agente(
    *,
    printer: str,
    raw: str,
    copies: int = 1,
    agent_url: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_token: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """
    Envía un job ZPL al Print Agent.

    raw: ZPL en string
    """
    base_url = _resolve_agent_url(agent_url=agent_url, agent_id=agent_id)
    url = f"{base_url}/jobs"

    # ZPL -> base64
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    else:
        raw_bytes = raw

    payload = {
        "printer": printer,
        "raw_base64": base64.b64encode(raw_bytes).decode("utf-8"),
        "copies": int(copies),
    }

    r = requests.post(
        url, json=payload, headers=_headers(agent_token=agent_token),
        timeout=timeout, allow_redirects=False,
    )
    if 300 <= r.status_code < 400:
        raise HTTPException(502, "El agente de impresión no puede redirigir solicitudes")
    r.raise_for_status()
    return r.json()
