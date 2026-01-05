from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.passwords import verify_password
from app.core.jwt import create_access_token

router = APIRouter(prefix="/auth")

@router.post("/login") 
def login(data: dict):
    usuario = data.get("usuario")
    password = data.get("password")

    if not usuario or not password:
        raise HTTPException(400, "Credenciales incompletas")

    with SessionLocal() as db:
        row = db.execute(
            text("""
                SELECT usuario, password_hash, rol
                FROM usuarios
                WHERE usuario = :u AND activo = true
            """),
            {"u": usuario}
        ).fetchone()

        if not row or not row.password_hash:
            raise HTTPException(401, "Usuario no válido")

        if not verify_password(password, row.password_hash):
            raise HTTPException(401, "Contraseña incorrecta")

    token = create_access_token({"sub": row.usuario, "rol": row.rol})

    return {"access_token": token, "token_type": "bearer", "usuario": row.usuario, "rol": row.rol}
