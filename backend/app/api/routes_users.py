from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.base import SessionLocal
from app.core.session import get_rol
from app.core.passwords import hash_password

router = APIRouter(prefix="/admin")

@router.post("/usuarios")
def crear_usuario(data: dict):
    if get_rol() != "ROOT":
        raise HTTPException(403, "Solo ROOT puede crear usuarios")

    usuario = data.get("usuario")
    nombre = data.get("nombre")
    password = data.get("password")
    rol = data.get("rol")

    if not usuario or not nombre or not password:
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
