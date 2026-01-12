from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.passwords import verify_password
from app.core.jwt import create_access_token
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/auth")

@router.post("/login")
def login(data: dict):
    usuario = (data.get("usuario") or "").strip()
    password = (data.get("password") or "").strip()

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
        ).mappings().first()

        if not row or not row.get("password_hash"):
            raise HTTPException(401, "Usuario no válido")

        if not verify_password(password, row["password_hash"]):
            raise HTTPException(401, "Contraseña incorrecta")

        usuario_db = row["usuario"]
        rol_db = (row.get("rol") or "").upper()

    token = create_access_token({"sub": usuario_db, "rol": rol_db})

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": usuario_db,
        "rol": rol_db
    }

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
