from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user
from app.core.passwords import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/usuarios")
def crear_usuario(data: dict, user: dict = Depends(get_current_user)):
    rol_token = (user.get("rol") or "").upper()
    if rol_token != "ROOT":
        raise HTTPException(status_code=403, detail="Solo ROOT puede crear usuarios")

    usuario = (data.get("usuario") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    password = (data.get("password") or "")
    rol = (data.get("rol") or "").upper().strip()

    if not usuario or not nombre or not password or not rol:
        raise HTTPException(status_code=400, detail="Campos obligatorios incompletos")

    if rol not in ("ROOT", "SUPERVISOR", "OPERADOR"):
        raise HTTPException(status_code=400, detail="Rol inválido")

    password_hash = hash_password(password)

    with SessionLocal() as db:
        try:
            db.execute(
                text("""
                    INSERT INTO usuarios (usuario, nombre, password_hash, rol, activo)
                    VALUES (:usuario, :nombre, :password_hash, :rol, true)
                """),
                {
                    "usuario": usuario,
                    "nombre": nombre,
                    "password_hash": password_hash,
                    "rol": rol
                }
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Usuario ya existe")

    return {"ok": True}
