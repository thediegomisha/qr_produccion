from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.auth_dep import get_current_user
from app.db.base import SessionLocal
from app.services.production_sql import production_cte, production_params

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

    sql = text(f"""
        {production_cte()}
        SELECT
            (scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
            lote,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%')::int AS empacadas,
            COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR')::int AS seleccionadas,
            COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR')::int AS sin_rol
        FROM base
        GROUP BY dia, lote
        ORDER BY dia, lote
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

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

    # El rol registrado del trabajador define la tarea. Todas sus lecturas y sus
    # horas activas se asignan a ese rol, aunque la etiqueta se haya impreso con
    # número o con letra.
    sql = text(f"""
        {production_cte()},
        sesiones AS (
            SELECT
                dni,
                user_id,
                session_uuid,
                (scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
                MIN(persona) AS persona,
                MIN(rol) AS rol,
                COUNT(*)::int AS cajas,
                COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%')::int AS empacadas,
                COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR')::int AS seleccionadas,
                COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR')::int AS sin_rol,
                MIN(scanned_at) AS primera,
                MAX(scanned_at) AS ultima
            FROM base
            GROUP BY dni, user_id, session_uuid, dia
        ),
        por_persona AS (
            SELECT
                dni,
                MIN(persona) AS persona,
                MIN(rol) AS rol,
                COUNT(*)::int AS sesiones,
                SUM(cajas)::int AS total_cajas,
                SUM(empacadas)::int AS empacadas,
                SUM(seleccionadas)::int AS seleccionadas,
                SUM(sin_rol)::int AS sin_rol,
                COUNT(DISTINCT dia)::int AS dias_trabajados,
                SUM(
                    CASE WHEN EXTRACT(EPOCH FROM (ultima - primera))::float / 3600 <= 0
                         THEN 1.0 / 60.0
                         ELSE EXTRACT(EPOCH FROM (ultima - primera))::float / 3600
                    END
                ) AS horas_activas
            FROM sesiones
            GROUP BY dni
        ),
        tareas AS (
            SELECT
                dni,
                rol,
                SUM(
                    CASE WHEN EXTRACT(EPOCH FROM (ultima - primera))::float / 3600 <= 0
                         THEN 1.0 / 60.0
                         ELSE EXTRACT(EPOCH FROM (ultima - primera))::float / 3600
                    END
                ) AS horas
            FROM (
                SELECT
                    dni,
                    session_uuid,
                    (scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
                    rol,
                    MIN(scanned_at) AS primera,
                    MAX(scanned_at) AS ultima
                FROM base
                GROUP BY dni, session_uuid, dia, rol
            ) tarea_sesion
            GROUP BY dni, rol
        )
        SELECT
            p.dni,
            p.persona,
            CASE WHEN p.rol = 'SIN ROL' THEN 'DESCONOCIDO' ELSE p.rol END AS rol_trabajador,
            p.sesiones,
            p.total_cajas,
            p.empacadas,
            p.seleccionadas,
            p.sin_rol,
            p.dias_trabajados,
            ROUND(p.horas_activas::numeric, 2)::float AS horas_activas,
            ROUND(COALESCE(te.horas, 0)::numeric, 2)::float AS horas_empacado,
            ROUND(COALESCE(ts.horas, 0)::numeric, 2)::float AS horas_seleccion,
            COALESCE(ROUND((p.total_cajas::float / NULLIF(p.horas_activas, 0))::numeric, 1)::float, 0) AS cajas_por_hora,
            COALESCE(ROUND((p.empacadas::float / NULLIF(te.horas, 0))::numeric, 1)::float, 0) AS empacadas_por_hora,
            COALESCE(ROUND((p.seleccionadas::float / NULLIF(ts.horas, 0))::numeric, 1)::float, 0) AS seleccionadas_por_hora
        FROM por_persona p
        LEFT JOIN tareas te ON te.dni = p.dni AND te.rol LIKE 'EMPACADOR%'
        LEFT JOIN tareas ts ON ts.dni = p.dni AND ts.rol = 'SELECCIONADOR'
        ORDER BY total_cajas DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

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

    sql = text(f"""
        {production_cte()}
        SELECT
            (scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz)::date AS dia,
            dni,
            MIN(persona) AS persona,
            MIN(rol) AS rol,
            COUNT(*)::int AS total_cajas,
            COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%')::int AS empacadas,
            COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR')::int AS seleccionadas,
            COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR')::int AS sin_rol
        FROM base
        GROUP BY dia, dni
        ORDER BY dia, total_cajas DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

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

    sql = text(f"""
        {production_cte()}
        SELECT
            EXTRACT(HOUR FROM (scanned_at AT TIME ZONE 'UTC' AT TIME ZONE :tz))::int AS hora,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%')::int AS empacadas,
            COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR')::int AS seleccionadas,
            COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR')::int AS sin_rol
        FROM base
        GROUP BY hora
        ORDER BY hora
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

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

    sql = text(f"""
        {production_cte()}
        SELECT
            dni,
            MIN(persona) AS persona,
            lote,
            MIN(rol) AS rol,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE rol LIKE 'EMPACADOR%')::int AS empacadas,
            COUNT(*) FILTER (WHERE rol = 'SELECCIONADOR')::int AS seleccionadas,
            COUNT(*) FILTER (WHERE rol NOT LIKE 'EMPACADOR%' AND rol <> 'SELECCIONADOR')::int AS sin_rol
        FROM base
        GROUP BY dni, lote
        ORDER BY persona, total DESC
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            date_from=date_from,
            date_to=date_to,
            tz=_TIMEZONE,
        )).mappings().all()

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

    sql = text(f"""
        {production_cte()}
        SELECT
            token,
            dni,
            persona,
            lote,
            CASE
                WHEN rol LIKE 'EMPACADOR%' THEN 'Empacada'
                WHEN rol = 'SELECCIONADOR' THEN 'Seleccionada'
                ELSE 'Sin rol'
            END AS tipo,
            scanned_at
        FROM base
        ORDER BY scanned_at DESC
        LIMIT :limite
    """)

    with SessionLocal() as db:
        rows = db.execute(sql, production_params(
            lote=lote,
            tz=_TIMEZONE,
            limite=limit,
        )).mappings().all()

    return {
        "lote_codigo": lote,
        "rows": [dict(r) for r in rows],
    }
