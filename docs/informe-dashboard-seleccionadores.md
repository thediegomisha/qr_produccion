# Informe: el dashboard no mostraba seleccionadores

**Fecha:** 2026-11-14
**Proyecto:** `qr_produccion_main_sync`
**Alcance:** ranking de eficiencia del personal en el dashboard
**Estado:** corregido (backend + UI + pruebas)

> **Actualización 2026-11-16 — regla de clasificación reemplazada.** Por decisión
> de operaciones se adoptó la **Opción A**: la tarea de una lectura se toma del
> **rol registrado** del trabajador (`trabajadores.rol`), no de la forma del código
> impreso. `EMPACADOR`/`EMPACADORA` cuenta como empacado y `SELECCIONADOR` como
> selección; las lecturas sin rol se agrupan en `sin_rol`. Este informe se conserva
> como registro histórico del incidente; la regla vigente está documentada en
> [`dashboard.md`](dashboard.md#tarea-y-rol-el-rol-registrado-define-la-tarea).

## 1. Resumen ejecutivo

El dashboard no mostraba seleccionadores por un problema **de presentación**, no de
clasificación. La regla de negocio es correcta y se mantiene: **el tipo de QR define
la tarea** — número de orden = empacado, código de letra = selección — y una misma
persona puede desempeñar ambas tareas, incluso cambiando de una a otra dentro de la
misma jornada.

La causa fue que la sección "Eficiencia del personal":

1. ordenaba únicamente por `empacadas` y mostraba el **top 10**, y
2. graficaba y tabulaba solo `empacadas`.

Como el volumen de empacado es mucho mayor, un seleccionador (o quien solo seleccionó
ese día) quedaba fuera del top 10 con `empacadas = 0` y su barra valía cero.

Además, la eficiencia se calculaba sobre las **horas activas de la sesión completa**.
Cuando una persona empaca y luego selecciona en la misma sesión, ese tiempo se
repartía entre ambas tareas y distorsionaba el ritmo de cada una.

## 2. Fuentes revisadas

- `backend/app/api/routes_dashboard.py` — consulta y endpoints del dashboard.
- `ui_web/app_modules/modules/dashboard_page.py` — ranking, gráficas y exportación.
- `ui_web/app_modules/modules/impresion_page.py` — origen del campo `id` del QR.
- `backend/app/services/qr_service.py` y `backend/app/api/routes_qr.py` — payload.
- `backend/app/api/routes_trabajadores.py` — campo `rol` (rol registrado).
- `tests/test_dashboard_api.py` y `tests/test_dashboard_streamlit.py`.
- Datos reales: `dump-qr_produccion-202607201705.sql`
  (23 693 lecturas, 53 lotes, 566 trabajadores, 06/01/2026 a 05/07/2026).

## 3. Regla vigente (confirmada con operaciones)

| Contenido del QR (`raw.id`) | Tarea |
|---|---|
| Empieza con dígito (número de orden, ej. `127`) | **Empacado** |
| Empieza con letra (código de letra, ej. `EUZ`) | **Selección** |

- El campo `id` del payload es el texto visible impreso en el centro del QR; el
  operador elige entre "Número de orden" y "Código de letra" al imprimir.
- Por tanto la tarea se deduce del **QR escaneado**, no de `trabajadores.rol`.
  Ese campo es solo el **rol registrado** del trabajador y se muestra como
  referencia (columna `rol_registrado`).
- Una persona puede tener lecturas numéricas y alfabéticas: aparece en los dos
  rankings, con sus propias cifras en cada uno.

## 4. Evidencia en datos reales

### 4.1 Totales del periodo

| Métrica | Valor |
|---|---:|
| Lecturas totales | 23 693 |
| `id` numérico → empacadas | 22 822 |
| `id` alfabético → seleccionadas | 871 |
| DNIs distintos con lecturas | 100 |
| Trabajadores registrados | 566 (559 EMPACADORA, 7 SELECCIONADOR) |

### 4.2 Personas con lecturas de selección

| DNI | Nombre | Rol registrado | Empacadas | Seleccionadas | Total |
|---|---|---|---:|---:|---:|
| 46665592 | CARLOS | EMPACADORA | 162 | **265** | 427 |
| 76302889 | ERIKA RUBI | EMPACADORA | 78 | **184** | 262 |
| 47554750 | EPIFANIA MARIBEL | EMPACADORA | 77 | **165** | 242 |
| 60971203 | JHORDAN JHAMIR | EMPACADORA | 0 | **139** | 139 |
| 46593792 | CHARY LEISY | EMPACADORA | 102 | **109** | 211 |
| 70832316 | YERSON CLAUDIO | EMPACADORA | 0 | **8** | 8 |
| 45525359 | LUIS JAVIER | EMPACADORA | 3 | **1** | 4 |

Los siete están registrados como EMPACADORA y aun así tienen lecturas alfabéticas:
es exactamente el caso de **cambio de tarea**, no un error de datos.

### 4.3 Por qué desaparecían

- **JHORDAN JHAMIR**: 139 cajas, todas con código de letra → `empacadas = 0`.
  Con el ranking anterior no aparecía en ninguna parte.
- **CARLOS**: 162 empacadas (fuera del top 10, que cerraba en ~699) y 265
  seleccionadas (nunca graficadas). Invisible en ambos rankings.
- El top 10 anterior era 100 % empacadoras puras; la selección solo aparecía como
  texto secundario en filas que casi nunca se mostraban.

## 5. Cambios aplicados

### 5.1 Backend — `eficiencia-personal`

Se agregaron horas y ritmo **por tarea**, manteniendo `horas_activas` y
`cajas_por_hora` de la sesión completa:

- `horas_empacado` / `horas_seleccion`: suma de la duración de cada bloque de
  tarea (primera a última lectura de esa tarea por sesión y día, mínimo 1 minuto).
- `empacadas_por_hora = empacadas / horas_empacado`.
- `seleccionadas_por_hora = seleccionadas / horas_seleccion`.

La CTE `tareas` agrupa por `(dni, session_uuid, dia, es_empacador)`, de modo que un
cambio de tarea dentro de la misma sesión genera dos bloques independientes.

### 5.2 UI — ranking por tarea

- Nuevo selector **`Ranking de: Empacadoras / Seleccionadores`**
  (`st.radio`, clave `dash_ranking_rol`).
- El ranking filtra `empacadas > 0` o `seleccionadas > 0` según la vista, así que
  un seleccionador no compite contra el volumen de empacado.
- Título y eje dinámicos: "Cajas empacadas por persona" / "Cajas seleccionadas por
  persona", con color propio para selección.
- La tabla completa (y la exportación a Excel/impresión) muestra **ambas tareas** y
  las nuevas columnas: `horas_empacado`, `horas_seleccion`, `empacadas_por_hora`,
  `seleccionadas_por_hora`, con `rol_trabajador` renombrado a `rol_registrado`.
- Se eliminó el cálculo local `empacadas / horas_activas`, que ahora viene del API.

## 6. Verificación

```bash
TEST_DATABASE_URL=postgresql+psycopg2://user@host/qr_lotes_test python -m pytest -q
```

Resultado: **97 pruebas aprobadas**, incluidas las nuevas:

- `test_eficiencia_personal_separa_horas_por_tarea_en_una_misma_sesion`:
  2 empacadas + 2 seleccionadas en la misma sesión → 1 h por tarea,
  2 cajas/hora en cada una, 3 h activas totales.
- `test_eficiencia_personal_mantiene_a_quien_solo_selecciona`: `empacadas = 0`,
  `seleccionadas = 2`, ritmo de selección calculado.
- `test_dashboard_selector_ranking_uses_qr_type_as_task`: la vista
  "Seleccionadores" muestra "Cajas seleccionadas por persona" y las cajas de quien
  empacó y luego seleccionó.

## 7. Observaciones pendientes

1. **Trabajadores desactivados:** los `JOIN` usan `t.activo = true`; al desactivar
   personal, sus lecturas históricas pasan a "SIN REGISTRO". En la muestra actual
   hay 0 afectados. Conviene resolver el nombre por DNI sin filtrar por estado.
2. **Seleccionadores sin lecturas:** 6 de los 7 trabajadores registrados como
   SELECCIONADOR no tienen ningún escaneo. Es un tema operativo: no se imprimen
   etiquetas a su nombre, no escanean, o escanean etiquetas de otra persona (la
   lectura se atribuye al DNI del QR).
3. **Reportes:** `routes_reports.py` aplica la misma regla de tipo de QR, por lo que
   es consistente con el dashboard.

## 8. Anexo: consulta de verificación

```sql
SELECT
    (se.raw->>'id') ~ '^[0-9]' AS es_empacado,
    COUNT(*) AS lecturas,
    COUNT(DISTINCT se.dni) AS personas
FROM scan_events se
GROUP BY 1
ORDER BY 1 DESC;
```

Y para ver el cambio de tarea por persona:

```sql
SELECT
    se.dni,
    COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[0-9]') AS empacadas,
    COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]') AS seleccionadas
FROM scan_events se
GROUP BY se.dni
HAVING COUNT(*) FILTER (WHERE (se.raw->>'id') ~ '^[A-Za-z]') > 0
ORDER BY seleccionadas DESC;
```
