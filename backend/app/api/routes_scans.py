from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from datetime import datetime, timezone, timedelta
import json

from app.db.base import SessionLocal
from app.db.models import QREmitido
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/scans", tags=["scans"])


# =========================
# MODELOS
# =========================
class ScanItem(BaseModel):
    token: str
    dni: str
    scanned_at: datetime
    raw: Optional[Dict[str, Any]] = None


class BatchIn(BaseModel):
    batch_uuid: str
    session_uuid: Optional[str] = None
    device_id: Optional[str] = None
    shift_label: Optional[str] = None
    lote_codigo: str
    scans: List[ScanItem]


def _norm_lote(c: str) -> str:
    return (c or "").strip().upper()


# =========================
# ENDPOINTS
# =========================
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
        return {
            "batch_uuid": payload.batch_uuid,
            "accepted_count": 0,
            "duplicate_count": 0
        }

    if len(payload.scans) > 5000:
        raise HTTPException(400, "Máximo 5000 lecturas por lote de envío")
    now = datetime.now(timezone.utc)
    for scan in payload.scans:
        if not scan.token.strip() or len(scan.token) > 128:
            raise HTTPException(400, "Token inválido")
        if len(scan.dni) != 8 or not scan.dni.isascii() or not scan.dni.isdigit():
            raise HTTPException(400, "DNI inválido")
        when = scan.scanned_at
        # Las APK antiguas pueden enviar hora UTC sin sufijo.
        when = when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
        if when > now + timedelta(minutes=5) or when.year < 2020:
            raise HTTPException(400, "Fecha de lectura inválida")

    lote_codigo = _norm_lote(payload.lote_codigo)
    if not lote_codigo:
        raise HTTPException(400, "Falta lote_codigo")

    insert_sql = text("""
        INSERT INTO scan_events (
            token,
            dni,
            user_id,
            device_id,
            scanned_at,
            batch_uuid,
            session_uuid,
            raw,
            lote_id
        )
        VALUES (
            :token,
            :dni,
            :user_id,
            :device_id,
            :scanned_at,
            :batch_uuid,
            :session_uuid,
            CAST(:raw AS jsonb),
            :lote_id
        )
        ON CONFLICT (token) DO NOTHING
        RETURNING token
    """)

    accepted = 0

    with SessionLocal() as db:
        # Validar el envío entero antes de crear lotes o insertar lecturas.
        tokens = {scan.token.strip() for scan in payload.scans}
        emissions = {
            row.token: row for row in db.query(QREmitido).filter(QREmitido.token.in_(tokens)).all()
        }
        for scan in payload.scans:
            emission = emissions.get(scan.token.strip())
            if emission is None or emission.dni_trabajador.strip() != scan.dni:
                raise HTTPException(400, "QR no emitido o DNI no coincide con la emisión")

        # 1) Resolver / crear lote
        lote_row = db.execute(
            text("SELECT id, estado FROM lotes WHERE codigo = :c FOR UPDATE"),
            {"c": lote_codigo},
        ).fetchone()

        if lote_row is None:
            lote_row = db.execute(
                text("""
                    INSERT INTO lotes (codigo, estado, creado_por)
                    VALUES (:c, 'ABIERTO', :u)
                    RETURNING id, estado
                """),
                {"c": lote_codigo, "u": user.get("usuario")},
            ).fetchone()
        if lote_row.estado == "CERRADO":
            raise HTTPException(409, f"Lote {lote_codigo} está CERRADO")

        lote_id = lote_row.id

        # 2) Insertar scans
        for s in payload.scans:
            token = (s.token or "").strip()
            dni = (s.dni or "").strip()

            if not token or not dni:
                continue

            raw_dict = s.raw or {}

            # Guardar shift_label dentro del raw (no altera esquema)
            if payload.shift_label:
                raw_dict.setdefault("shift_label", payload.shift_label)

            raw_json = json.dumps(raw_dict) if raw_dict else None

            # La columna es timestamp sin zona: normalizar a UTC explícito para que
            # la hora almacenada no dependa de la zona horaria del servidor.
            scanned_at = s.scanned_at
            if scanned_at.tzinfo is not None:
                scanned_at = scanned_at.astimezone(timezone.utc).replace(tzinfo=None)

            r = db.execute(
                insert_sql,
                {
                    "token": token,
                    "dni": dni,
                    "user_id": user["usuario"],
                    "device_id": payload.device_id,
                    "scanned_at": scanned_at,
                    "batch_uuid": payload.batch_uuid,
                    "session_uuid": payload.session_uuid,
                    "raw": raw_json,
                    "lote_id": lote_id,
                }
            ).fetchone()

            if r is not None:
                accepted += 1

        db.commit()

    duplicates = len(payload.scans) - accepted
    return {
        "batch_uuid": payload.batch_uuid,
        "accepted_count": accepted,
        "duplicate_count": duplicates
    }
