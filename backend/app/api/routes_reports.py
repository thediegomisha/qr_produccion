from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from datetime import datetime, timezone
from typing import Optional

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


# -------------------------
# Reporte: DNI Summary (totales + tabla por DNI)
# -------------------------
@router.get("/dni-summary")
def dni_summary(
    date_from: str = Query(..., description="ISO 8601, ej: 2026-01-03T00:00:00Z"),
    date_to: str = Query(..., description="ISO 8601, ej: 2026-01-04T00:00:00Z"),
    producto: Optional[str] = Query(None, description="Ej: UVA"),
    scanned_by: Optional[str] = Query(None, description="user_id que escaneó (solo ROOT/SUPERVISOR)"),
    user=Depends(get_current_user),
):
    dt_from = _to_dt(date_from)
    dt_to = _to_dt(date_to)
    if dt_to <= dt_from:
        raise HTTPException(400, "date_to debe ser mayor a date_from")

    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)

    # ✅ Totales sin IDs únicos
    totals_sql = text("""
        SELECT
          COUNT(*) AS total_lecturas,
          COUNT(*) FILTER (WHERE (raw->>'id') ~ '^[0-9]+$') AS emp_lecturas,
          COUNT(*) FILTER (WHERE (raw->>'id') ~ '^[A-Za-z]+$') AS sel_lecturas
        FROM scan_events
        WHERE scanned_at >= :dt_from
          AND scanned_at <  :dt_to
          AND raw IS NOT NULL
          AND (raw->>'id') IS NOT NULL
          AND (:producto IS NULL OR raw->>'p' = :producto)
          AND (:scanned_by IS NULL OR user_id = :scanned_by)
          -- OPCIONAL: solo DNIs válidos
          -- AND TRIM(dni) ~ '^[0-9]{8}$'
        ;
    """)

    # ✅ Tabla por DNI + persona (JOIN con trabajadores)
    # ✅ FIX: usa :dt_from / :dt_to (no :date_from/:date_to)
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
        LEFT JOIN trabajadores t
          ON TRIM(t.dni) = TRIM(se.dni)
         AND t.activo = true
        WHERE se.scanned_at >= :dt_from
          AND se.scanned_at <  :dt_to
          AND se.raw IS NOT NULL
          AND (se.raw->>'id') IS NOT NULL
          AND (:producto IS NULL OR se.raw->>'p' = :producto)
          AND (:scanned_by IS NULL OR se.user_id = :scanned_by)
          -- OPCIONAL: solo DNIs válidos
          -- AND TRIM(se.dni) ~ '^[0-9]{8}$'
        GROUP BY se.dni, persona
        ORDER BY total DESC;
    """)

    params = {
        "dt_from": dt_from,
        "dt_to": dt_to,
        "producto": producto,
        "scanned_by": scanned_by_eff,
    }

    with SessionLocal() as db:
        totals = db.execute(totals_sql, params).mappings().first() or {}
        rows = db.execute(rows_sql, params).mappings().all()

    return {
        "date_from": dt_from.isoformat().replace("+00:00", "Z"),
        "date_to": dt_to.isoformat().replace("+00:00", "Z"),
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "totals": dict(totals),
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Reporte: resumen por operador (user_id)
# -------------------------
@router.get("/operator-summary")
def operator_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    producto: Optional[str] = Query(None),
    scanned_by: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    dt_from = _to_dt(date_from)
    dt_to = _to_dt(date_to)
    if dt_to <= dt_from:
        raise HTTPException(400, "date_to debe ser mayor a date_from")

    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)

    # ✅ también removí ids_distintos para mantener consistencia con "no ids únicos"
    sql = text("""
        SELECT
            user_id,
            COUNT(*)::int AS total,
            COUNT(DISTINCT dni)::int AS dnis_distintos,
            MAX(scanned_at) AS ultima_lectura
        FROM scan_events
        WHERE scanned_at >= :dt_from
          AND scanned_at <  :dt_to
          AND (:producto IS NULL OR raw->>'p' = :producto)
          AND (:scanned_by IS NULL OR user_id = :scanned_by)
        GROUP BY user_id
        ORDER BY total DESC, ultima_lectura DESC;
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "dt_from": dt_from,
            "dt_to": dt_to,
            "producto": producto,
            "scanned_by": scanned_by_eff
        }).mappings().all()

    return {
        "date_from": dt_from.isoformat().replace("+00:00", "Z"),
        "date_to": dt_to.isoformat().replace("+00:00", "Z"),
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "rows": [dict(r) for r in rows],
    }
