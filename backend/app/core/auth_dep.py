from fastapi import Header, HTTPException
from jose import JWTError
from app.core.jwt import decode_token, credential_version
from app.db.base import SessionLocal
from sqlalchemy import text
import secrets

def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta Authorization Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    usuario = payload.get("sub")
    token_type = payload.get("typ")

    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido (sin sub)")

    if token_type != "access":
        raise HTTPException(status_code=401, detail="Token inválido para acceso")

    with SessionLocal() as db:
        account = db.execute(text("""
            SELECT rol, password_hash FROM usuarios
            WHERE usuario = :u AND activo = true
        """), {"u": usuario}).mappings().first()
    if not account or not secrets.compare_digest(
        str(payload.get("cv", "")), credential_version(account.get("password_hash") or "")
    ):
        raise HTTPException(401, "Sesión revocada; vuelva a iniciar sesión")
    return {"usuario": usuario, "rol": (account["rol"] or "").upper()}
