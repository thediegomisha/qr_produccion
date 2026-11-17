"""Consulta base compartida para los reportes de producción.

La clasificación de una lectura se hace por el rol registrado del trabajador
(EMPACADORA / SELECCIONADOR), no por la forma del código impreso. El código
visible se conserva solo para trazabilidad.

La base también resuelve el DNI y el producto desde ``qr_emitidos`` cuando el
token existe, para no depender de un ``raw`` incompleto o manipulado.
"""

PRODUCTION_BASE_SQL = """
    SELECT
        se.token,
        se.dni AS dni_lectura,
        se.user_id,
        se.session_uuid,
        se.scanned_at,
        se.lote_id,
        COALESCE(NULLIF(TRIM(q.dni_trabajador), ''), se.dni) AS dni,
        COALESCE(NULLIF(TRIM(q.nn), ''), NULLIF(TRIM(se.raw->>'id'), '')) AS codigo,
        COALESCE(NULLIF(TRIM(q.producto), ''), NULLIF(TRIM(se.raw->>'p'), '')) AS producto,
        COALESCE(NULLIF(UPPER(TRIM(t.rol)), ''), 'SIN ROL') AS rol,
        COALESCE(l.codigo, 'SIN LOTE') AS lote,
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
        ) AS persona
    FROM scan_events se
    LEFT JOIN lotes l ON l.id = se.lote_id
    LEFT JOIN qr_emitidos q ON q.token = se.token
    LEFT JOIN LATERAL (
        SELECT tw.rol, tw.nombre, tw.apellido_paterno, tw.apellido_materno
        FROM trabajadores tw
        WHERE TRIM(tw.dni) = TRIM(COALESCE(NULLIF(TRIM(q.dni_trabajador), ''), se.dni))
        ORDER BY tw.activo DESC, tw.id
        LIMIT 1
    ) t ON TRUE
"""

PRODUCTION_FILTERS_SQL = """
    WHERE (:scanned_by IS NULL OR se.user_id = :scanned_by)
      AND (:producto IS NULL OR TRIM(UPPER(COALESCE(NULLIF(TRIM(q.producto), ''), NULLIF(TRIM(se.raw->>'p'), '')))) = TRIM(UPPER(:producto)))
      AND (:lote IS NULL OR TRIM(UPPER(l.codigo)) = TRIM(UPPER(:lote)))
      AND (CAST(:date_from AS date) IS NULL OR se.scanned_at >= (CAST(:date_from AS date))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
      AND (CAST(:date_to AS date) IS NULL OR se.scanned_at < ((CAST(:date_to AS date) + 1))::timestamp AT TIME ZONE :tz AT TIME ZONE 'UTC')
"""


def production_cte() -> str:
    """Devuelve el CTE ``base`` listo para prefijar una consulta."""
    return f"WITH base AS ({PRODUCTION_BASE_SQL} {PRODUCTION_FILTERS_SQL})"


def production_params(
    *,
    producto=None,
    scanned_by=None,
    lote=None,
    date_from=None,
    date_to=None,
    tz="America/Lima",
    **extra,
) -> dict:
    """Parámetros comunes que espera ``production_cte()``."""
    params = {
        "producto": producto,
        "scanned_by": scanned_by,
        "lote": lote,
        "date_from": date_from,
        "date_to": date_to,
        "tz": tz,
    }
    params.update(extra)
    return params
