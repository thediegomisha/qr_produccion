from fastapi import FastAPI, Depends, HTTPException
from agent.security import verify_agent_token
from agent.printers import printer_provider
from agent.models import PrintJobIn, PrintJob
from agent.queue_worker import enqueue, get_job, get_state, start_worker
from agent.audit import audit
from agent.env import AGENT_ID, AGENT_NAME

app = FastAPI(title="QR Print Agent")

@app.on_event("startup")
async def _startup():
    import asyncio
    start_worker(asyncio.get_event_loop())
    audit("agent_startup", {"agent_id": AGENT_ID, "name": AGENT_NAME})

@app.get("/health")
def health():
    # público: para saber si está vivo (sin datos sensibles)
    return {"ok": True, "agent_id": AGENT_ID, "name": AGENT_NAME}

@app.get("/status", dependencies=[Depends(verify_agent_token)])
def status():
    return {
        "ok": True,
        "agent_id": AGENT_ID,
        "name": AGENT_NAME,
        **get_state(),
    }

@app.get("/printers", dependencies=[Depends(verify_agent_token)])
def list_printers():
    return printer_provider.list_printers()

@app.post("/jobs", dependencies=[Depends(verify_agent_token)])
async def create_job(payload: PrintJobIn):
    try:
        job = PrintJob(printer=payload.printer, raw=payload.raw)
        job = await enqueue(job)
        return job.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/jobs/{job_id}", dependencies=[Depends(verify_agent_token)])
async def job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job.model_dump()
