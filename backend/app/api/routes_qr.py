from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.session import get_usuario
from app.core.tokens import generar_token
from app.services.qr_service import generar_qr_memoria
from app.services.zpl_service import generar_zpl_qr
from app.services.agent_client import enviar_job_agente
from app.services.zpl_service import generar_zpl_qr_4cols
from app.core.security import sign  # si necesitas firmar aquí (si ya firmas en otro lado, usa tu flujo)

from app.db.base import SessionLocal
from app.db.models import QREmitido
from app.config import IMPRESORA_ACTIVA

router = APIRouter(tags=["QR"])

# ==========================================================
# GENERAR QR (PNG) – NO IMPRIME
# ==========================================================
@router.post("/preview")
def preview_qr(data: dict):
    required = ["dni", "nn", "producto"]
    if not all(k in data for k in required):
        raise HTTPException(400, "Datos incompletos")

    # Token SOLO para vista previa (no se guarda)
    token_preview = "VP"

    img = generar_qr_memoria(
        token_preview,
        data["dni"],
        data["nn"],
        data["producto"]
    )

    return StreamingResponse(img, media_type="image/png")


# ==========================================================
# IMPRIMIR QR (ZPL) – USA PRINT AGENT (COLA)
# ==========================================================
@router.post("/print")
def print_tickets(
    data: dict,
    usuario: str = Depends(get_usuario)
):
    required = ["dni", "nn", "producto", "cantidad"]
    if not all(k in data for k in required):
        raise HTTPException(400, "Datos incompletos")

    cantidad = int(data["cantidad"])
    if cantidad < 1 or cantidad > 5000:
        raise HTTPException(400, "Cantidad fuera de rango")

    # Dinámico desde UI (opcional)
    agent_url = data.get("agent_url")  # ej: http://200.100.20.153:5000
    printer = data.get("printer")      # ej: ZT411

    # Fallback a config estática
    if not printer:
        printer = IMPRESORA_ACTIVA["printer"]

    # agent_id solo se usa si NO mandas agent_url
    agent_id = IMPRESORA_ACTIVA.get("agent_id")

    tickets = []

    with SessionLocal() as db:
        remaining = cantidad

        while remaining > 0:
            batch_n = 4 if remaining >= 4 else remaining
            batch_items = []

            # 1) Generar y guardar 1..4 tickets
            for _ in range(batch_n):
                token = generar_token(data["producto"])

                qr = QREmitido(
                    token=token,
                    dni_trabajador=data["dni"],
                    nn=data["nn"],
                    producto=data["producto"],
                    impreso_por=usuario
                )
                db.add(qr)
                db.flush()

                base = f"{token}|{data['dni']}|{data['nn']}|{data['producto']}|1"
                sig = sign(base)

                batch_items.append({
                    "token": token,
                    "dni": data["dni"],
                    "visible": data["nn"],
                    "producto": data["producto"],
                    "sig": sig,
                })

            # 2) ZPL 4 columnas (una fila)
            zpl = generar_zpl_qr_4cols(batch_items, dpi=203, qr_mag=4)

            # 3) Enviar 1 job por fila (4 columnas) usando dinámico si viene
            job = enviar_job_agente(
                agent_url=agent_url,
                agent_id=None if agent_url else agent_id,
                printer=printer,
                raw=zpl,
                copies=1
            )

            job_id = job.get("job_id") or job.get("id")

            for it in batch_items:
                tickets.append({"token": it["token"], "job_id": job_id})

            remaining -= batch_n

        db.commit()

    return {
        "ok": True,
        "cantidad": cantidad,
        "tickets": tickets,
        "printer": printer,
        "agent_url": agent_url
    }

