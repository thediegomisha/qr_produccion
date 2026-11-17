# Diagnóstico de API 400 al sincronizar la APK

## Hallazgo de código

El mensaje anterior «QR no emitido o DNI no coincide con la emisión» se genera
en `backend/app/api/routes_scans.py`, no en el lector de cámara.

En el código revisado de la APK v1.2.6:

- `ConteoCajasActivity.parsePayload` extrae `t` y `dni` del QR.
- Se conserva el token (solo se recortan espacios exteriores); no se convierte
  a mayúsculas ni se elimina el guion bajo del nuevo formato.
- El DNI conserva sus dígitos y se exige una longitud de ocho cifras.
- `ApiClient.postBatch` envía los campos guardados en `ScanEntity` y el JSON
  original como `raw`. Aunque el campo auxiliar de producto del parser antiguo
  busca `producto`, el valor `p` sigue presente en `raw`; eso no causa este 400.
- Ante un 400, el envío vuelve a pendiente. No reinstalar, borrar datos ni
  limpiar el historial para intentar resolverlo.

Esto es evidencia de la revisión del código local. Aún se necesita comprobar
la lectura concreta y la base que utiliza la API desplegada; no se ha inspeccionado
el almacenamiento del teléfono ni confirmado su versión instalada.

## Corrección compatible con la APK actual

- Una lectura ya registrada con el mismo token y DNI se confirma como duplicada,
  aunque su emisión antigua ya no esté en `qr_emitidos`.
- No se inserta nuevamente, no cambia de lote y no se reconstruye la emisión.
- Un DNI distinto al de la lectura existente sigue siendo rechazado.
- Las lecturas nuevas siguen exigiendo una emisión válida con el mismo DNI.
- El servidor diferencia `QR_NO_EMITIDO`, `DNI_EMISION_DISTINTO` y
  `DNI_LECTURA_DISTINTO`, indicando la posición de la lectura en el envío.
- Un error sigue rechazando todo el envío; no se responde 200 parcial porque
  las APK existentes marcarían como enviados registros que permanecen pendientes.

## Identificar la causa real

Ejecutar `scripts/diagnosticar_qr.sql` en la misma base usada por la API,
reemplazando los dos valores por el token y el DNI del QR o de la lectura local.
La consulta no escribe datos ni muestra el DNI esperado.

- `QR_NO_EMITIDO`: verificar si la etiqueta se imprimió desde otra base/instancia,
  si no se confirmó su transacción o si la emisión fue eliminada. El mensaje
  solo establece que el registro no está en esa base, no prueba una falsificación.
- `DNI_EMISION_DISTINTO`: comparar privadamente la etiqueta y su emisión.
  No sustituir el DNI automáticamente: podría atribuir producción a otra persona.
- `DUPLICADO_CONFIRMADO`: el cambio del backend permite confirmar el reenvío
  sin volver a contabilizarlo.
- `EMISION_VALIDA`: verificar que la APK esté enviando a esa misma API/base y
  revisar las demás lecturas del envío. Basta una inválida para rechazarlo entero.

Si faltan emisiones de etiquetas legítimas, recuperar solo las identificadas
desde respaldos o registros confiables, con respaldo previo y confirmación del
administrador. No registrar automáticamente todo QR que envíe el teléfono ni
desactivar la validación global.
