# Dashboard de producción y eliminación masiva de lotes

## Dashboard (`📈 Dashboard`)

Disponible para ROOT, GERENCIA y SUPERVISOR. Filtros: rango de fechas (hora de Perú) y lote.

El diseño sigue el modelo de tableros estilo Plecto (números grandes en tarjetas, ranking del personal y visuales limpios), recreado en Streamlit:

1. **Tarjetas KPI** con números grandes y acentos de color: Cajas totales, Empacadas, Seleccionadas, Personas activas y Días trabajados.
2. **Gráfica principal: Cajas por lote** — barras apiladas horizontales por código de lote, separando cajas **empacadas** (`raw.id` numérico) y **seleccionadas** (`raw.id` alfabético), con tabla resumen debajo.
3. **Eficiencia del personal** — ranking estilo leaderboard con medallas 🥇🥈🥉 para el top 3, cajas totales y cajas/hora de cada trabajador. La eficiencia se calcula como cajas por hora activa (primera a última lectura de cada sesión, mínimo 1 minuto), seguida de la gráfica de cajas/hora y la tabla completa.
4. **Cajas por día (vista secundaria)** — dentro de un panel desplegable al final; distribución diaria de empacadas/seleccionadas para revisión puntual.

Endpoints (requieren token con rol ROOT, GERENCIA o SUPERVISOR):

| Ruta | Contenido |
|---|---|
| `GET /api/dashboard/cajas-por-dia` | Filas `dia, lote, total, empacadas, seleccionadas` |
| `GET /api/dashboard/eficiencia-personal` | Filas por DNI con totales y `cajas_por_hora` |
| `GET /api/dashboard/eficiencia-por-dia` | Filas por día y DNI |

## Eliminación masiva de lotes

Solo el usuario **ROOT** ve la grilla editable en la pestaña Lotes. Se seleccionan varios lotes con el checkbox `🗑️ Eliminar` y se confirma explícitamente antes de eliminar. La operación `POST /api/lotes/bulk-delete`:

- Elimina los lotes seleccionados **y sus lecturas asociadas** en una sola transacción.
- Rechaza IDs inexistentes (404), lotes sin selección (422) y roles distintos de ROOT (403).

## Pruebas

```bash
TEST_DATABASE_URL=postgresql+psycopg2://user@host/qr_lotes_test python -m pytest -q
```

Las pruebas del dashboard verifican el orden de las secciones (lote primero, día como secundaria), los valores de las tarjetas KPI, el ranking con medallas y las tablas por lote y por persona.
