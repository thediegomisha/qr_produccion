from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.base import SessionLocal
from app.core.passwords import hash_password
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/admin")

@router.post("/usuarios")
def crear_usuario(data: dict, user: dict = Depends(get_current_user)):
    rol_actual = (user.get("rol") or "").upper()

    # ROOT y GERENCIA pueden administrar (casi igual)
    if rol_actual not in ("ROOT", "GERENCIA"):
        raise HTTPException(403, "Solo ROOT o GERENCIA puede crear usuarios")

    usuario = (data.get("usuario") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    password = (data.get("password") or "").strip()
    rol_nuevo = (data.get("rol") or "").strip().upper()

    if not usuario or not nombre or not password or not rol_nuevo:
        raise HTTPException(status_code=400, detail="Campos obligatorios incompletos")

    # Roles permitidos en el sistema
    ROLES_VALIDOS = ("ROOT", "GERENCIA", "SUPERVISOR", "OPERADOR")
    if rol_nuevo not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol inválido")

    # Regla: solo ROOT puede crear GERENCIA (y recomendado: solo ROOT crea ROOT)
    if rol_nuevo in ("GERENCIA", "ROOT") and rol_actual != "ROOT":
        raise HTTPException(403, "Solo ROOT puede crear usuarios GERENCIA o ROOT")

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
                    "rol": rol_nuevo
                }
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Usuario ya existe")

    return {"ok": True}
