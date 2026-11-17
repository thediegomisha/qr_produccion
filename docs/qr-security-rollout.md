# QR compacto y despliegue seguro

## Formato y etiqueta

- Etiqueta sin cambios: 25 × 25 mm, cuatro columnas, separación y márgenes originales.
- Nuevo JSON: `{"t":"TOKEN","dni":"12345678","id":"001","p":"UVA"}`.
- Incluye el nombre completo del producto en `p`, para filtros SQL directos
  sobre `raw->>'p'`. No incluye versión ni firma. El servidor exige una emisión registrada
  en `qr_emitidos` cuyo DNI coincida. Esto permite etiquetas antiguas firmadas y
  etiquetas nuevas compactas, pero rechaza tokens desconocidos.
- Los tokens nuevos usan 96 bits aleatorios en 16 caracteres (antes, 32 bits).
  Con DNI de ocho cifras y código de tres caracteres el JSON ocupa 62 bytes para
  UVA y 64 para PALTA. El prefijo del producto ya no es necesario.
- ECC H, zona de silencio de cuatro módulos, magnificación máxima que cabe
  (3 para UVA/PALTA con token de 16 caracteres) y recuadro central fijo de 48 × 30 puntos.
- Texto central con altura de 22 puntos ZPL (antes 20); el ancho se ajusta para
  que tres caracteres no se recorten. Las medidas de la etiqueta no cambian.
- El PNG conserva píxeles enteros, sin reducción interpolada.
- La APK v1.2.6 puede consumir `t`, `dni`, `id`. El parser PWA acepta tanto las
  claves antiguas cortas como sus alias largos.
- La validación de emisión no impide copiar físicamente una etiqueta; la unicidad
  del token en las lecturas sigue impidiendo contabilizarla dos veces.

Antes de uso masivo, imprimir una fila real y comprobar lectura con la impresora,
papel y teléfonos de producción. No confundir una prueba digital con esta prueba.
Se recomienda mantener limpio el cabezal, evitar sobrecalentar la impresión y
preservar la zona blanca alrededor del QR.

## Cambios de seguridad

- JWT obligatorio para preview, impresión, RENIEC, impresoras y visitas.
- Eliminada la sesión global compartida y su endpoint.
- Bootstrap deshabilitado por defecto; para una instalación nueva requiere
  `ENABLE_BOOTSTRAP=true` y un `BOOTSTRAP_TOKEN` de al menos 32 caracteres,
  enviado en `X-Bootstrap-Token`. Deshabilitarlo después de crear ROOT.
- JWT y secreto QR obligatorios al arrancar, sin claves predeterminadas.
- Los tokens nuevos incluyen una versión derivada de las credenciales.
  Cambiar contraseña o desactivar una cuenta revoca sus tokens; el rol se obtiene
  de la cuenta vigente, no del JWT. Los tokens previos al cambio requieren login.
- Contraseñas nuevas: mínimo 12 caracteres.
- Límite de autenticación: 30 solicitudes/minuto por IP y proceso.
  Completar con un límite compartido en el proxy para despliegues multiworker.
- Refresh tokens revocables por cambio de contraseña/desactivación; aún no hay
  rotación de uso único ni revocación individual al cerrar sesión.
- Docs y OpenAPI públicos deshabilitados, cabeceras de seguridad y no-store en API.
- Agentes dinámicos de impresión restringidos a URLs configuradas en el servidor;
  sin redirecciones HTTP. Usar direcciones IP fijas o DNS administrado para evitar
  que un nombre autorizado cambie a un destino no confiable.
- Validación atómica de emisión/DNI/fecha antes de insertar un envío de lecturas.
  Los reenvíos de lecturas ya registradas con el mismo token y DNI se confirman
  como duplicados sin exigir la emisión histórica ni volver a insertarlos.
  Se aceptan fechas antiguas desde 2020 para sincronización offline, no más de
  cinco minutos en el futuro. Un elemento inválido rechaza todo el envío y no se
  borra de la cola del cliente; corregir/investigar esa lectura antes de reintentar.
- Las emisiones se confirman antes de enviar la fila al agente. Si el agente
  falla, quedan registradas para trazabilidad; no reintentar ciegamente una
  impresión cuyo resultado físico es desconocido.

## Acciones obligatorias del administrador antes de publicar

1. Hacer respaldo de base de datos y configuración privada. No subirlo a Git.
2. Rotar la contraseña PostgreSQL y los tokens de servicios externos/impresión
   expuestos. Actualizar todos los consumidores coordinadamente.
3. Generar secretos JWT y QR independientes con `scripts/generate_secrets.py`;
   guardar la salida en un archivo privado con permisos 600, fuera del repositorio.
   Completar `.env.example` en el entorno del servidor. No reutilizar claves viejas.
4. Configurar `PRINT_AGENT_URL`, `PRINT_AGENTS_JSON` o
   `PRINT_AGENT_ALLOWED_URLS` con los destinos reales autorizados. El cliente ya
   no puede elegir cualquier dirección. No publicar sus tokens.
5. Cerrar PostgreSQL a Internet; restringir 8000/8501 a loopback o red privada.
   Publicar la aplicación únicamente por HTTPS mediante un proxy de confianza.
   Configurar límites de cuerpo/solicitudes en ese proxy.
6. Retirar el acceso público al repositorio con datos filtrados y planificar la
   limpieza coordinada del historial, forks, releases y artefactos. Quitar los
   archivos del índice no elimina copias históricas ni reemplaza la rotación.
7. Desplegar backend y UI juntos, tras la validación completa. Todos los usuarios
   deben iniciar sesión nuevamente. El despliegue comprueba `/api/health` (base
   disponible, sin datos de usuarios), no `/docs` ni `/setup/status`.
8. Actualizar la PWA a shell 1.1.4, aceptar la actualización y cerrar/reabrir las
   pestañas. No borrar el almacenamiento local: puede contener lecturas pendientes.
9. Probar login, impresión/preview, una etiqueta antigua y una nueva, sincronización
   offline, rechazo de QR desconocido, reportes y revocación de una cuenta de prueba.

No se ha ejecutado un despliegue ni una rotación remota como parte de estos cambios.
No se han eliminado ni corregido lecturas de producción.

## Validación local

- Suite Python: 132 pruebas aprobadas con PostgreSQL aislado, incluidos filtros
  directos `raw->>'p'` para UVA y PALTA después de sincronizar el QR compacto.
- PNG real con producto y número central decodificado por el WASM de la PWA a
  120/160 px sin desenfoque, 180 px con blur de 1 px y 220 px con blur de 1,5 px.
- `tests/scanner-regressions.cjs`: parser compacto/antiguo, reintento de captura,
  resolución nativa y limpieza del watchdog aprobados.
- La prueba de cámara en navegador `tests/mobile-decoder.cjs` fue actualizada,
  pero no se ejecutó en esta validación. Tampoco se probó una impresión física.
- El script de creación inicial de base requiere `psql` 15 o posterior para leer
  la contraseña del entorno sin ponerla en los argumentos del proceso.
