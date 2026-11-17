from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/impresoras", tags=["Impresoras"])


# --------------------------------------------------
# LISTAR impresoras activas
# --------------------------------------------------
@router.get("/")
def listar_impresoras(user=Depends(get_current_user)):
    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, nombre, marca, conexion, ip, puerto
                FROM impresoras
                WHERE activa = true
                ORDER BY nombre
            """)
        ).mappings().all()

        return list(rows)


# --------------------------------------------------
# CREAR impresora (solo ROOT)
# --------------------------------------------------
@router.post("/")
def crear_impresora(data: dict, user=Depends(get_current_user)):
    if user["rol"] != "ROOT":
        raise HTTPException(403, "Solo ROOT puede crear impresoras")

    nombre = data.get("nombre")
    marca = data.get("marca")
    conexion = data.get("conexion")
    ip = data.get("ip")
    puerto = data.get("puerto")

    if not nombre or not marca or not conexion:
        raise HTTPException(400, "Datos incompletos")

    with SessionLocal() as db:
        db.execute(
            text("""
                INSERT INTO impresoras
                (nombre, marca, conexion, ip, puerto, activa)
                VALUES
                (:n, :m, :c, :ip, :p, true)
            """),
            {
                "n": nombre,
                "m": marca,
                "c": conexion,
                "ip": ip,
                "p": puerto
            }
        )
        db.commit()

    return {"ok": True}
