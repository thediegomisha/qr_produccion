# Dashboard de producción y eliminación masiva de lotes

## Dashboard (`📈 Dashboard`)

Disponible para ROOT, GERENCIA y SUPERVISOR. Filtros: rango de fechas (hora de Perú) y lote, con **atajos de rango** (Hoy, 7 días, 30 días, 90 días) sobre los selectores de fecha.

Si el rango seleccionado no tiene lecturas pero el servidor sí registra lecturas en otras fechas, el dashboard indica la **fecha de la última lectura registrada** y ofrece un botón para saltar directamente a ese día. Si el servidor aún no tiene lecturas, guía al usuario hacia la impresión y el escaneo con la APK.

El diseño sigue el modelo de tableros estilo Plecto (números grandes en tarjetas, ranking del personal y visuales limpios), recreado en Streamlit:

1. **Tarjetas KPI** con números grandes y acentos de color. La primera es **Cajas empacadas** — la métrica de producción y base para formar pallets — seguida de Selección, Lecturas totales, Personas activas y Días trabajados.
2. **Gráfica principal: Cajas empacadas por lote** — barras por código de lote con las **empacadas** al frente (color sólido) y la **selección** al lado en tono claro, solo como referencia: son dos conceptos distintos. Tabla resumen con empacadas en primer lugar.
3. **Distribución (donut)** — proporción empacadas/selección con las empacadas al centro.
4. **Ritmo por hora del día** — barras por hora (hora de Perú) separando empacadas y selección, con hora pico de empacado.
5. **Tendencia de empacadas vs meta** — línea de empacadas/día con meta configurable (`Meta empacadas/día`) y % de avance sobre el promedio.
6. **Empacadas por persona y lote (heatmap)** — matriz de intensidad basada en cajas empacadas (la selección aparece en el tooltip).
7. **Eficiencia del personal** — ranking por **cajas empacadas** estilo leaderboard con medallas 🥇🥈🥉 para el top 3; cada fila muestra las empacadas como número principal y la selección como referencia, más la gráfica de empacadas/hora y la tabla completa.
8. **Actividad reciente** — últimas 10 lecturas en vivo (hora local, persona, lote, tipo).
9. **Cajas por día (vista secundaria)** — dentro de un panel desplegable al final; distribución diaria de empacadas/seleccionadas para revisión puntual.

El tablero se **actualiza automáticamente cada 30 segundos** (modo tablero de TV estilo Plecto). El intervalo es configurable con `DASHBOARD_REFRESH_SECONDS`; el listado de lotes se cachea un minuto por sesión para reducir el tráfico al servidor en cada tic.

Endpoints (requieren token con rol ROOT, GERENCIA o SUPERVISOR):

| Ruta | Contenido |
|---|---|
| `GET /api/dashboard/cajas-por-dia` | Filas `dia, lote, total, empacadas, seleccionadas` |
| `GET /api/dashboard/cajas-por-hora` | Filas `hora, total, empacadas, seleccionadas` (hora de Perú) |
| `GET /api/dashboard/eficiencia-personal` | Filas por DNI con totales y `cajas_por_hora` |
| `GET /api/dashboard/eficiencia-por-dia` | Filas por día y DNI |
| `GET /api/dashboard/produccion-persona-lote` | Matriz persona × lote para el heatmap |
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

Las pruebas del dashboard verifican el orden de las secciones (lote primero, día como secundaria), los valores de las tarjetas KPI, el ranking con medallas y las tablas por lote y por persona.
