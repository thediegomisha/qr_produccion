from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user
from app.services.production_sql import production_cte, production_params

router = APIRouter(prefix="/reports", tags=["reports"])

# Los días se evalúan en hora local de la operación (Perú), igual que el dashboard.
_TIMEZONE = "America/Lima"


def _clean_date(value: Optional[str]) -> Optional[str]:
    value = _clean_optional(value)
    if not value:
        return None
    # Formato oficial de la API: AAAA-MM-DD (día en hora Perú).
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    # Compatibilidad: versiones anteriores de la APK enviaban ISO-8601 en UTC
    # (p. ej. 2026-03-06T05:00:00Z). Se convierte a día local de Perú para que
    # esos equipos sigan funcionando sin reinstalar la app.
    try:
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        try:
            tz = ZoneInfo(_TIMEZONE)
        except Exception:
            # Perú no aplica horario de verano: UTC-5 fijo como respaldo.
            tz = timezone(timedelta(hours=-5))
        return dt.astimezone(tz).date().isoformat()
    except Exception:
        raise HTTPException(400, f"Fecha inválida (use AAAA-MM-DD): {value}")


def _date_pair(date_from: Optional[str], date_to: Optional[str]):
    date_from = _clean_date(date_from)
    date_to = _clean_date(date_to)
    if (date_from is None) != (date_to is None):
        raise HTTPException(400, "Indique ambas fechas (date_from y date_to) o ninguna")
    if date_from and date_to and date_to < date_from:
        raise HTTPException(400, "La fecha final debe ser mayor o igual a la inicial")
    return date_from, date_to


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
    """Production reports are shared across authenticated users.

    Only an explicitly requested operator filter narrows the consolidated lot.
    The caller's identity must never silently change the totals.
    """
    requested = (requested_user_id or "").strip()
    return requested or None


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
    producto: Optional[str] = Query(None, description="Ej: UVA"),
    scanned_by: Optional[str] = Query(None, description="Filtro opcional por operador; omitido incluye todos"),
    lote_codigo: Optional[str] = Query(None, description="Código de lote, ej: 1234-2026"),
    date_from: Optional[str] = Query(None, description="AAAA-MM-DD (hora Perú)"),
    date_to: Optional[str] = Query(None, description="AAAA-MM-DD (hora Perú)"),
    user=Depends(get_current_user),
):
    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)
    lote_codigo = _clean_optional(lote_codigo)
    date_from, date_to = _date_pair(date_from, date_to)

    sql = text(f"""
    {production_cte()}
    SELECT
      dni,
      persona,
      MIN(rol) AS rol,
      COALESCE(
        STRING_AGG(DISTINCT codigo, ', ' ORDER BY codigo)
          FILTER (WHERE codigo IS NOT NULL),
        ''
      ) AS codigo,
      COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%') AS empacador,
      COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR') AS seleccionador,
      COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR') AS sin_rol,
      COUNT(*) AS total
    FROM base
    GROUP BY dni, persona
    ORDER BY total DESC;
    """)

    with SessionLocal() as db:
        _, lote_codigo_db, _ = _resolve_lote(db, lote_codigo)

        params = production_params(
            producto=producto,
            scanned_by=scanned_by_eff,
            lote=lote_codigo_db,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )
        rows = [dict(r) for r in db.execute(sql, params).mappings().all()]

    totals = {
        "total_lecturas": sum(int(r["total"] or 0) for r in rows),
        "emp_lecturas": sum(int(r["empacador"] or 0) for r in rows),
        "sel_lecturas": sum(int(r["seleccionador"] or 0) for r in rows),
        "sin_rol_lecturas": sum(int(r["sin_rol"] or 0) for r in rows),
    }

    return {
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "lote_codigo": lote_codigo,
        "date_from": date_from,
        "date_to": date_to,
        "totals": totals,
        "rows": rows,
    }



# -------------------------
# Reporte: resumen por operador (user_id) - POR LOTE
# -------------------------
@router.get("/operator-summary")
def operator_summary(
    producto: Optional[str] = Query(None),
    scanned_by: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="AAAA-MM-DD (hora Perú)"),
    date_to: Optional[str] = Query(None, description="AAAA-MM-DD (hora Perú)"),
    user=Depends(get_current_user),
):
    producto = _clean_optional(producto)
    scanned_by_eff = _effective_user_filter(user, scanned_by)
    lote_codigo = _clean_optional(lote_codigo)
    date_from, date_to = _date_pair(date_from, date_to)

    sql = text(f"""
    {production_cte()}
    SELECT
      user_id,
      COUNT(*)::int AS total,
      COUNT(DISTINCT dni)::int AS dnis_distintos,
      MAX(scanned_at) AS ultima_lectura
    FROM base
    GROUP BY user_id
    ORDER BY total DESC, ultima_lectura DESC;
    """)

    with SessionLocal() as db:
        _, lote_codigo_db, _ = _resolve_lote(db, lote_codigo)
        rows = db.execute(sql, production_params(
            producto=producto,
            scanned_by=scanned_by_eff,
            lote=lote_codigo_db,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

    return {
        "producto": producto,
        "scanned_by": scanned_by_eff,
        "lote_codigo": lote_codigo,
        "date_from": date_from,
        "date_to": date_to,
        "rows": [dict(r) for r in rows],
    }
