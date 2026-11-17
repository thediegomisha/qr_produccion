from fastapi import APIRouter, HTTPException, Depends
from app.core.auth_dep import get_current_user
from app.services.reniec import consultar_dni

router = APIRouter(prefix="/reniec", tags=["RENIEC"], dependencies=[Depends(get_current_user)])

@router.get("/dni/{dni}")
def validar_dni(dni: str):
    if not dni.isdigit() or len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI inválido")

    data = consultar_dni(dni)
    if not data:
        raise HTTPException(status_code=404, detail="DNI no encontrado")

    return data
