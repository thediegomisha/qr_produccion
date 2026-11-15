# QR Lector para iPhone

## Instalación

La PWA está incluida en el paquete web y se sirve desde el mismo backend:

`https://app.juanluisdiaz.space/api/movil/`

Esta dirección estará disponible **después de desplegar los cambios web**.

1. Abrir la dirección HTTPS en Safari en el iPhone 14.
2. Pulsar **Compartir → Añadir a pantalla de inicio**.
3. Abrir QR Lector desde el icono e iniciar sesión con el usuario existente.
4. Permitir el acceso a la cámara y seleccionar un lote abierto.

No requiere Mac, App Store ni cuenta de desarrollador Apple.
La URL LAN por HTTP permite consultas, pero **no permite cámara en Safari**.
Para cámara en LAN se necesita HTTPS con certificado confiable para el iPhone.

## Funciones

- Login y renovación automática del access token mediante refresh token.
- El menú muestra nombre registrado, nickname y rol. El nombre se toma del campo
  **Nombre** de Administración de usuarios; si está vacío se conserva el nickname.
  La web principal muestra la misma identificación en la barra lateral.
- Conteo de cajas: QR, lote obligatorio, total y rejilla por DNI.
- Motor ZXing-C++ compilado a WebAssembly (`zxing-wasm` 3.1.6), ejecutado en
  un Worker para no bloquear la interfaz. Comparte el motor base de Android,
  no necesariamente la misma revisión del código C++. Cámara y enfoque siguen
  dependiendo de Safari. Conteo busca solo QR; vigilancia busca Code39 y QR.
  Si la etiqueta se ve borrosa, usar el selector de cámara sobre la vista previa
  para probar otra lente trasera y alejar ligeramente la etiqueta.
- Detección local de tokens repetidos.
- Lotes: selección y creación; cierre según permisos; reapertura solo ROOT.
- Historial local: pendientes, enviados y recibos de envíos con duplicados.
- Reportes por DNI, empacador y seleccionador; fechas inclusivas en hora Perú.
- En los clientes móviles, el reporte **por lote** incluye todos los días:
  se retiraron Desde/Hasta y no se envía un rango de fechas oculto.
  La API mantiene los filtros opcionales para los demás reportes.
- La grilla muestra nombre, DNI, código de etiqueta, empacado, selección y total.
  El campo `codigo` conserva el identificador QR leído (numérico o letra);
  si hay varios códigos para un DNI en el mismo lote, se muestran sin repetir.
  Instalar APK 1.2.5 y desplegar el backend actualizado para ver esta columna.
- Reportes consolidados del lote para todos los roles, sin filtro implícito por
  el usuario que consulta. Tras **Consultar**, la PWA y la APK 1.2.2 refrescan
  cada 10 segundos mientras el reporte está abierto/en primer plano. No es
  push instantáneo: solo incluye lecturas confirmadas por el servidor.
  Comparar siempre el mismo lote, producto y rango de fechas entre equipos.
- Consultas por DNI.
- Vigilancia: Code 39 o QR con DNI; entrada/salida y registro manual de personas.
- Menú por rol, siguiendo la APK. El backend sigue siendo responsable de autorizar peticiones.

El backend devuelve cantidades agregadas de aceptados y duplicados, no el estado
de cada etiqueta. Por eso los duplicados del servidor se muestran por envío.
El historial de este iPhone no incorpora el historial local de las APK.

## Sin conexión y sesión

Después de una primera apertura con conexión, el service worker guarda la interfaz
y el lector local. Con sesión recordada y lote ya seleccionado, las lecturas se
guardan en IndexedDB. Al recuperar conexión, pulsar **Enviar**; no hay sincronización
en segundo plano ni envío automático. Cada envío conserva usuario, lote y sesión
originales, con un máximo de 500 lecturas del mismo contexto.

