import json, time, os
from agent.env import AUDIT_LOG_PATH, AGENT_ID

def audit(event: str, payload: dict):
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH) or ".", exist_ok=True)
    record = {
        "ts": time.time(),
        "agent_id": AGENT_ID,
        "event": event,
        "payload": payload,
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
