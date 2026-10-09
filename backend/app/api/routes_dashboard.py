from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.auth_dep import get_current_user
from app.db.base import SessionLocal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Días trabajados se evalúan en hora local de la operación (Perú).
_TIMEZONE = "America/Lima"


def _clean_optional(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


def _allowed(user: dict) -> bool:
    rol = (user.get("rol") or "").upper()
    return rol in ("ROOT", "GERENCIA", "SUPERVISOR")


# -------------------------
# Cajas procesadas por día y lote
# -------------------------
@router.get("/cajas-por-dia")
def cajas_por_dia(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)
    date_from = _clean_optional(date_from)
    date_to = _clean_optional(date_to)

    sql = text("""
        SELECT
            (se.scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
            COALESCE(l.codigo, 'SIN LOTE') AS lote,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$')::int AS empacadas,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$')::int AS seleccionadas
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        WHERE (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (:lote IS NULL OR l.codigo = :lote)
        GROUP BY dia, lote
        ORDER BY dia, lote
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "tz": _TIMEZONE,
            "date_from": date_from,
            "date_to": date_to,
            "lote": lote,
        }).mappings().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Eficiencia por persona (trabajadores)
# -------------------------
@router.get("/eficiencia-personal")
def eficiencia_personal(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)
    date_from = _clean_optional(date_from)
    date_to = _clean_optional(date_to)

    # Eficiencia: cajas por hora activa en la sesión (primera a última lectura por sesión+día).
    sql = text("""
        WITH base AS (
            SELECT
                se.dni,
                se.user_id,
                se.session_uuid,
                (se.scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
                se.scanned_at,
                (se.raw->>'id') ~ '^[0-9]+$' AS es_empacador
            FROM scan_events se
            LEFT JOIN lotes l ON l.id = se.lote_id
            WHERE (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
              AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
              AND (:lote IS NULL OR l.codigo = :lote)
        ),
        sesiones AS (
            SELECT
                dni,
                user_id,
                session_uuid,
                dia,
                COUNT(*)::int AS cajas,
                COUNT(*) FILTER (WHERE es_empacador)::int AS empacadas,
                COUNT(*) FILTER (WHERE NOT es_empacador)::int AS seleccionadas,
                MIN(scanned_at) AS primera,
                MAX(scanned_at) AS ultima
            FROM base
            GROUP BY dni, user_id, session_uuid, dia
        )
        SELECT
            s.dni,
            COALESCE(NULLIF(TRIM(t.apellido_paterno || ' ' || COALESCE(t.apellido_materno, '') || ' ' || COALESCE(t.nombre, '')), ''), 'SIN REGISTRO') AS persona,
            COALESCE(t.rol, 'DESCONOCIDO') AS rol_trabajador,
            COUNT(*)::int AS sesiones,
            SUM(s.cajas)::int AS total_cajas,
            SUM(s.empacadas)::int AS empacadas,
            SUM(s.seleccionadas)::int AS seleccionadas,
            COUNT(DISTINCT s.dia)::int AS dias_trabajados,
            ROUND(SUM(
                CASE WHEN EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600 <= 0
                     THEN 1.0 / 60.0
                     ELSE EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600
                END
            )::numeric, 2)::float AS horas_activas,
            ROUND((
                CASE WHEN SUM(
                    CASE WHEN EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600 <= 0
                         THEN 1.0 / 60.0
                         ELSE EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600
                    END
                ) > 0
                THEN SUM(s.cajas)::float / SUM(
                    CASE WHEN EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600 <= 0
                         THEN 1.0 / 60.0
                         ELSE EXTRACT(EPOCH FROM (s.ultima - s.primera))::float / 3600
                    END
                )
                ELSE 0 END
            )::numeric, 1)::float AS cajas_por_hora
        FROM sesiones s
        LEFT JOIN trabajadores t ON TRIM(t.dni) = TRIM(s.dni) AND t.activo = true
        GROUP BY s.dni, persona, rol_trabajador
        ORDER BY total_cajas DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "tz": _TIMEZONE,
            "date_from": date_from,
            "date_to": date_to,
            "lote": lote,
        }).mappings().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Serie diaria por persona (para gráfico)
# -------------------------
@router.get("/eficiencia-por-dia")
def eficiencia_por_dia(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)
    date_from = _clean_optional(date_from)
    date_to = _clean_optional(date_to)

    sql = text("""
        SELECT
            (se.scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
            se.dni,
            COALESCE(NULLIF(TRIM(t.apellido_paterno || ' ' || COALESCE(t.apellido_materno, '') || ' ' || COALESCE(t.nombre, '')), ''), 'SIN REGISTRO') AS persona,
            COUNT(*)::int AS total_cajas,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$')::int AS empacadas,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$')::int AS seleccionadas
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        LEFT JOIN trabajadores t ON TRIM(t.dni) = TRIM(se.dni) AND t.activo = true
        WHERE (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (:lote IS NULL OR l.codigo = :lote)
        GROUP BY dia, se.dni, persona
        ORDER BY dia, total_cajas DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "tz": _TIMEZONE,
            "date_from": date_from,
            "date_to": date_to,
            "lote": lote,
        }).mappings().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Ritmo por hora del día (hora local de la operación)
# -------------------------
@router.get("/cajas-por-hora")
def cajas_por_hora(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)
    date_from = _clean_optional(date_from)
    date_to = _clean_optional(date_to)

    sql = text("""
        SELECT
            EXTRACT(HOUR FROM (se.scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz))::int AS hora,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$')::int AS empacadas,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$')::int AS seleccionadas
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        WHERE (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (:lote IS NULL OR l.codigo = :lote)
        GROUP BY hora
        ORDER BY hora
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "tz": _TIMEZONE,
            "date_from": date_from,
            "date_to": date_to,
            "lote": lote,
        }).mappings().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Producción por persona y lote (matriz para heatmap)
# -------------------------
@router.get("/produccion-persona-lote")
def produccion_persona_lote(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    lote_codigo: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)
    date_from = _clean_optional(date_from)
    date_to = _clean_optional(date_to)

    sql = text("""
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
            COALESCE(l.codigo, 'SIN LOTE') AS lote,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]+$')::int AS empacadas,
            COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]+$')::int AS seleccionadas
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        LEFT JOIN trabajadores t ON TRIM(t.dni) = TRIM(se.dni) AND t.activo = true
        WHERE (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
          AND (:lote IS NULL OR l.codigo = :lote)
        GROUP BY se.dni, persona, lote
        ORDER BY persona, total DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "tz": _TIMEZONE,
            "date_from": date_from,
            "date_to": date_to,
            "lote": lote,
        }).mappings().all()

    return {
        "date_from": date_from,
        "date_to": date_to,
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }


# -------------------------
# Actividad reciente (últimas lecturas)
# -------------------------
@router.get("/actividad-reciente")
def actividad_reciente(
    lote_codigo: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_current_user),
):
    if not _allowed(user):
        raise HTTPException(403, "Sin permisos para el dashboard")

    lote = _clean_optional(lote_codigo)

    sql = text("""
        SELECT
            se.token,
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
            COALESCE(l.codigo, 'SIN LOTE') AS lote,
            CASE
                WHEN (se.raw->>'id') ~ '^[0-9]+$' THEN 'Empacada'
                ELSE 'Seleccionada'
            END AS tipo,
            se.scanned_at
        FROM scan_events se
        LEFT JOIN lotes l ON l.id = se.lote_id
        LEFT JOIN trabajadores t ON TRIM(t.dni) = TRIM(se.dni) AND t.activo = true
        WHERE (:lote IS NULL OR l.codigo = :lote)
        ORDER BY se.scanned_at DESC
        LIMIT :limite
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, {
            "lote": lote,
            "limite": limit,
        }).mappings().all()

    return {
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }
