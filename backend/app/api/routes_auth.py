from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.passwords import verify_password
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.core.auth_dep import get_current_user
from jose import JWTError

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
    refresh_token = create_refresh_token({"sub": usuario_db, "rol": rol_db})

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "usuario": usuario_db,
        "rol": rol_db
    }


@router.post("/refresh")
def refresh(data: dict):
    refresh_token = (data.get("refresh_token") or "").strip()
    if not refresh_token:
        raise HTTPException(400, "Refresh token requerido")

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(401, "Refresh token inválido o expirado")
    except Exception:
        raise HTTPException(401, "Refresh token inválido")

    if payload.get("typ") != "refresh":
        raise HTTPException(401, "Tipo de token inválido")

    usuario = (payload.get("sub") or "").strip()
    if not usuario:
        raise HTTPException(401, "Refresh token inválido")

    with SessionLocal() as db:
        row = db.execute(
            text("""
                SELECT usuario, rol
                FROM usuarios
                WHERE usuario = :u AND activo = true
            """),
            {"u": usuario},
        ).mappings().first()

        if not row:
            raise HTTPException(401, "Usuario no válido")

        rol_db = (row.get("rol") or "").upper()

    new_access = create_access_token({"sub": usuario, "rol": rol_db})
    new_refresh = create_refresh_token({"sub": usuario, "rol": rol_db})

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "usuario": usuario,
        "rol": rol_db,
    }

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
