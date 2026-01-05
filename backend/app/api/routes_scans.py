from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from datetime import datetime
import json

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanItem(BaseModel):
    token: str
    dni: str
    scanned_at: datetime
    raw: Optional[Dict[str, Any]] = None


class BatchIn(BaseModel):
    batch_uuid: str
    session_uuid: Optional[str] = None
    device_id: Optional[str] = None
    shift_label: Optional[str] = None  # NO es columna en DB; lo guardaremos dentro de raw
    scans: List[ScanItem]


@router.get("/exists/{token}")
def token_exists(token: str, user=Depends(get_current_user)):
    t = (token or "").strip()
    if not t:
        raise HTTPException(400, "Token inválido")

    with SessionLocal() as db:
        r = db.execute(
            text("SELECT 1 FROM scan_events WHERE token = :t LIMIT 1"),
            {"t": t}
        ).fetchone()

    return {"token": t, "exists": r is not None}


@router.post("/batch")
def upload_batch(payload: BatchIn, user=Depends(get_current_user)):
    if payload.scans is None:
        raise HTTPException(400, "Falta scans")

    if len(payload.scans) == 0:
        return {"batch_uuid": payload.batch_uuid, "accepted_count": 0, "duplicate_count": 0}

    sql = text("""
        INSERT INTO scan_events(token, dni, user_id, device_id, scanned_at, batch_uuid, session_uuid, raw)
        VALUES (:token, :dni, :user_id, :device_id, :scanned_at, :batch_uuid, :session_uuid, CAST(:raw AS jsonb))
        ON CONFLICT ON CONSTRAINT scan_events_token_uq DO NOTHING
        RETURNING token
    """)

    accepted = 0

    with SessionLocal() as db:
        for s in payload.scans:
            token = (s.token or "").strip()
            dni = (s.dni or "").strip()

            if not token or not dni:
                # si quieres: contar inválidos; por ahora simplemente ignoramos
                continue

            # raw: aquí debe venir {token,dni,id,producto,version,firma,...}
            raw_dict = s.raw or {}

            # Guardar shift_label sin tocar DB: lo metemos dentro de raw
            if payload.shift_label:
                raw_dict.setdefault("shift_label", payload.shift_label)

            raw_json = json.dumps(raw_dict) if raw_dict else None

            r = db.execute(sql, {
                "token": token,
                "dni": dni,
                "user_id": user["usuario"],
                "device_id": payload.device_id,
                "scanned_at": s.scanned_at,
                "batch_uuid": payload.batch_uuid,
                "session_uuid": payload.session_uuid,
                "raw": raw_json
            }).fetchone()

            if r is not None:
                accepted += 1

        db.commit()

    duplicates = len(payload.scans) - accepted
    return {"batch_uuid": payload.batch_uuid, "accepted_count": accepted, "duplicate_count": duplicates}
