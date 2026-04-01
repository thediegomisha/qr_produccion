from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/productos", tags=["Productos"])


def _require_root_or_gerencia(user: dict):
    rol = (user.get("rol") or "").upper()
    if rol not in ("ROOT", "GERENCIA"):
        raise HTTPException(403, "Solo ROOT o GERENCIA puede administrar productos")


@router.get("")
def listar_productos(user: dict = Depends(get_current_user)):
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, nombre, activo, creado_en
                FROM productos
                WHERE activo = true
                ORDER BY nombre
                """
            )
        ).mappings().all()

    return list(rows)


@router.get("/all")
def listar_productos_admin(user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT id, nombre, activo, creado_en
                FROM productos
                ORDER BY nombre
                """
            )
        ).mappings().all()

    return list(rows)


@router.post("")
def crear_producto(data: dict, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(400, "Nombre requerido")

    with SessionLocal() as db:
        try:
            db.execute(
                text(
                    """
                    INSERT INTO productos (nombre, activo)
                    VALUES (:nombre, true)
                    """
                ),
                {"nombre": nombre},
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Producto ya existe")

    return {"ok": True}


@router.put("/{producto_id}")
def actualizar_producto(producto_id: int, data: dict, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    nombre = data.get("nombre")
    activo = data.get("activo")

    sets = []
    params: dict[str, object] = {"id": producto_id}

    if nombre is not None:
        nombre = (str(nombre) or "").strip()
        if not nombre:
            raise HTTPException(400, "Nombre no puede ser vacío")
        sets.append("nombre = :nombre")
        params["nombre"] = nombre

    if activo is not None:
        sets.append("activo = :activo")
        params["activo"] = bool(activo)

    if not sets:
        raise HTTPException(400, "No hay campos para actualizar")

    with SessionLocal() as db:
        try:
            result = db.execute(
                text(f"UPDATE productos SET {', '.join(sets)} WHERE id = :id"),
                params,
            )
            if result.rowcount == 0:
                raise HTTPException(404, "Producto no encontrado")
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Producto ya existe")

    return {"ok": True}


@router.delete("/{producto_id}")
def desactivar_producto(producto_id: int, user: dict = Depends(get_current_user)):
    _require_root_or_gerencia(user)

    with SessionLocal() as db:
        result = db.execute(
            text("UPDATE productos SET activo = false WHERE id = :id"),
            {"id": producto_id},
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Producto no encontrado")
        db.commit()

    return {"ok": True}
