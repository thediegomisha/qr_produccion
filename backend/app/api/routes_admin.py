from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.base import SessionLocal
from app.core.passwords import hash_password
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

ROLES_VALIDOS = ("ROOT", "GERENCIA", "SUPERVISOR", "OPERADOR", "AGENTE")


def _rol(user: dict) -> str:
    return (user.get("rol") or "").upper()


def _require_root_or_gerencia(user: dict):
    if _rol(user) not in ("ROOT", "GERENCIA"):
        raise HTTPException(403, "Solo ROOT o GERENCIA puede administrar usuarios")


def _gerencia_block_target(target_rol: str, user: dict):
    # GERENCIA no puede administrar ROOT/GERENCIA
    if _rol(user) == "GERENCIA" and target_rol in ("ROOT", "GERENCIA"):
        raise HTTPException(403, "GERENCIA no puede administrar usuarios ROOT o GERENCIA")


def _gerencia_block_assign(new_rol: str, user: dict):
    # GERENCIA no puede crear/ascender a ROOT/GERENCIA
    if _rol(user) == "GERENCIA" and new_rol in ("ROOT", "GERENCIA"):
        raise HTTPException(403, "GERENCIA no puede asignar rol ROOT o GERENCIA")


# ======================================================
# LISTAR USUARIOS
# ======================================================
@router.get("/usuarios")
def listar_usuarios(user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    with SessionLocal() as db:
        rows = db.execute(text("""
            SELECT usuario, nombre, rol, activo, creado_en
            FROM usuarios
            ORDER BY usuario
        """)).mappings().all()

    return {"items": list(rows)}


# ======================================================
# CREAR USUARIO
# - ROOT puede crear cualquiera
# - GERENCIA puede crear SUPERVISOR/OPERADOR (NO GERENCIA/ROOT)
# ======================================================
@router.post("/usuarios")
def crear_usuario(data: dict, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    usuario = (data.get("usuario") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    password = (data.get("password") or "").strip()
    rol_nuevo = (data.get("rol") or "").strip().upper()

    if not usuario or not nombre or not password or not rol_nuevo:
        raise HTTPException(400, "Campos obligatorios incompletos")

    if rol_nuevo not in ROLES_VALIDOS:
        raise HTTPException(400, "Rol inválido")

    _gerencia_block_assign(rol_nuevo, user)

    password_hash = hash_password(password)

    with SessionLocal() as db:
        try:
            db.execute(text("""
                INSERT INTO usuarios (usuario, nombre, password_hash, rol, activo)
                VALUES (:usuario, :nombre, :ph, :rol, true)
            """), {"usuario": usuario, "nombre": nombre, "ph": password_hash, "rol": rol_nuevo})
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Usuario ya existe")

    return {"ok": True}


# ======================================================
# EDITAR USUARIO (nombre, rol, activo)
# - GERENCIA no toca ROOT/GERENCIA
# - GERENCIA no asigna ROOT/GERENCIA
# ======================================================
@router.put("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: str, data: dict, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    nuevo_nombre = data.get("nombre")
    nuevo_rol = data.get("rol")
    nuevo_activo = data.get("activo")

    if nuevo_nombre is not None:
        nuevo_nombre = (str(nuevo_nombre) or "").strip()
        if not nuevo_nombre:
            raise HTTPException(400, "Nombre no puede ser vacío")

    if nuevo_rol is not None:
        nuevo_rol = (str(nuevo_rol) or "").strip().upper()
        if nuevo_rol not in ROLES_VALIDOS:
            raise HTTPException(400, "Rol inválido")
        _gerencia_block_assign(nuevo_rol, user)

    if nuevo_activo is not None:
        nuevo_activo = bool(nuevo_activo)

    with SessionLocal() as db:
        target = db.execute(
            text("SELECT usuario, rol FROM usuarios WHERE usuario = :u"),
            {"u": usuario_id}
        ).mappings().first()

        if not target:
            raise HTTPException(404, "Usuario no encontrado")

        target_rol = (target.get("rol") or "").upper()
        _gerencia_block_target(target_rol, user)

        sets = []
        params = {"u": usuario_id}

        if nuevo_nombre is not None:
            sets.append("nombre = :nombre")
            params["nombre"] = nuevo_nombre
        if nuevo_rol is not None:
            sets.append("rol = :rol")
            params["rol"] = nuevo_rol
        if nuevo_activo is not None:
            sets.append("activo = :activo")
            params["activo"] = nuevo_activo

        if not sets:
            raise HTTPException(400, "No hay campos para actualizar")

        db.execute(text(f"UPDATE usuarios SET {', '.join(sets)} WHERE usuario = :u"), params)
        db.commit()

    return {"ok": True}


# ======================================================
# CAMBIAR PASSWORD
# - GERENCIA no cambia password de ROOT/GERENCIA
# ======================================================
@router.put("/usuarios/{usuario_id}/password")
def cambiar_password(usuario_id: str, data: dict, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    new_password = (data.get("password") or "").strip()
    if not new_password:
        raise HTTPException(400, "Password obligatorio")
    if len(new_password) < 6:
        raise HTTPException(400, "Password muy corto (mínimo 6)")

    with SessionLocal() as db:
        target = db.execute(
            text("SELECT usuario, rol FROM usuarios WHERE usuario = :u"),
            {"u": usuario_id}
        ).mappings().first()

        if not target:
            raise HTTPException(404, "Usuario no encontrado")

        target_rol = (target.get("rol") or "").upper()
        _gerencia_block_target(target_rol, user)

        db.execute(text("""
            UPDATE usuarios
            SET password_hash = :ph
            WHERE usuario = :u
        """), {"ph": hash_password(new_password), "u": usuario_id})
        db.commit()

    return {"ok": True}
