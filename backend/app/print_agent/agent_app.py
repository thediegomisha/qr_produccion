#!/usr/bin/env python3
"""
Print Agent (FastAPI) - minimal, robust, cross-platform-friendly agent.

Endpoints:
- GET  /health
- GET  /printers          (requires X-Agent-Token)
- POST /jobs              (requires X-Agent-Token) -> queues job + worker processes
- GET  /jobs/{job_id}     (requires X-Agent-Token)
Config via ENV: AGENT_TOKEN, AGENT_ID, PRINTERS_JSON, DB_PATH
"""
import os
import json
import logging
import base64
import uuid
import socket
import subprocess
import sqlite3
import time
import threading
import shutil
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# -----------------------------
# Configuration (env)
# -----------------------------
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "change-me")
AGENT_ID = os.getenv("AGENT_ID", "agent-unknown")
PRINTERS_JSON = os.getenv("PRINTERS_JSON", "[]")  # JSON list of printer configs
DB_PATH = os.getenv("DB_PATH", "print_agent_jobs.db")
WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "2"))  # seconds
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "2"))  # seconds

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("print_agent")

# -----------------------------
# Load configured printers from PRINTERS_JSON
# Each printer: {"name": "zebra1", "type": "network", "host": "...", "port":9100}
# or {"name": "office_lp", "type":"command", "cmd": ["lp", "-d", "Zebra_TP"]}
# -----------------------------
try:
    CONFIGURED_PRINTERS: List[Dict[str, Any]] = json.loads(PRINTERS_JSON) if PRINTERS_JSON else []
    if not isinstance(CONFIGURED_PRINTERS, list):
        logger.warning("PRINTERS_JSON not a list; using empty list")
        CONFIGURED_PRINTERS = []
except Exception as e:
    logger.exception("Failed to parse PRINTERS_JSON; using empty list: %s", e)
    CONFIGURED_PRINTERS = []

