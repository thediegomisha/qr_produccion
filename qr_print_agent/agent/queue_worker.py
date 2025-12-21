import asyncio, time, math
from collections import deque
from agent.models import PrintJob
from agent.printers import printer_provider
from agent.audit import audit
from agent.env import QUEUE_MAX, RETRY_MAX, RETRY_BASE_SECONDS

_jobs = deque()          # FIFO
_job_index = {}          # job_id -> PrintJob
_lock = asyncio.Lock()
_worker_task = None
_is_running = False

def get_state():
    return {
        "queue_len": len(_jobs),
        "jobs_total": len(_job_index),
        "running": _is_running,
    }

async def enqueue(job: PrintJob) -> PrintJob:
    async with _lock:
        if len(_jobs) >= QUEUE_MAX:
            raise RuntimeError("Cola llena, intente nuevamente")
        _jobs.append(job.job_id)
        _job_index[job.job_id] = job
    audit("job_queued", {"job_id": job.job_id, "printer": job.printer})
    return job

async def get_job(job_id: str) -> PrintJob | None:
    async with _lock:
        return _job_index.get(job_id)

async def _run_loop():
    global _is_running
    _is_running = True
    try:
        while True:
            job_id = None
            async with _lock:
                if _jobs:
                    job_id = _jobs.popleft()

            if not job_id:
                await asyncio.sleep(0.1)
                continue

            async with _lock:
                job = _job_index.get(job_id)

            if not job:
                continue

            # ejecutar
            job.status = "printing"
            job.attempts += 1
            audit("job_printing", {"job_id": job.job_id, "attempt": job.attempts})

            try:
                printer_provider.print_raw(job.printer, job.raw.encode())
                job.status = "done"
                job.last_error = None
                audit("job_done", {"job_id": job.job_id})
            except Exception as e:
                job.last_error = str(e)
                audit("job_error", {"job_id": job.job_id, "error": job.last_error})

                if job.attempts < RETRY_MAX:
                    # backoff exponencial
                    delay = RETRY_BASE_SECONDS * math.pow(2, job.attempts - 1)
                    await asyncio.sleep(delay)
                    job.status = "queued"
                    async with _lock:
                        _jobs.appendleft(job.job_id)  # reintento pronto
                else:
                    job.status = "failed"
                    audit("job_failed", {"job_id": job.job_id, "attempts": job.attempts})
    finally:
        _is_running = False

def start_worker(loop: asyncio.AbstractEventLoop):
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = loop.create_task(_run_loop())
