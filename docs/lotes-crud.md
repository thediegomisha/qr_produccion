# CRUD de lotes

Desarrollo en la rama `feature/crud-lotes`, basado en la versión de `main` instalada en el servidor. El ajuste ZPL recuperado del servidor se conserva en el directorio de trabajo.

## Funcionalidad

La pestaña **Lotes** permite crear, buscar por código, filtrar por estado y recorrer todo el listado en páginas de 50 registros. Cada fila muestra su identificador, código, estado, cantidad de lecturas y fechas de creación/cierre/reapertura.

El formulario de creación está dentro de **Crear nuevo lote**, un panel desplegable. Seleccionar un lote en **Seleccionar lote** abre un modal con su detalle y las acciones disponibles para el rol. La página principal conserva el listado y los filtros, sin desplegar los formularios de mantenimiento.

Al guardar, eliminar, cerrar/reabrir o usar el lote activo, el modal se cierra y se actualiza el listado. Se puede salir con **Volver al listado**, la X, Escape o un clic fuera del modal. La selección se limpia para permitir abrir nuevamente el mismo lote; los cambios sin guardar se descartan.

| Operación | ROOT | GERENCIA | SUPERVISOR |
|---|---|---|---|
| Crear, consultar y seleccionar lote activo | Sí | Sí | Sí |
| Cerrar lote | Sí | Sí | Sí |
| Reabrir lote | Sí | No | No |
| Editar código y estado | Sí | Sí, sin reabrir | No |
| Eliminar lote completo y sus lecturas | Sí | Sí | No |

Los permisos se verifican también en la API. Las fechas y autores de creación/cierre/reapertura son datos de seguimiento y no se editan manualmente.

Editar el código conserva el ID y las lecturas existentes. El lote activo de la sesión Streamlit se actualiza al guardar, y se limpia al cerrar o eliminar. Al renombrar un lote, debe seleccionarse el código actualizado en los lectores para los próximos envíos: el contrato Android actual identifica los lotes por código y no actualiza las lecturas pendientes de otros dispositivos.

Eliminar un lote completo requiere confirmación en la pantalla y borra `lotes` y sus registros de `scan_events` en una sola transacción. Los reportes dejan de incluir esas lecturas. Si otra referencia de la base impide borrar, la transacción se revierte y también conserva las lecturas. La generación de etiquetas y las personas no son parte de esta eliminación.

Los envíos Android y las modificaciones del lote utilizan un bloqueo de fila PostgreSQL. Un envío que ya está en curso termina antes de editar/cerrar/eliminar el lote. La eliminación no borra las colas locales de los lectores; las rutas antiguas de asegurar/enviar pueden crear nuevamente un código inexistente si otro dispositivo lo utiliza después.

## API

| Método | Ruta | Función |
|---|---|---|
| POST | `/api/lotes` | Crear; responde 201 o 409 si el código existe |
| GET | `/api/lotes` | Listar con `q`, `estado`, `limit` y `offset` |
| GET | `/api/lotes/{id}` | Consultar detalle y cantidad de lecturas |
| PUT | `/api/lotes/{id}` | Editar `codigo` y `estado` |
| DELETE | `/api/lotes/{id}` | Eliminar lote y lecturas; devuelve `deleted_scans` |
| POST | `/api/lotes/ensure` | Creación idempotente utilizada por la APK |
| POST | `/api/lotes/{codigo}/close` | Cierre compatible con la APK |
| POST | `/api/lotes/{codigo}/open` | Reapertura compatible con la APK |

Los códigos se normalizan a mayúsculas y sin espacios exteriores. Deben tener entre 1 y 64 caracteres y no contener barras ni caracteres de control. No se requiere una migración de esquema para este CRUD: utiliza las tablas existentes.

## Pruebas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Por defecto se utiliza SQLite en memoria. Para ejecutar además la integración de envíos Android y concurrencia PostgreSQL, preparar una base vacía de pruebas llamada exactamente `qr_lotes_test`:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://usuario@127.0.0.1:55432/qr_lotes_test python -m pytest -q
```

Las pruebas crean, limpian y eliminan sus tablas en esa base aislada. No utilizan los `.env` del proyecto ni la API del servidor. Las pruebas Streamlit ejecutan formularios reales con AppTest y una API local simulada por TestClient.

El workflow `.github/workflows/lotes-tests.yml` ejecuta la suite en PostgreSQL 16 cuando se publique la rama `feature/crud-lotes` o se abra una solicitud de integración hacia `main`. Utiliza una base efímera del runner y publica el informe de pruebas, sin desplegar al servidor.

## Prueba funcional de la rama

1. ROOT: crear un lote, comprobar rechazo de duplicados y buscarlo en el listado.
   Seleccionarlo para abrir el modal; cerrar sin guardar y volver a seleccionar el mismo lote.
2. Agregar lecturas a un lote de pruebas y renombrarlo: su ID y el total de lecturas deben conservarse.
3. Cerrar y reabrir; comprobar el lote activo y los autores/fechas de las operaciones.
4. GERENCIA: editar un lote cerrado y comprobar que no permite reabrirlo.
5. SUPERVISOR: comprobar creación/cierre y ausencia de edición/eliminación.
6. Eliminar un lote de pruebas con lecturas: exigir la confirmación, mostrar la cantidad eliminada y conservar los demás lotes.
7. Consultar los reportes y comprobar el cambio de nombre o la eliminación de sus lecturas.

El backend y el frontend de esta rama deben probarse juntos: la pantalla utiliza los nuevos endpoints y la paginación. Para probar en el servidor, utilizar una instalación y una base de pruebas separadas de `/opt/qr_produccion` y de sus servicios en producción. Las conexiones siguen siendo variables del entorno del servidor.
