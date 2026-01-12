from fastapi import Header, HTTPException
from jose import JWTError
from app.core.jwt import decode_token

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
    rol = (payload.get("rol") or "").upper()

    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido (sin sub)")

    return {"usuario": usuario, "rol": rol}
