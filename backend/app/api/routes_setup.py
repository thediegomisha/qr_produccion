import os
import secrets
from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.passwords import hash_password

# ======================================================
# ROUTER SETUP (BOOTSTRAP DEL SISTEMA)
# ======================================================
# ⚠️ IMPORTANTE:
# - AQUÍ SÍ VA EL PREFIJO /setup
# - EN main.py NO DEBE REPETIRSE
# ======================================================

def require_bootstrap(x_bootstrap_token: str = Header("")):
    expected = os.getenv("BOOTSTRAP_TOKEN", "")
    if len(expected) < 32 or not secrets.compare_digest(x_bootstrap_token, expected):
        raise HTTPException(403, "Bootstrap no autorizado")


router = APIRouter(prefix="/setup", tags=["Setup"], dependencies=[Depends(require_bootstrap)])


# ------------------------------------------------------
# VERIFICAR ESTADO DEL SISTEMA
# ------------------------------------------------------
@router.get("/status")
def status():
    """
    Devuelve si el sistema ya fue inicializado.
    initialized = True  → existe un ROOT activo
    initialized = False → no existe ROOT (bootstrap pendiente)
    """
    with SessionLocal() as db:
        root = db.execute(
            text(""" SELECT 1
                FROM usuarios
                WHERE rol = 'ROOT'
                AND activo = true LIMIT 1 """)
        ).first()

    return {"initialized": bool(root)}


# ------------------------------------------------------
# INICIALIZAR ROOT (SOLO UNA VEZ)
# ------------------------------------------------------
@router.post("/init-root")
def init_root(data: dict):
    """
    Crea el usuario ROOT inicial.
    Este endpoint SOLO puede ejecutarse una vez.
    """

    usuario = (data.get("usuario") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    password = (data.get("password") or "").strip()

    # -------------------------------
    # Validaciones
    # -------------------------------
    if not usuario or not nombre or not password:
        raise HTTPException(
            status_code=400,
            detail="usuario, nombre y password son obligatorios"
        )

    if len(password) < 12:
        raise HTTPException(
            status_code=400,
            detail="El password debe tener al menos 12 caracteres"
        )

    with SessionLocal() as db:
        # ¿Ya existe ROOT?
        existe = db.execute(
            text(""" SELECT 1
                FROM usuarios
                WHERE rol = 'ROOT' LIMIT 1 """)
        ).first()

        if existe:
            raise HTTPException(
                status_code=403,
                detail="El sistema ya fue inicializado"
            )

        # Crear ROOT
        db.execute(
            text(""" INSERT INTO usuarios (
                    usuario,
                    nombre,
                    rol,
                    password_hash,
                    activo )
                VALUES (
                    :usuario,
                    :nombre,
                    'ROOT',
                    :password_hash,
                    true ) """),
            {
                "usuario": usuario,
                "nombre": nombre,
                "password_hash": hash_password(password)
            }
        )

        db.commit()

    return {
        "ok": True,
        "mensaje": "Usuario ROOT creado correctamente"
    }
