# Dashboard de producción y eliminación masiva de lotes

## Dashboard (`📈 Dashboard`)

Disponible para ROOT, GERENCIA y SUPERVISOR. Filtros: rango de fechas (hora de Perú) y lote, con **atajos de rango** (Hoy, 7 días, 30 días, 90 días) sobre los selectores de fecha.

Si el rango seleccionado no tiene lecturas pero el servidor sí registra lecturas en otras fechas, el dashboard indica la **fecha de la última lectura registrada** y ofrece un botón para saltar directamente a ese día. Si el servidor aún no tiene lecturas, guía al usuario hacia la impresión y el escaneo con la APK.

El diseño sigue el modelo de tableros estilo Plecto (números grandes en tarjetas, ranking del personal y visuales limpios), recreado en Streamlit:

1. **Tarjetas KPI** con números grandes y acentos de color. La primera es **Cajas empacadas** — la métrica de producción y base para formar pallets — seguida de Selección, Lecturas totales, Personas activas, Días trabajados y Sin rol.
2. **Gráfica principal: Cajas empacadas por lote** — barras por código de lote con las **empacadas** al frente (color sólido) y la **selección** al lado en tono claro. Si hay lecturas sin código clasificable se agregan en gris. Tabla resumen con empacadas en primer lugar y un total que siempre coincide con la suma de sus columnas.
3. **Distribución (donut)** — proporción empacadas/selección (y sin rol cuando existe) con las empacadas al centro, junto al **Ritmo por hora del día**: barras por hora (hora de Perú) separando empacadas, selección y sin rol, con hora pico de empacado.
4. **Eficiencia del personal** — ranking estilo leaderboard con medallas 🥇🥈🥉 y un selector **Ranking de: Empacadoras / Seleccionadores**. Ver [tarea y rol](#tarea-y-rol-el-código-del-qr-define-la-tarea).
5. **Exportar dashboard** — Excel (hojas Resumen, Por lote y Por persona) e impresión, con la tabla completa del personal.
6. **Actividad reciente** — últimas 10 lecturas en vivo (hora local, persona, lote, tipo).

### Tarea y rol: el código del QR define la tarea

La clasificación vuelve a tomar el código impreso, como antes de la regresión del 16 de noviembre. `trabajadores.rol` se conserva como información del trabajador, pero no determina sus cantidades:

| Código del QR | Tarea |
|---|---|
| Comienza con número (`^[0-9]`) | **Empacado** |
| Comienza con letra (`^[A-Za-z]`) | **Selección** |
| Vacío, ausente o inicio no reconocido | **Sin clasificar**, conservado como `sin_rol` por compatibilidad |

El código se resuelve desde `qr_emitidos.nn`, con respaldo en `raw.id`, y se eliminan espacios exteriores antes de clasificar. Una persona registrada como empacadora puede tener cantidades en ambas columnas. No se modifica su rol ni se reescriben lecturas históricas.

Consecuencias en el dashboard y los reportes:

- El ranking tiene dos vistas. **Empacadoras** ordena por `empacadas` y **Seleccionadores** por `seleccionadas`; solo aparece quien tiene al menos una caja de ese rol, de modo que un seleccionador no queda oculto detrás del mayor volumen de empacado.
- Cada persona puede aparecer en ambos rankings según sus lecturas. Un trabajador sin registro también se clasifica si el código es reconocible; ninguna lectura se descarta por falta de rol.
- `total = empacadas + seleccionadas + sin_rol` en todas las filas y en los totales. Los KPIs y totales se calculan desde las mismas filas de la tabla para que nunca difieran.
- La eficiencia se calcula **por tarea del QR**: `horas_empacado` y `horas_seleccion` suman la duración de las lecturas de esa tarea (primera a última lectura de cada operador, sesión y día, mínimo 1 minuto). Así `empacadas_por_hora = empacadas / horas_empacado` y `seleccionadas_por_hora = seleccionadas / horas_seleccion`. `horas_activas` y `cajas_por_hora` siguen midiendo la sesión completa.
- El DNI, el nombre y el producto se resuelven desde `qr_emitidos` cuando el token existe, con respaldo en `scan_events.dni` y `raw`. Los filtros de lote se comparan con `TRIM(UPPER(...))`.

El tablero se **actualiza automáticamente cada 30 segundos** (modo tablero de TV estilo Plecto). El intervalo es configurable con `DASHBOARD_REFRESH_SECONDS`; el listado de lotes se cachea un minuto por sesión para reducir el tráfico al servidor en cada tic.

Endpoints (requieren token con rol ROOT, GERENCIA o SUPERVISOR):

| Ruta | Contenido |
|---|---|
| `GET /api/dashboard/cajas-por-dia` | Filas `dia, lote, total, empacadas, seleccionadas, sin_rol` |
| `GET /api/dashboard/cajas-por-hora` | Filas `hora, total, empacadas, seleccionadas, sin_rol` (hora de Perú) |
| `GET /api/dashboard/eficiencia-personal` | Filas por DNI con `empacadas`, `seleccionadas`, `sin_rol`, `horas_empacado`, `horas_seleccion`, `empacadas_por_hora`, `seleccionadas_por_hora`, `horas_activas`, `cajas_por_hora` y `rol_trabajador` |
| `GET /api/dashboard/eficiencia-por-dia` | Filas por día y DNI con `empacadas`, `seleccionadas` y `sin_rol` |
| `GET /api/dashboard/produccion-persona-lote` | Matriz persona × lote con `empacadas`, `seleccionadas` y `sin_rol` |
| `GET /api/dashboard/actividad-reciente` | Últimas lecturas (`lote_codigo` y `limit` opcionales) |

Las horas se almacenan como **UTC explícito** en `scanned_at` (normalizado al recibir el lote de la APK), de modo que la conversión a hora de Perú no depende de la zona horaria configurada en el servidor de base de datos.

## Eliminación masiva de lotes

Solo el usuario **ROOT** ve la grilla editable en la pestaña Lotes. Se seleccionan varios lotes con el checkbox `🗑️ Eliminar` y se confirma explícitamente antes de eliminar. La operación `POST /api/lotes/bulk-delete`:

- Elimina los lotes seleccionados **y sus lecturas asociadas** en una sola transacción.
- Rechaza IDs inexistentes (404), lotes sin selección (422) y roles distintos de ROOT (403).

## Pruebas

```bash
TEST_DATABASE_URL=postgresql+psycopg2://user@host/qr_lotes_test python -m pytest -q
```

Las pruebas verifican rankings, tablas y clasificación por código: un mismo DNI suma en empacado y selección, independientemente de su rol; las lecturas sin código clasificable caen en `sin_rol`, y los totales coinciden con la suma de la tabla (`tests/test_dashboard_api.py`, `tests/test_dashboard_streamlit.py`, `tests/test_shared_production_reports.py`).
