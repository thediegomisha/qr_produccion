from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


# -------------------------
# Helpers
# -------------------------
def _to_dt(s: str) -> datetime:
    """
    Acepta ISO 8601: "2026-01-03T10:00:00Z" o con offset "+00:00"
    Retorna datetime timezone-aware en UTC
    """
    try:
        s = (s or "").strip()
        if not s:
            raise ValueError("vacío")

        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except Exception:
        raise HTTPException(400, f"Fecha inválida: {s}")


def _effective_user_filter(user, requested_user_id: Optional[str]) -> Optional[str]:
    """
    - ROOT/SUPERVISOR: pueden filtrar por cualquier user_id o dejar None (todos)
    - Otros: forzar a su propio usuario
    """
    rol = (user.get("rol") or "").upper()
    me = (user.get("usuario") or "").strip()

    if rol in ("ROOT", "SUPERVISOR"):
        ru = (requested_user_id or "").strip()
        return ru if ru else None

    return me if me else None


def _clean_optional(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s if s else None


def _resolve_lote(db, lote_codigo: Optional[str]) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Si lote_codigo viene, valida que exista y retorna (lote_id, codigo, estado).
    Si no viene, retorna (None, None, None) (sin filtro por lote).
    """
    codigo = _clean_optional(lote_codigo)
    if not codigo:
        return None, None, None

    q = text("""
        SELECT id, codigo, estado
        FROM lotes
        WHERE TRIM(UPPER(codigo)) = TRIM(UPPER(:codigo))
        LIMIT 1;
    """)
    row = db.execute(q, {"codigo": codigo}).mappings().first()

    if not row:
        raise HTTPException(404, f"Lote no existe: {codigo}")

    return int(row["id"]), row.get("codigo"), row.get("estado")


# -------------------------
# Reporte: DNI Summary (totales + tabla por DNI) - POR LOTE
# -------------------------
@router.get("/dni-summary")
def dni_summary(
    date_from: str = Query(..., description="ISO 8601, ej: 2026-01-03T00:00:00Z"),
    date_to: str = Query(..., description="ISO 8601, ej: 2026-01-04T00:00:00Z"),
    producto: Optional[str] = Query(None, description="Ej: UVA"),
    scanned_by: Optional[str] = Query(None, description="user_id que escaneó (solo ROOT/SUPERVISOR)"),
    lote_codigo: Optional[str] = Query(None, description="Código de lote, ej: 1234-2026"),
    user=Depends(get_current_user),
):

    dt_from = _to_dt(date_from)
    dt_to = _to_dt(date_to)
    if dt_to <= dt_from:
        raise HTTPException(400, "date_to debe ser mayor a date_from")

    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)
    lote_codigo = _clean_optional(lote_codigo)

    totals_sql = text("""
    SELECT
      COUNT(*) AS total_lecturas,
      COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$') AS emp_lecturas,
      COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$') AS sel_lecturas
    FROM scan_events se
    LEFT JOIN lotes l ON l.id = se.lote_id
    WHERE se.scanned_at >= :dt_from
      AND se.scanned_at <  :dt_to
      AND se.raw IS NOT NULL
      AND (se.raw->>'id') IS NOT NULL
      AND (:producto IS NULL OR se.raw->>'p' = :producto)
      AND (:scanned_by IS NULL OR se.user_id = :scanned_by)
      AND (:lote_id IS NULL OR se.lote_id = :lote_id)
    ;
""")


    rows_sql = text("""
        SELECT
        se.dni,
        COALESCE(
            NULLIF(
            TRIM(
                t.apellido_paterno || ' ' ||
                COALESCE(t.apellido_materno, '') || ' ' ||
                COALESCE(t.nombre, '')
            ),
            ''
            ),
            'SIN REGISTRO'
        ) AS persona,
        COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$') AS empacador,
        COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$') AS seleccionador,
        COUNT(*) AS total
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        LEFT JOIN trabajadores t
        ON TRIM(t.dni) = TRIM(se.dni)
        AND t.activo = true
        WHERE se.scanned_at >= :dt_from
        AND se.scanned_at <  :dt_to
        AND se.raw IS NOT NULL
        AND (se.raw->>'id') IS NOT NULL
        AND (:producto IS NULL OR se.raw->>'p' = :producto)
        AND (:scanned_by IS NULL OR se.user_id = :scanned_by)
        AND (:lote_id IS NULL OR se.lote_id = :lote_id)
        GROUP BY se.dni, persona
        ORDER BY total DESC;
    """)



    with SessionLocal() as db:
        lote_id, lote_codigo_db, lote_estado = _resolve_lote(db, lote_codigo)

        params = {
            "dt_from": dt_from,
            "dt_to": dt_to,
            "producto": producto,
            "scanned_by": scanned_by_eff,
            "lote_id": lote_id,
        }


        totals = db.execute(totals_sql, params).mappings().first() or {}
        rows = db.execute(rows_sql, params).mappings().all()

    return {
        "date_from": dt_from.isoformat().replace("+00:00", "Z"),
        "date_to": dt_to.isoformat().replace("+00:00", "Z"),
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "lote_codigo": lote_codigo,
        "totals": dict(totals),
        "rows": [dict(r) for r in rows],
    }



# -------------------------
# Reporte: resumen por operador (user_id) - POR LOTE
# -------------------------
@router.get("/operator-summary")
def operator_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    producto: Optional[str] = Query(None),
    scanned_by: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    dt_from = _to_dt(date_from)
    dt_to = _to_dt(date_to)
    if dt_to <= dt_from:
        raise HTTPException(400, "date_to debe ser mayor a date_from")

    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)
    lote_codigo = _clean_optional(lote_codigo)

    sql = text("""
        SELECT
        se.user_id,
        COUNT(*)::int AS total,
        COUNT(DISTINCT se.dni)::int AS dnis_distintos,
        MAX(se.scanned_at) AS ultima_lectura
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        WHERE se.scanned_at >= :dt_from
        AND se.scanned_at <  :dt_to
        AND (:producto IS NULL OR se.raw->>'p' = :producto)
        AND (:scanned_by IS NULL OR se.user_id = :scanned_by)
        AND (:lote_id IS NULL OR se.lote_id = :lote_id)
        GROUP BY se.user_id
        ORDER BY total DESC, ultima_lectura DESC;
    """)


    with SessionLocal() as db:
        lote_id, lote_codigo_db, lote_estado = _resolve_lote(db, lote_codigo)
        rows = db.execute(sql, {
            "dt_from": dt_from,
            "dt_to": dt_to,
            "producto": producto,
            "scanned_by": scanned_by_eff,
            "lote_id": lote_id,
        }).mappings().all()


    return {
        "date_from": dt_from.isoformat().replace("+00:00", "Z"),
        "date_to": dt_to.isoformat().replace("+00:00", "Z"),
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "lote_codigo": lote_codigo,
        "rows": [dict(r) for r in rows],
    }
