import os
from fastapi import Header, HTTPException

AGENT_TOKEN = os.getenv("PRINT_AGENT_TOKEN")

def verify_agent_token(x_agent_token: str = Header(...)):
    if not AGENT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="PRINT_AGENT_TOKEN no configurado en el agente"
        )

    if x_agent_token != AGENT_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Token del agente inválido"
        )