**Limpiar** crea una sesión nueva: no borra los pendientes ni cambia su lote.
Los envíos interrumpidos se recuperan al reintentar. Un lote cerrado conserva sus
pendientes hasta que ROOT lo reabra; no se reasignan automáticamente a otro lote.

Las visitas de vigilancia requieren conexión. Un error se muestra para completar
o reintentar explícitamente; no se encolan visitas para registrarlas con otra fecha.

La sesión puede sobrevivir inactividad mientras el refresh token sea válido
(actualmente 7 días). Cuando expire, se pedirá login nuevamente. Las credenciales
se almacenan en el espacio del sitio del navegador, no en el llavero nativo de iOS.
No compartir el perfil de Safari con terceros.

Safari puede eliminar datos del sitio por falta de espacio o por acción del usuario.
No borrar datos de Safari ni desinstalar la PWA con lecturas sin enviar.

## Actualizaciones

La PWA busca una nueva versión del service worker al volver al primer plano y
muestra **Actualizar**. Al aceptarlo se recarga la interfaz, sin borrar IndexedDB.
Al cambiar los archivos de la interfaz, incrementar `VERSION` en
`backend/app/mobile/sw.js` para instalar un shell completo y coherente.

No mezclar la actualización PWA con la APK:

- APK: publicar APK firmada y `version.json` en la misma carpeta persistente
  `UPDATES_DIR/qrlector` (por defecto `/opt/qr_produccion-web/shared/updates/qrlector`).
- LAN/WAN sirven `<base-api>/updates/qrlector/version.json` y la misma APK.
- Android prueba la red seleccionada, la otra y el override configurado. Para un
  manifiesto recibido por HTTP LAN, descarga la APK del mismo host y puerto LAN.
- La detección de Android ocurre al abrir el menú, como máximo cada 6 horas;
  mantener pulsado el usuario fuerza la comprobación.
- Android pide confirmar la instalación; no es una instalación silenciosa.
- La APK que incorpora el nuevo actualizador LAN/WAN debe instalarse primero en
  los dispositivos antiguos. Publicarla no cambia por sí solo su actualizador.

Evitar caché de `version.json` en proxy/CDN. No cachear `/api/auth/*` ni los endpoints
de negocio. Los recursos de la PWA se cachean únicamente bajo `/api/movil/`.

## Pruebas

Backend y recursos estáticos:

```bash
TEST_DATABASE_URL="postgresql+psycopg2://postgres:postgres@127.0.0.1:54322/qr_lotes_test" \
  .venv/bin/python -m pytest -q
```

Prueba de navegador sin escrituras a la base: requiere backend local activo,
Chrome y `playwright-core`. Se puede instalar la dependencia en una carpeta temporal.

```bash
npm install --prefix /tmp/opencode/pwa-tests --no-audit --no-fund playwright-core@1.56.0
NODE_PATH=/tmp/opencode/pwa-tests/node_modules \
  node tests/mobile-smoke.cjs
```

Prueba de decodificación real (imagen QR → stream de cámara simulado → Worker
→ ZXing-C++), incluyendo rotación e inversión:

```bash
npm install --prefix /tmp/opencode/pwa-tests --ignore-scripts --no-audit --no-fund qrcode@1.5.4
NODE_PATH=/tmp/opencode/pwa-tests/node_modules node tests/mobile-decoder.cjs
```

Al actualizar desde la primera PWA, aceptar **Actualizar** y volver a abrirla.
La versión del shell es `1.1.0`; incluye el JS del lector y el archivo WASM local.

Opcionales: `CHROME_BIN` para la ruta del navegador y `MOBILE_URL` para una
instancia local distinta. La prueba simula todas las respuestas de negocio.

Validado en Chromium con viewport móvil, cámara simulada y pruebas de cola offline.
**Pendiente en el iPhone físico:** permisos Safari, enfoque/lectura de etiquetas QR
y Code 39 reales, instalación, sonido, retorno tras bloqueo y actualización instalada.
La emulación no certifica el comportamiento de Safari iOS.
