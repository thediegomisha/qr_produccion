from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.session import get_usuario
from app.core.tokens import generar_token
from app.services.qr_service import generar_qr_memoria
from app.services.zpl_service import generar_zpl_qr
from app.services.agent_client import enviar_job_agente

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

    tickets = []

    with SessionLocal() as db:
        for _ in range(cantidad):

            # 1️⃣ Token real
            token = generar_token(data["producto"])

            # 2️⃣ Guardar ticket
            qr = QREmitido(
                token=token,
                dni_trabajador=data["dni"],
                nn=data["nn"],
                producto=data["producto"],
                impreso_por=usuario
            )
            db.add(qr)
            db.flush()

            # 3️⃣ Generar ZPL real
            zpl = generar_zpl_qr(
                token=token,
                dni=data["dni"],
                visible=data["nn"],
                producto=data["producto"]
            )

            # 4️⃣ Imprimir UNA VEZ
            job = enviar_job_agente(
                agent_id=IMPRESORA_ACTIVA["agent_id"],
                printer=IMPRESORA_ACTIVA["printer"],
                raw=zpl
            )

            tickets.append({
                "token": token,
                "job_id": job.get("job_id")
            })

        db.commit()

    return {
        "ok": True,
        "cantidad": cantidad,
        "tickets": tickets
    }


