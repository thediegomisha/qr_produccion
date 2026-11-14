# Dashboard de producción y eliminación masiva de lotes

## Dashboard (`📈 Dashboard`)

Disponible para ROOT, GERENCIA y SUPERVISOR. Filtros: rango de fechas (hora de Perú) y lote, con **atajos de rango** (Hoy, 7 días, 30 días, 90 días) sobre los selectores de fecha.

Si el rango seleccionado no tiene lecturas pero el servidor sí registra lecturas en otras fechas, el dashboard indica la **fecha de la última lectura registrada** y ofrece un botón para saltar directamente a ese día. Si el servidor aún no tiene lecturas, guía al usuario hacia la impresión y el escaneo con la APK.

El diseño sigue el modelo de tableros estilo Plecto (números grandes en tarjetas, ranking del personal y visuales limpios), recreado en Streamlit:

1. **Tarjetas KPI** con números grandes y acentos de color. La primera es **Cajas empacadas** — la métrica de producción y base para formar pallets — seguida de Selección, Lecturas totales, Personas activas y Días trabajados.
2. **Gráfica principal: Cajas empacadas por lote** — barras por código de lote con las **empacadas** al frente (color sólido) y la **selección** al lado en tono claro. Tabla resumen con empacadas en primer lugar.
3. **Distribución (donut)** — proporción empacadas/selección con las empacadas al centro, junto al **Ritmo por hora del día**: barras por hora (hora de Perú) separando empacadas y selección, con hora pico de empacado.
4. **Eficiencia del personal** — ranking estilo leaderboard con medallas 🥇🥈🥉 y un selector **Ranking de: Empacadoras / Seleccionadores**. Ver [tarea y rol](#tarea-y-rol-el-tipo-de-qr-define-la-tarea).
5. **Exportar dashboard** — Excel (hojas Resumen, Por lote y Por persona) e impresión, con la tabla completa del personal.
6. **Actividad reciente** — últimas 10 lecturas en vivo (hora local, persona, lote, tipo).

### Tarea y rol: el tipo de QR define la tarea

Una misma persona puede desempeñarse como empacadora o seleccionadora durante la jornada, e incluso cambiar de tarea a mitad de sesión (primero empaca, luego selecciona). Por eso la tarea **no** se toma de `trabajadores.rol` ni del nombre del trabajador, sino del **tipo de QR escaneado**:

| Contenido del QR (`raw.id`) | Tarea |
|---|---|
| Empieza con dígito (número de orden, ej. `127`) | **Empacado** |
| Empieza con letra (código de letra, ej. `EUZ`) | **Selección** |

Consecuencias en el dashboard:

- El ranking tiene dos vistas. **Empacadoras** ordena por `empacadas` y **Seleccionadores** por `seleccionadas`; solo aparece quien tiene al menos una caja de esa tarea, de modo que un seleccionador no queda oculto detrás del mayor volumen de empacado.
- Una persona con ambas tareas aparece en los dos rankings, con sus propias cifras en cada uno.
- `trabajadores.rol` se muestra solo como **rol registrado** (columna `rol_registrado`), no como la tarea realizada.
- La eficiencia se calcula **por tarea**: `horas_empacado` y `horas_seleccion` suman la duración de cada bloque de tarea (primera a última lectura de esa tarea en cada sesión y día, mínimo 1 minuto). Así `empacadas_por_hora = empacadas / horas_empacado` y `seleccionadas_por_hora = seleccionadas / horas_seleccion`. `horas_activas` y `cajas_por_hora` siguen midiendo la sesión completa.

El tablero se **actualiza automáticamente cada 30 segundos** (modo tablero de TV estilo Plecto). El intervalo es configurable con `DASHBOARD_REFRESH_SECONDS`; el listado de lotes se cachea un minuto por sesión para reducir el tráfico al servidor en cada tic.

Endpoints (requieren token con rol ROOT, GERENCIA o SUPERVISOR):

| Ruta | Contenido |
|---|---|
| `GET /api/dashboard/cajas-por-dia` | Filas `dia, lote, total, empacadas, seleccionadas` |
| `GET /api/dashboard/cajas-por-hora` | Filas `hora, total, empacadas, seleccionadas` (hora de Perú) |
| `GET /api/dashboard/eficiencia-personal` | Filas por DNI con `empacadas`, `seleccionadas`, `horas_empacado`, `horas_seleccion`, `empacadas_por_hora`, `seleccionadas_por_hora`, `horas_activas`, `cajas_por_hora` y `rol_trabajador` |
| `GET /api/dashboard/eficiencia-por-dia` | Filas por día y DNI |
| `GET /api/dashboard/produccion-persona-lote` | Matriz persona × lote |
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

Las pruebas del dashboard verifican el orden de las secciones, los valores de las tarjetas KPI, el ranking con medallas y las tablas por lote y por persona. Además cubren la regla de tarea por tipo de QR: horas y ritmo calculados por tarea cuando una persona empaca y luego selecciona en la misma sesión, y el ranking de seleccionadores mostrando a quien solo selecciona (`tests/test_dashboard_api.py`, `tests/test_dashboard_streamlit.py`).
