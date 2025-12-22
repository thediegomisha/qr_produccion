from dotenv import load_dotenv
load_dotenv()

from agent.api import app
from fastapi import FastAPI, Depends
from agent.security import verify_agent_token
from agent.printers import list_printers

app = FastAPI()

@app.get("/printers", dependencies=[Depends(verify_agent_token)])
def printers():
    return list_printers()
