import os, json, requests

TOKEN = os.getenv("PRINT_AGENT_TOKEN")
AGENTS = json.loads(os.getenv("PRINT_AGENTS_JSON", "[]"))

def list_agents():
    return AGENTS

def get_agent(agent_id: str):
    for a in AGENTS:
        if a["id"] == agent_id:
            return a
    return None

def agent_headers():
    return {"X-Agent-Token": TOKEN}

def agent_printers(agent_id: str):
    a = get_agent(agent_id)
    r = requests.get(f'{a["base_url"]}/printers', headers=agent_headers(), timeout=3)
    r.raise_for_status()
    return r.json()

def enviar_job_agente(agent_id: str, printer: str, raw: str):
    a = get_agent(agent_id)
    r = requests.post(
        f'{a["base_url"]}/jobs',
        json={"printer": printer, "raw": raw},
        headers=agent_headers(),
        timeout=5
    )
    r.raise_for_status()
    return r.json()


