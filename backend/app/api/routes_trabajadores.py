from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.assignments import next_num_orden, next_cod_letra

router = APIRouter()

# ==================================================
# LISTAR TRABAJADORES
# ==================================================
@router.get("/")
def listar_trabajadores(activos: bool = True):
    """
    Lista trabajadores.
    - activos=true  → solo activos
    - activos=false → todos
    """
    with SessionLocal() as db:
        query = """
            SELECT
                id,
                dni,
                nombre,
                rol,
                num_orden,
                cod_letra,
                activo,
                creado_en
            FROM trabajadores
        """

        if activos:
            query += " WHERE activo = true"

        query += " ORDER BY nombre"

        rows = db.execute(text(query)).mappings().all()
        return list(rows)


# ==================================================
# CREAR TRABAJADOR
# ==================================================
@router.post("/")
def crear_trabajador(data: dict):
    dni = (data.get("dni") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    rol = (data.get("rol") or "").strip()

    # -------------------------------
    # Validaciones
    # -------------------------------
    if len(dni) != 8 or not dni.isdigit():
        raise HTTPException(status_code=400, detail="DNI inválido (8 dígitos)")

    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre obligatorio")

    if rol not in ("EMPACADORA", "SELECCIONADOR"):
        raise HTTPException(
            status_code=400,
            detail="Rol inválido (EMPACADORA / SELECCIONADOR)"
        )

    with SessionLocal() as db:
        # DNI único
        existe = db.execute(
            text("SELECT 1 FROM trabajadores WHERE dni = :dni"),
            {"dni": dni}
        ).first()

        if existe:
            raise HTTPException(status_code=409, detail="DNI ya registrado")

        # Asignación automática
        num_orden = next_num_orden(db)
        cod_letra = next_cod_letra(db)

        db.execute(
            text("""
                INSERT INTO trabajadores
                (
                    dni,
                    nombre,
                    rol,
                    num_orden,
                    cod_letra,
                    activo
                )
                VALUES
                (
                    :dni,
                    :nombre,
                    :rol,
                    :num_orden,
                    :cod_letra,
                    true
                )
            """),
            {
                "dni": dni,
                "nombre": nombre,
                "rol": rol,
                "num_orden": num_orden,
                "cod_letra": cod_letra,
            }
        )

        db.commit()

    return {
        "ok": True,
        "dni": dni,
        "num_orden": num_orden,
        "cod_letra": cod_letra
    }


# ==================================================
# DESACTIVAR TRABAJADOR (SOFT DELETE)
# ==================================================
@router.delete("/{trabajador_id}")
def desactivar_trabajador(trabajador_id: int):
    with SessionLocal() as db:
        result = db.execute(
            text("""
                UPDATE trabajadores
                SET activo = false
                WHERE id = :id
            """),
            {"id": trabajador_id}
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Trabajador no encontrado"
            )

        db.commit()

    return {"ok": True}
