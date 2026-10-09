# Dashboard de producción y eliminación masiva de lotes

## Dashboard (`📈 Dashboard`)

Disponible para ROOT, GERENCIA y SUPERVISOR. Filtros: rango de fechas (hora de Perú) y lote.

Métricas generadas:

- **Cajas por día**: barras agrupadas por día (hora local `America/Lima`) con separación entre cajas empacadas (`emp`) y seleccionadas (`sel`) según el payload del QR (`raw.id` numérico = empacador, alfabético = seleccionador).
- **Cajas por lote**: total acumulado por código de lote en el rango.
- **Eficiencia del personal**: cajas por trabajador, con conteo empacadas/seleccionadas, días trabajados, sesiones y **cajas por hora activa**. Las horas activas se calculan desde la primera hasta la última lectura de cada sesión (mínimo 1 minuto por sesión).
- Serie **por día y persona** disponible en `/api/dashboard/eficiencia-por-dia`.

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
