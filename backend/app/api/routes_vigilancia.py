from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import text
from app.db.base import SessionLocal
from pydantic import BaseModel, Field
from datetime import date, datetime

import requests

from app.services.reniec import consultar_dni_fullname
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/vigilancia", tags=["vigilancia"])


# ======================================================
# Helpers
# ======================================================
def _only_digits(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def norm_persona_from_service(raw) -> tuple[str, str, str]:
    """
    Normaliza distintos formatos posibles del servicio externo (PeruDevs/RENIEC-like).

    Soporta:
    - {"estado": true, "resultado": {...}}
    - {...} directo
    - claves snake_case / camelCase
    - apellidos juntos en "apellidos" o "apellido"
    - fallback con "nombre_completo"
    """
    if isinstance(raw, dict):
        data = raw.get("resultado")
        if not isinstance(data, dict):
            data = raw
    else:
        data = {}

    nombres = (data.get("nombres") or data.get("nombre") or data.get("nombres_completos") or "").strip()

    ap_pat = (data.get("apellido_paterno") or data.get("apellidoPaterno") or data.get("ap_paterno") or "").strip()
    ap_mat = (data.get("apellido_materno") or data.get("apellidoMaterno") or data.get("ap_materno") or "").strip()

    apellidos = (data.get("apellidos") or data.get("apellido") or "").strip()
    if (not ap_pat and not ap_mat) and apellidos:
        partes = apellidos.split()
        if len(partes) == 1:
            ap_pat = partes[0]
        elif len(partes) >= 2:
            ap_pat = partes[0]
            ap_mat = " ".join(partes[1:])

    nombre_completo = (data.get("nombre_completo") or data.get("nombreCompleto") or "").strip()
    if nombre_completo and (not ap_pat or not ap_mat or not nombres):
        parts = nombre_completo.split()
        if len(parts) >= 3:
            ap_pat = ap_pat or parts[-2]
            ap_mat = ap_mat or parts[-1]
            nombres = nombres or " ".join(parts[:-2])

    return nombres, ap_pat, ap_mat


# ======================================================
# DTOs
# ======================================================
class PersonaOut(BaseModel):
    dni: str
    nombres: str = ""
    apellido_paterno: str = ""
    apellido_materno: str = ""
    found: bool = False
    offline: bool = False


class VisitaIn(BaseModel):
    dni: str = Field(..., pattern=r"^\d{8}$")
    tipo: str = Field(..., pattern=r"^(ENTRADA|SALIDA)$")
    nombres: str | None = None
    apellido_paterno: str | None = None
    apellido_materno: str | None = None


# ======================================================
# BD (reemplaza por tu acceso real)
# ======================================================
def db_get_persona(dni: str):
    sql = text("""
      SELECT nro_doc AS dni, nombres, apellido_paterno, apellido_materno
      FROM personas
      WHERE tipo_doc = 'DNI' AND nro_doc = :dni
      LIMIT 1
    """)
    with SessionLocal() as db:
        row = db.execute(sql, {"dni": dni}).mappings().first()
        return dict(row) if row else None



def db_upsert_persona(dni: str, nombres: str, apellido_paterno: str, apellido_materno: str, fuente: str = "RENIEC"):
    sql = text("""
      INSERT INTO personas (tipo_doc, nro_doc, nombres, apellido_paterno, apellido_materno, fuente, updated_at)
      VALUES ('DNI', :dni, :nombres, :ap_pat, :ap_mat, :fuente, now())
      ON CONFLICT (tipo_doc, nro_doc) DO UPDATE SET
        nombres = EXCLUDED.nombres,
        apellido_paterno = EXCLUDED.apellido_paterno,
        apellido_materno = EXCLUDED.apellido_materno,
        fuente = EXCLUDED.fuente,
        updated_at = now()
    """)
    with SessionLocal() as db:
        db.execute(sql, {
            "dni": dni,
            "nombres": nombres,
            "ap_pat": apellido_paterno,
            "ap_mat": apellido_materno,
            "fuente": fuente
        })
        db.commit()

def db_insert_visita(
    dni: str,
    tipo: str,
    nombres: str,
    apellido_paterno: str,
    apellido_materno: str,
    usuario: str | None,
):
    sql = text("""
      INSERT INTO vigilancia_visitas
        (dni, tipo, nombres, apellido_paterno, apellido_materno, usuario)
      VALUES
        (:dni, :tipo, :nombres, :ap_pat, :ap_mat, :usuario)
      RETURNING creado_en
    """)
    with SessionLocal() as db:
        creado_en = db.execute(sql, {
            "dni": dni,
            "tipo": tipo,
            "nombres": nombres,
            "ap_pat": apellido_paterno,
            "ap_mat": apellido_materno,
            "usuario": usuario
        }).scalar_one()
        db.commit()

    return {
        "creado_en": creado_en.isoformat(timespec="seconds") if hasattr(creado_en, "isoformat") else str(creado_en),
        "tipo": tipo,
        "dni": dni,
        "nombres": nombres,
        "apellido_paterno": apellido_paterno,
        "apellido_materno": apellido_materno,
        "usuario": usuario,
    }



def db_list_visitas(fecha: date, limit: int):
    sql = text("""
      SELECT v.creado_en, v.tipo, v.dni, v.usuario,
             p.nombres, p.apellido_paterno, p.apellido_materno
      FROM vigilancia_visitas v
      LEFT JOIN personas p
        ON p.tipo_doc = 'DNI' AND p.nro_doc = v.dni
      WHERE v.creado_en::date = :fecha
      ORDER BY v.creado_en DESC
      LIMIT :limit
    """)
    with SessionLocal() as db:
        rows = db.execute(sql, {"fecha": fecha, "limit": limit}).mappings().all()

    return [dict(r) for r in rows]



# ======================================================
# 1b) Preview persona (MISMA LOGICA pero por query param)
#     GET /vigilancia/persona/?dni=XXXXXXXX
# ======================================================
@router.get("/persona/", response_model=PersonaOut)
def get_persona_query(dni: str = Query(...), user=Depends(get_current_user)):
    dni = _only_digits(dni)
    if len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI inválido")

    # 1) BD
    p = db_get_persona(dni)
    if p:
        return PersonaOut(
            dni=dni,
            nombres=p.get("nombres", ""),
            apellido_paterno=p.get("apellido_paterno", ""),
            apellido_materno=p.get("apellido_materno", ""),
            found=True,
            offline=False,
        )

    # 2) Servicio externo
    try:
        raw = consultar_dni_fullname(dni)
        if not raw:
            return PersonaOut(dni=dni, found=False, offline=False)

        nombres, ap_pat, ap_mat = norm_persona_from_service(raw)

        if not nombres and not ap_pat and not ap_mat:
            return PersonaOut(dni=dni, found=False, offline=False)

        db_upsert_persona(dni, nombres, ap_pat, ap_mat, fuente="RENIEC")

        return PersonaOut(
            dni=dni,
            nombres=nombres,
            apellido_paterno=ap_pat,
            apellido_materno=ap_mat,
            found=True,
            offline=False,
        )

    except requests.RequestException:
        return PersonaOut(dni=dni, found=False, offline=True)



# ======================================================
# 2) Registrar visita
# ======================================================
@router.post("/visita")
def post_visita(payload: VisitaIn, user=Depends(get_current_user)):
    usuario = user.get("usuario") or user.get("sub")
    dni = payload.dni

    # --- caso manual ---
    if payload.nombres and payload.apellido_paterno and payload.apellido_materno:
        nombres = payload.nombres.strip()
        ap_pat = payload.apellido_paterno.strip()
        ap_mat = payload.apellido_materno.strip()

        if not nombres or not ap_pat or not ap_mat:
            raise HTTPException(status_code=400, detail="Nombres/apellidos requeridos (manual).")

        db_upsert_persona(dni, nombres, ap_pat, ap_mat, fuente="MANUAL")
        return db_insert_visita(dni, payload.tipo, nombres, ap_pat, ap_mat, usuario=usuario)

    # --- caso automático ---
    p = db_get_persona(dni)
    if p:
        nombres = (p.get("nombres") or "").strip()
        ap_pat = (p.get("apellido_paterno") or "").strip()
        ap_mat = (p.get("apellido_materno") or "").strip()

        # si tu BD tiene parcial, fuerza consulta externa
        if not nombres or not ap_pat or not ap_mat:
            p = None

    if not p:
        try:
            raw = consultar_dni_fullname(dni)
        except requests.RequestException:
            # si el servicio externo cae, permite que el cliente registre manual
            raise HTTPException(status_code=503, detail="Servicio externo no disponible (offline).")

        if not raw:
            raise HTTPException(status_code=404, detail="No encontrado en BD ni en servicio externo")

        nombres, ap_pat, ap_mat = norm_persona_from_service(raw)

        if not nombres or not ap_pat or not ap_mat:
            raise HTTPException(status_code=502, detail="Servicio externo devolvió datos incompletos")

        db_upsert_persona(dni, nombres, ap_pat, ap_mat)

    return db_insert_visita(dni, payload.tipo, nombres, ap_pat, ap_mat, usuario=usuario)

# ======================================================
# 3) Listar visitas
# ======================================================
@router.get("/visitas")
def list_visitas(
    fecha: date = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=500),
):
    return {"items": db_list_visitas(fecha, limit)}