# -----------------------------
# Local printer detection
# -----------------------------
def detect_local_printers() -> List[Dict[str, Any]]:
    """
    Detect local printers on the host.
    - On Linux/macOS: uses lpstat -a (CUPS).
    - On Windows: uses win32print if available.
    Returns a list of printers in the format similar to PRINTERS_JSON,
    typically type 'command' with cmd ["lp", "-d", "<printer>"] so the worker can call lp.
    """
    printers: List[Dict[str, Any]] = []

    # Windows detection (win32print)
    if sys.platform.startswith("win"):
        try:
            import win32print  # type: ignore
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            for p in win32print.EnumPrinters(flags):
                # p is tuple, name usually at index 2
                name = p[2]
                printers.append({
                    "name": name,
                    "type": "windows",
                    # we will retry using win32print printing path in worker if needed
                })
            logger.info("Detected %d Windows printers via win32print", len(printers))
            return printers
        except Exception as e:
            logger.debug("win32print not available or detection failed: %s", e)
            return printers

    # Unix-like (lpstat)
    if shutil.which("lpstat"):
        try:
            out = subprocess.run(["lpstat", "-a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=5)
            text = out.stdout.decode(errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # line example: "EPSON_L5590_Series accepting requests since ...", printer name is first token
                name = line.split()[0]
                # produce a printer config that the agent can use: a 'command' printer that uses lp
                if shutil.which("lp"):
                    cmd = ["lp", "-d", name]
                    printers.append({
                        "name": name,
                        "type": "command",
                        "cmd": cmd,
                        "source": "auto"
                    })
                else:
                    # if lp not available, still include the printer as 'local' so UI can show it
                    printers.append({
                        "name": name,
                        "type": "local",
                        "source": "auto"
                    })
            logger.info("Detected %d local printers via lpstat", len(printers))
            return printers
        except subprocess.TimeoutExpired:
            logger.warning("lpstat timed out while detecting printers")
            return printers
        except Exception as e:
            logger.exception("Error detecting printers with lpstat: %s", e)
            return printers
    else:
        logger.debug("lpstat not found on PATH; skipping local detection")
        return printers

# Merge configured printers and detected printers, preferring configured entries when name collides
def build_printer_list() -> List[Dict[str, Any]]:
    detected = detect_local_printers()
    result: List[Dict[str, Any]] = []
    seen = set()

    # First: include configured printers (explicit)
    for p in CONFIGURED_PRINTERS:
        name = p.get("name")
        if not name:
            continue
        entry = dict(p)  # copy
        entry["source"] = "config"
        result.append(entry)
        seen.add(name)

    # Then: include detected printers that are not configured
    for p in detected:
        name = p.get("name")
        if not name or name in seen:
            continue
        result.append(dict(p))
        seen.add(name)

    return result

# Build PRINTER_MAP used by worker: map name -> config
def build_printer_map() -> Dict[str, Dict[str, Any]]:
    printers = build_printer_list()
    return {p["name"]: p for p in printers if "name" in p}

# initialize PRINTER_MAP
PRINTER_MAP = build_printer_map()
PRINTERS = build_printer_list()  # canonical list served by /printers

# -----------------------------
# DB helpers (SQLite)
# -----------------------------
def init_db(path: str):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            printer TEXT NOT NULL,
            payload BLOB NOT NULL,
            copies INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn

_db_conn = init_db(DB_PATH)

def db_insert_job(job_id: str, printer: str, payload: bytes, copies: int):
    now = datetime.utcnow().isoformat()
    _db_conn.execute(
        "INSERT INTO jobs (id, printer, payload, copies, status, attempts, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, printer, payload, copies, "queued", 0, now, now),
    )
    _db_conn.commit()

def db_fetch_one_queued():
    cur = _db_conn.execute("SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None
    job_id = row[0]
    now = datetime.utcnow().isoformat()
    res = _db_conn.execute(
        "UPDATE jobs SET status = 'processing', attempts = attempts + 1, updated_at = ? WHERE id = ? AND status = 'queued'",
        (now, job_id),
    )
    _db_conn.commit()
    if res.rowcount == 1:
        cur = _db_conn.execute("SELECT id, printer, payload, copies, attempts FROM jobs WHERE id = ?", (job_id,))
        r = cur.fetchone()
        if r:
            return {"id": r[0], "printer": r[1], "payload": r[2], "copies": r[3], "attempts": r[4]}
    return None

def db_update_job_done(job_id: str):
    now = datetime.utcnow().isoformat()
    _db_conn.execute("UPDATE jobs SET status = 'done', updated_at = ?, last_error = NULL WHERE id = ?", (now, job_id))
    _db_conn.commit()

def db_update_job_failed(job_id: str, error_msg: str):
    now = datetime.utcnow().isoformat()
    _db_conn.execute(
        "UPDATE jobs SET status = 'failed', last_error = ?, updated_at = ? WHERE id = ?",
        (error_msg[:1000], now, job_id),
    )
    _db_conn.commit()

def db_requeue_with_backoff(job_id: str, attempts: int, error_msg: str):
    if attempts >= MAX_RETRIES:
        db_update_job_failed(job_id, f"Max retries reached: {error_msg}")
        return
    now = datetime.utcnow().isoformat()
    _db_conn.execute(
        "UPDATE jobs SET status = 'queued', last_error = ?, updated_at = ? WHERE id = ?",
        (error_msg[:1000], now, job_id),
    )
    _db_conn.commit()

def db_get_job(job_id: str):
    cur = _db_conn.execute("SELECT id, printer, attempts, status, last_error, created_at, updated_at FROM jobs WHERE id = ?", (job_id,))
    r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "printer": r[1],
        "attempts": r[2],
        "status": r[3],
        "last_error": r[4],
        "created_at": r[5],
        "updated_at": r[6],
    }

# -----------------------------
# Printing backends
# -----------------------------
def send_to_network_printer(host: str, port: int, data: bytes, timeout: int = 10):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            s.sendall(data)
    except Exception as e:
        raise RuntimeError(f"Network send error to {host}:{port} -> {e}")

def send_to_command_printer(cmd: List[str], data: bytes, timeout: int = 30):
    try:
        proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="ignore")
            raise RuntimeError(f"Command failed: {stderr}")
    except Exception as e:
        raise RuntimeError(f"Command execution error: {e}")

def send_to_windows_printer(printer_name: str, data: bytes):
    """
    If running on Windows and win32print is available, use it.
    """
    try:
        import win32print  # type: ignore
        import win32con    # type: ignore
    except Exception as e:
        raise RuntimeError("win32print not available on this system")

    ph = win32print.OpenPrinter(printer_name)
    try:
        # StartDocPrinter/WritePrinter expects bytes
        job_info = ("PrintAgentJob", None, "RAW")
        hjob = win32print.StartDocPrinter(ph, 1, job_info)
        win32print.StartPagePrinter(ph)
        win32print.WritePrinter(ph, data)
        win32print.EndPagePrinter(ph)
        win32print.EndDocPrinter(ph)
    finally:
        win32print.ClosePrinter(ph)

# -----------------------------
# Worker thread
# -----------------------------
_worker_stop = threading.Event()

def worker_loop(poll_interval: float):
    logger.info("Worker started, polling every %s seconds", poll_interval)
    while not _worker_stop.is_set():
        try:
            job = db_fetch_one_queued()
            if not job:
                time.sleep(poll_interval)
                continue

            job_id = job["id"]
            printer_name = job["printer"]
            payload = job["payload"]
            copies = int(job["copies"])
            attempts = int(job["attempts"])

            logger.info("Processing job %s -> printer=%s attempts=%s", job_id, printer_name, attempts)

            # Refresh PRINTER_MAP every job in case runtime printers changed (e.g. new lpstat)
            global PRINTER_MAP
            PRINTER_MAP = build_printer_map()

            p = PRINTER_MAP.get(printer_name)
            if not p:
                err = f"Printer config '{printer_name}' not found"
                logger.error(err)
                db_update_job_failed(job_id, err)
                continue

            try:
                if p.get("type") == "network":
                    host = p.get("host")
                    port = p.get("port", 9100)
                    if not host:
                        raise RuntimeError("Printer config missing host")
                    for i in range(copies):
                        send_to_network_printer(host, port, payload)
                elif p.get("type") == "command":
                    cmd = p.get("cmd")
                    if isinstance(cmd, str):
                        cmd_list = cmd.split()
                    else:
                        cmd_list = cmd
                    for i in range(copies):
                        send_to_command_printer(cmd_list, payload)
                elif p.get("type") == "windows":
                    for i in range(copies):
                        send_to_windows_printer(printer_name, payload)
                elif p.get("type") == "local":
                    # local without lp command; fail gracefully
                    raise RuntimeError("Printer type 'local' unsupported for automatic printing (no command provided)")
                else:
                    raise RuntimeError(f"Unsupported printer type: {p.get('type')}")
            except Exception as e:
                logger.exception("Job %s printing error: %s", job_id, e)
                db_requeue_with_backoff(job_id, attempts, str(e))
                time.sleep(min(10, RETRY_BACKOFF_BASE ** attempts))
                continue

            db_update_job_done(job_id)
            logger.info("Job %s done", job_id)

        except Exception as e:
            logger.exception("Worker unexpected error: %s", e)
            time.sleep(1)

# -----------------------------
# FastAPI app and endpoints
# -----------------------------
app = FastAPI(title="Print Agent")

class JobRequest(BaseModel):
    printer: str
    raw_base64: Optional[str] = None
    raw_text: Optional[str] = None
    copies: int = 1
    client_job_id: Optional[str] = None

def require_token(request: Request):
    token = request.headers.get("X-Agent-Token")
    if not token or token != AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid agent token")

@app.on_event("startup")
def on_startup():
    t = threading.Thread(target=worker_loop, args=(WORKER_POLL_INTERVAL,), daemon=True)
    t.start()
    logger.info("Agent %s starting. Printers: %s", AGENT_ID, list(PRINTER_MAP.keys()))

@app.on_event("shutdown")
def on_shutdown():
    _worker_stop.set()
    logger.info("Agent shutting down")

@app.get("/health")
def health():
    return {"ok": True, "agent_id": AGENT_ID, "printers": list(PRINTER_MAP.keys())}

@app.get("/printers")
def list_printers(request: Request):
    # show both configured and detected printers; token required
    require_token(request)
    # rebuild to include any runtime-detected printers
    combined = build_printer_list()
    # Only include select fields in response
    out = []
    for p in combined:
        entry = {
            "name": p.get("name"),
            "type": p.get("type"),
            "source": p.get("source", "config"),
        }
        if p.get("type") == "network":
            entry["host"] = p.get("host")
            entry["port"] = p.get("port", 9100)
        if p.get("type") == "command":
            entry["cmd"] = p.get("cmd")
        out.append(entry)
    return out

@app.post("/jobs")
def post_job(job: JobRequest, request: Request):
    require_token(request)
    # validate printer exists in current map
    # rebuild PRINTER_MAP to ensure we include detected printers
    global PRINTER_MAP
    PRINTER_MAP = build_printer_map()
    if job.printer not in PRINTER_MAP:
        raise HTTPException(status_code=404, detail=f"Printer '{job.printer}' not found")
    if job.raw_base64:
        try:
            payload = base64.b64decode(job.raw_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {e}")
    elif job.raw_text is not None:
        payload = job.raw_text.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide raw_base64 or raw_text")
    if job.copies < 1 or job.copies > 100:
        raise HTTPException(status_code=400, detail="copies must be between 1 and 100")
    job_id = job.client_job_id or str(uuid.uuid4())
    try:
        db_insert_job(job_id, job.printer, payload, int(job.copies))
    except Exception as e:
        logger.exception("Failed inserting job: %s", e)
        raise HTTPException(status_code=500, detail="Failed to persist job")
    logger.info("Job %s queued for printer %s (copies=%s)", job_id, job.printer, job.copies)
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    require_token(request)
    j = db_get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return j