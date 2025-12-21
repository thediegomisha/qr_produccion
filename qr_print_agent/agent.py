import os
from fastapi import FastAPI, Header, HTTPException
from printers import list_printers
from zpl_sender import send_raw
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("PRINT_AGENT_TOKEN")
PORT = int(os.getenv("AGENT_PORT", 9001))

app = FastAPI(title="QR Print Agent")

def auth(x_agent_token: str = Header(None)):
    if x_agent_token != TOKEN:
        raise HTTPException(401, "Token inválido")

@app.get("/printers")
def printers(x_agent_token: str = Header(None)):
    auth(x_agent_token)
    return list_printers()

@app.post("/jobs")
def job(data: dict, x_agent_token: str = Header(None)):
    auth(x_agent_token)
    send_raw(data["printer"], data["raw"])
    return {"job_id": "ok"}
