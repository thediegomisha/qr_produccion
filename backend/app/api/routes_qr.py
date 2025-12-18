from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from app.core.tokens import generar_token
from app.core.session import get_usuario
from app.services.qr_service import generar_qr_memoria
from app.db.base import SessionLocal
from app.db.models import QREmitido

router = APIRouter()


@router.post("/print")
def print_qr(data: dict):
    usuario = get_usuario()
    if not usuario:
        raise HTTPException(401, "Usuario no autenticado")

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

    # 👉 por ahora devolvemos SOLO 1 imagen si cantidad = 1
    # 👉 si es >1 luego se empaqueta (ZIP / PDF / impresora)
    return StreamingResponse(images[0], media_type="image/png")

    @router.post("/print-zpl")
    def print_zpl(data: dict):
        dni = data["dni"]
        nn = data["nn"]
        producto = data["producto"]
        cantidad = int(data["cantidad"])
        impresora_id = data["impresora_id"]

        with SessionLocal() as db:
            imp = db.execute(
                text("SELECT * FROM impresoras WHERE id=:id AND activa=true"),
                {"id": impresora_id}
            ).mappings().first()

            if not imp:
                raise HTTPException(404, "Impresora no encontrada")

        # -------------------------
        # Generar ZPL
        # -------------------------
        zpl = generar_zpl_qr(
            token=str(uuid.uuid4()),
            dni=dni,
            visible=nn,
            producto=producto,
            cantidad=cantidad
        )

        # -------------------------
        # Enviar a impresora
        # -------------------------
        enviar_a_impresora(zpl, imp)

        return {"ok": True}
