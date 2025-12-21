from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.core.session import get_usuario
from app.core.tokens import generar_token
from app.services.qr_service import generar_qr_memoria
from app.services.zpl_service import generar_zpl_qr
from app.services.agent_client import enviar_job_agente

from app.db.base import SessionLocal
from app.db.models import QREmitido

router = APIRouter(tags=["QR"])


# ==========================================================
# GENERAR QR (PNG) – NO IMPRIME
# ==========================================================
@router.post("/print")
def print_qr(
    data: dict,
    usuario: str = Depends(get_usuario)
):
    # ----------------------------
    # Validación mínima
    # ----------------------------
    required = ["dni", "nn", "producto", "cantidad"]
    if not all(k in data for k in required):
        raise HTTPException(400, "Datos incompletos")

    cantidad = int(data["cantidad"])
    if cantidad < 1 or cantidad > 5000:
        raise HTTPException(400, "Cantidad fuera de rango")

    images = []

    with SessionLocal() as db:
        for _ in range(cantidad):
            token = generar_token(data["producto"])

            qr = QREmitido(
                token=token,
                dni_trabajador=data["dni"],
                nn=data["nn"],
                producto=data["producto"],
                impreso_por=usuario
            )
            db.add(qr)

            img = generar_qr_memoria(
                token,
                data["dni"],
                data["nn"],
                data["producto"]
            )
            images.append(img)

        db.commit()

    # Por ahora devolvemos solo una imagen
    return StreamingResponse(images[0], media_type="image/png")


# ==========================================================
# IMPRIMIR QR (ZPL) – USA PRINT AGENT (COLA)
# ==========================================================
@router.post("/print-zpl")
def print_zpl(
    data: dict,
    usuario: str = Depends(get_usuario)
):
    required = ["dni", "nn", "producto", "cantidad"]
    if not all(k in data for k in required):
        raise HTTPException(400, "Datos incompletos")

    zpl = generar_zpl_qr(
        token=data["nn"],
        dni=data["dni"],
        visible=data["nn"],
        producto=data["producto"],
        cantidad=int(data["cantidad"])
    )

    job = enviar_job_agente(
        agent_id=IMPRESORA_ACTIVA["agent_id"],
        printer=IMPRESORA_ACTIVA["printer"],
        raw=zpl
    )

    return {
        "ok": True,
        "job_id": job["job_id"],
        "enviado_por": usuario
    }

