from fastapi import APIRouter, HTTPException
from sqlalchemy import text
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

    if rol not in ("SUPERVISOR", "OPERADOR"):
        raise HTTPException(400, "Rol inválido")

    with SessionLocal() as db:
        db.execute(
            text("""
                INSERT INTO usuarios (usuario, nombre, rol, password_hash, activo)
                VALUES (:u, :n, :r, :p, true)
            """),
            {
                "u": usuario,
                "n": nombre,
                "r": rol,
                "p": hash_password(password)
            }
        )
        db.commit()

    return {"ok": True}
