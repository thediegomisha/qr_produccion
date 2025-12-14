from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from uuid import uuid4
from sqlalchemy import text
from datetime import datetime
import io
import zipfile

from app.core.tokens import generar_token
from app.core.session import get_usuario
from app.services.qr_service import generar_qr_memoria
from app.db.base import SessionLocal
from app.db.models import QREmitido

router = APIRouter()


@router.post("/preview")
def preview(data: dict):
    # --------------------------------------------------
    # Usuario activo (auditoría)
    # --------------------------------------------------
    usuario = get_usuario()
    if not usuario:
        raise HTTPException(401, "Usuario no definido")

    # --------------------------------------------------
    # Validación de entrada
    # --------------------------------------------------
    if "trabajador_id" not in data:
        raise HTTPException(400, "trabajador_id requerido")

    trabajador_id = data["trabajador_id"]
    producto = data.get("producto", "UVA")
    visible = data.get("visible")

    # --------------------------------------------------
    # Obtener datos reales del trabajador (BD)
    # --------------------------------------------------
    db = SessionLocal()

    row = db.execute(
        text("""
            SELECT dni, num_orden, cod_letra
            FROM trabajadores
            WHERE id = :id AND activo = true
        """),
        {"id": trabajador_id}
    ).fetchone()

    if not row:
        raise HTTPException(404, "Trabajador no encontrado")

    dni = row.dni
    num_orden = row.num_orden
    cod_letra = row.cod_letra

    # --------------------------------------------------
    # Definir texto visible en la etiqueta
    # --------------------------------------------------
    if visible == num_orden:
        texto_visible = num_orden
    elif visible == cod_letra:
        texto_visible = cod_letra
    else:
        texto_visible = num_orden  # default seguro

    # --------------------------------------------------
    # Generar token QR
    # --------------------------------------------------
    token = generar_token(producto)

    # --------------------------------------------------
    # Registrar emisión (auditoría / destajo)
    # --------------------------------------------------
    qr = QREmitido(
        token=token,
        dni_trabajador=dni,
        nn=texto_visible,
        producto=producto,
        impreso_por=usuario
    )
    db.add(qr)
    db.commit()

    # --------------------------------------------------
    # Generar imagen QR
    # --------------------------------------------------
    img = generar_qr_memoria(
        token=token,
        dni=dni,
        numord=texto_visible,
        producto=producto
    )

    return StreamingResponse(
        img,
        media_type="image/png"
    )

@router.post("/print-batch")
def print_batch(data: dict):
    # --------------------------------------------------
    # Usuario activo (auditoría)
    # --------------------------------------------------
    usuario = get_usuario()
    if not usuario:
        raise HTTPException(401, "Usuario no definido")

    # --------------------------------------------------
    # Validaciones de entrada
    # --------------------------------------------------
    for campo in ("trabajador_id", "producto", "cantidad"):
        if campo not in data:
            raise HTTPException(400, f"{campo} es requerido")

    trabajador_id = int(data["trabajador_id"])
    producto = data.get("producto", "UVA")
    cantidad = int(data["cantidad"])
    visible = data.get("visible")

    if cantidad <= 0 or cantidad > 500:
        raise HTTPException(
            400,
            "Cantidad inválida (1 a 500 permitidas)"
        )

    db = SessionLocal()

    # --------------------------------------------------
    # Obtener trabajador real desde BD
    # --------------------------------------------------
    row = db.execute(
        text("""
            SELECT dni, num_orden, cod_letra
            FROM trabajadores
            WHERE id = :id AND activo = true
        """),
        {"id": trabajador_id}
    ).fetchone()

    if not row:
        raise HTTPException(404, "Trabajador no encontrado")

    dni = row.dni
    num_orden = row.num_orden
    cod_letra = row.cod_letra

    # --------------------------------------------------
    # Determinar texto visible
    # --------------------------------------------------
    if visible == cod_letra:
        texto_visible = cod_letra
    else:
        texto_visible = num_orden

    # --------------------------------------------------
    # Bloqueo: evitar impresión duplicada pendiente
    # --------------------------------------------------
    pendientes = db.execute(
        text("""
            SELECT COUNT(*)
            FROM qr_emitidos
            WHERE dni_trabajador = :dni
            AND producto = :producto
            AND estado = 'CREADO'
        """),
        {"dni": dni, "producto": producto}
    ).scalar()

    if pendientes > 0:
        raise HTTPException(
            409,
            "Existen etiquetas pendientes de uso para este trabajador"
        )

    # --------------------------------------------------
    # Generar etiquetas únicas
    # --------------------------------------------------
    etiquetas = []

    for _ in range(cantidad):
        token = generar_token(producto)

        qr = QREmitido(
            token=token,
            dni_trabajador=dni,
            nn=texto_visible,
            producto=producto,
            estado="CREADO",
            impreso_por=usuario,
            fecha_impresion=datetime.utcnow()
        )

        db.add(qr)
        etiquetas.append(qr)

    db.commit()

    # --------------------------------------------------
    # Generar ZIP de imágenes
    # --------------------------------------------------
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for idx, qr in enumerate(etiquetas, start=1):
            img = generar_qr_memoria(
                token=qr.token,
                dni=qr.dni_trabajador,
                numord=qr.nn,
                producto=qr.producto
            )

            nombre = f"etiqueta_{idx:03d}.png"
            zipf.writestr(nombre, img.getvalue())

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=etiquetas_qr.zip"
        }
    )