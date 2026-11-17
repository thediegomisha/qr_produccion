from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.passwords import verify_password
from app.core.jwt import create_access_token, create_refresh_token, decode_token, credential_version
from app.core.rate_limit import auth_rate_limit
from app.core.auth_dep import get_current_user
from jose import JWTError

router = APIRouter(prefix="/auth")

@router.post("/login", dependencies=[Depends(auth_rate_limit)])
def login(data: dict):
    usuario = (data.get("usuario") or "").strip()
    password = (data.get("password") or "").strip()

    if not usuario or not password:
        raise HTTPException(400, "Credenciales incompletas")

    with SessionLocal() as db:
        row = db.execute(
            text("""
                SELECT usuario, nombre, password_hash, rol
                FROM usuarios
                WHERE usuario = :u AND activo = true
            """),
            {"u": usuario}
        ).mappings().first()

        if not row or not row.get("password_hash"):
            raise HTTPException(401, "Credenciales inválidas")

        if not verify_password(password, row["password_hash"]):
            raise HTTPException(401, "Credenciales inválidas")

        usuario_db = row["usuario"]
        nombre_db = (row.get("nombre") or "").strip()
        rol_db = (row.get("rol") or "").upper()
        auth_version = credential_version(row["password_hash"])

    token = create_access_token({"sub": usuario_db, "rol": rol_db, "cv": auth_version})
    refresh_token = create_refresh_token({"sub": usuario_db, "rol": rol_db, "cv": auth_version})

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "usuario": usuario_db,
        "nombre": nombre_db,
        "rol": rol_db
    }


@router.post("/refresh", dependencies=[Depends(auth_rate_limit)])
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
                SELECT usuario, nombre, rol, password_hash
                FROM usuarios
                WHERE usuario = :u AND activo = true
            """),
            {"u": usuario},
        ).mappings().first()

        if not row:
            raise HTTPException(401, "Usuario no válido")
        if payload.get("cv") != credential_version(row.get("password_hash") or ""):
            raise HTTPException(401, "Sesión revocada; vuelva a iniciar sesión")

        rol_db = (row.get("rol") or "").upper()
        nombre_db = (row.get("nombre") or "").strip()

    new_access = create_access_token({"sub": usuario, "rol": rol_db, "cv": payload["cv"]})
    new_refresh = create_refresh_token({"sub": usuario, "rol": rol_db, "cv": payload["cv"]})

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "usuario": usuario,
        "nombre": nombre_db,
        "rol": rol_db,
    }

@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    with SessionLocal() as db:
        row = db.execute(text("""
            SELECT usuario, nombre, rol FROM usuarios
            WHERE usuario = :u AND activo = true
        """), {"u": user["usuario"]}).mappings().first()
    if not row:
        raise HTTPException(401, "Usuario no válido")
    return {
        "usuario": row["usuario"],
        "nombre": (row.get("nombre") or "").strip(),
        "rol": (row.get("rol") or "").upper(),
    }
