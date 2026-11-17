-- Solo lectura. Ejecutar en la misma base de datos que utiliza la API.
-- Sustituir ambos valores con los datos del QR físico o la lectura pendiente.
-- No publica el DNI esperado ni cambia emisiones, lecturas o lotes.
WITH leido AS (
    SELECT 'TOKEN_ESCANEADO'::text AS token, 'DNI_ESCANEADO'::text AS dni
)
SELECT
    q.token IS NOT NULL AS emision_existe,
    COALESCE(TRIM(q.dni_trabajador) = leido.dni, false) AS dni_coincide_emision,
    s.token IS NOT NULL AS lectura_ya_registrada,
    COALESCE(TRIM(s.dni) = leido.dni, false) AS dni_coincide_lectura,
    CASE
        WHEN s.token IS NOT NULL AND TRIM(s.dni) = leido.dni
            THEN 'DUPLICADO_CONFIRMADO'
        WHEN s.token IS NOT NULL
            THEN 'DNI_LECTURA_DISTINTO'
        WHEN q.token IS NULL
            THEN 'QR_NO_EMITIDO'
        WHEN q.dni_trabajador IS NULL OR TRIM(q.dni_trabajador) <> leido.dni
            THEN 'DNI_EMISION_DISTINTO'
        ELSE 'EMISION_VALIDA'
    END AS diagnostico
FROM leido
LEFT JOIN qr_emitidos q ON q.token = TRIM(leido.token)
LEFT JOIN scan_events s ON s.token = TRIM(leido.token);
