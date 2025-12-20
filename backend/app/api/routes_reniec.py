from fastapi import APIRouter, HTTPException
from app.services.reniec import consultar_dni

router = APIRouter(prefix="/reniec", tags=["RENIEC"])

@router.get("/dni/{dni}")
def validar_dni(dni: str):
    if not dni.isdigit() or len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI inválido")

    data = consultar_dni(dni)
    if not data:
        raise HTTPException(status_code=404, detail="DNI no encontrado")

    return data
