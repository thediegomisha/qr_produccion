from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.assignments import next_num_orden, next_cod_letra
from app.core.session import get_rol


router = APIRouter()

# ==================================================
# LISTAR TRABAJADORES
# ==================================================
@router.get("/")
def listar_trabajadores(activos: bool = True):
    """
    Lista trabajadores.
    - activos=true  → solo activos
    - activos=false → todos """
    with SessionLocal() as db:
        query = """ SELECT
                id,
                dni,
                nombre,
                apellido_paterno,
                apellido_materno,
                rol,
                num_orden,
                cod_letra,
                activo,
                creado_en
            FROM trabajadores """

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
    
    if get_rol() not in ("ROOT", "SUPERVISOR"):
        raise HTTPException(403, "Permiso insuficiente")

    dni = (data.get("dni") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    apellido_paterno = (data.get("apellido_paterno") or "").strip()
    apellido_materno = (data.get("apellido_materno") or "").strip()
    rol = (data.get("rol") or "").strip()

    # -------------------------------
    # Validaciones
    # -------------------------------
    if len(dni) != 8 or not dni.isdigit():
        raise HTTPException(status_code=400, detail="DNI inválido (8 dígitos)")

    if not nombre:
        raise HTTPException(400, "Nombres obligatorios")

    if not apellido_paterno:
        raise HTTPException(400, "Apellido paterno obligatorio")


    if rol not in ("EMPACADORA", "SELECCIONADOR"):
        raise HTTPException(
            status_code=400,
            detail="Nombre y apellido paterno son obligatorios"
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
            text(""" INSERT INTO trabajadores (
                    dni,
                    nombre,
                    apellido_paterno,
                    apellido_materno,
                    rol,
                    num_orden,
                    cod_letra,
                    activo )
                VALUES (
                    :dni,
                    :nombre,
                    :ap_paterno,
                    :ap_materno,
                    :rol,
                    :num_orden,
                    :cod_letra,
                    true ) """),
            {
                "dni": dni,
                "nombre": nombre,
                "ap_paterno": apellido_paterno,
                "ap_materno": apellido_materno,
                "rol": rol,
                "num_orden": num_orden,
                "cod_letra": cod_letra
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
# ACTUALIZAR TRABAJADOR
# ==================================================
@router.put("/{trabajador_id}")
def actualizar_trabajador(trabajador_id: int, data: dict):

    if get_rol() not in ("ROOT", "SUPERVISOR"):
        raise HTTPException(403, "Permiso insuficiente")

    dni = (data.get("dni") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    apellido_paterno = (data.get("apellido_paterno") or "").strip()
    apellido_materno = (data.get("apellido_materno") or "").strip()
    rol = (data.get("rol") or "").strip()

    # -------------------------------
    # Validaciones
    # -------------------------------
    if len(dni) != 8 or not dni.isdigit():
        raise HTTPException(400, "DNI inválido (8 dígitos)")

    if not nombre:
        raise HTTPException(400, "Nombre obligatorio")

    if not apellido_paterno:
        raise HTTPException(400, "Apellido paterno obligatorio")

    if rol not in ("EMPACADORA", "SELECCIONADOR"):
        raise HTTPException(400, "Rol inválido")

    with SessionLocal() as db:

        # Verificar existencia
        existe = db.execute(
            text("SELECT id FROM trabajadores WHERE id = :id"),
            {"id": trabajador_id}
        ).first()

        if not existe:
            raise HTTPException(404, "Trabajador no encontrado")

        # Validar DNI duplicado (excluyendo al mismo trabajador)
        dni_duplicado = db.execute(
            text("""
                SELECT 1 FROM trabajadores
                WHERE dni = :dni AND id != :id
            """),
            {"dni": dni, "id": trabajador_id}
        ).first()

        if dni_duplicado:
            raise HTTPException(409, "DNI ya registrado por otro trabajador")

        # Actualización
        db.execute(
            text("""
                UPDATE trabajadores
                SET
                    dni = :dni,
                    nombre = :nombre,
                    apellido_paterno = :ap_paterno,
                    apellido_materno = :ap_materno,
                    rol = :rol
                WHERE id = :id
            """),
            {
                "dni": dni,
                "nombre": nombre,
                "ap_paterno": apellido_paterno,
                "ap_materno": apellido_materno,
                "rol": rol,
                "id": trabajador_id
            }
        )

        db.commit()

    return {"ok": True}

# ==================================================
# OBTENER TRABAJADOR POR ID
# ==================================================
@router.get("/{trabajador_id}")
def obtener_trabajador(trabajador_id: int):
    with SessionLocal() as db:
        row = db.execute(
            text("""
                SELECT
                    id,
                    dni,
                    nombre,
                    apellido_paterno,
                    apellido_materno,
                    rol,
                    num_orden,
                    cod_letra,
                    activo,
                    creado_en
                FROM trabajadores
                WHERE id = :id
            """),
            {"id": trabajador_id}
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Trabajador no encontrado"
            )

        return dict(row)


# ==================================================
# DESACTIVAR TRABAJADOR (SOFT DELETE)
# ==================================================
@router.delete("/{trabajador_id}")
def desactivar_trabajador(trabajador_id: int):
    with SessionLocal() as db:
        result = db.execute(
            text(""" UPDATE trabajadores
                SET activo = false
                WHERE id = :id """),
            {"id": trabajador_id}
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Trabajador no encontrado"
            )

        db.commit()

    return {"ok": True}
