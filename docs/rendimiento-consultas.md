# Rendimiento de consultas de producción

## Problema reproducido

La consulta compartida usaba un `LEFT JOIN LATERAL` correlacionado para buscar
al trabajador de cada lectura:

```sql
WHERE TRIM(tw.dni) = TRIM(dni_resuelto)
ORDER BY tw.activo DESC, tw.id
LIMIT 1
```

El índice normal de DNI no cubre directamente `TRIM(dni)`. En los planes medidos,
PostgreSQL recorría `trabajadores` por cada lectura, incluso en el resumen por
operador, que no necesita nombres ni roles. La UI web solicita sucesivamente el
resumen por DNI y el resumen por operador, acumulando sus demoras.

## Corrección

- Resolver una única fila por DNI normalizado con `DISTINCT ON (TRIM(dni))`,
  conservando exactamente la prioridad `activo DESC, id`.
- Usar esa relación como lookup no correlacionado, en lugar de repetir la
  búsqueda por lectura.
- Omitir por completo trabajadores en el resumen por operador y los agregados
  del dashboard por día/lote y por hora.
- Mantener DNI/producto/código resueltos desde emisiones con sus respaldos
  anteriores, clasificación por código, filtros y lecturas sin clasificar.
- No cachear resultados ni modificar índices, esquema, roles o datos de producción.

## Comparación local

PostgreSQL 18 aislado, sin red externa; 265 trabajadores y 16.000/50.000 lecturas
sintéticas. Mediana de tres ejecuciones `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
por consulta y versión, después de cargar datos y ejecutar `ANALYZE`.
Se compararon las filas completas con la consulta anterior del commit `58bccd9`:
resultados idénticos en los seis casos.

| Lecturas | Consulta | Antes | Después |
|---:|---|---:|---:|
| 16.000 | Resumen por DNI, sin filtros | 1.687,681 ms | 61,649 ms |
| 16.000 | Resumen por DNI, lote y producto | 602,597 ms | 38,767 ms |
| 16.000 | Resumen por operador | 1.796,485 ms | 33,066 ms |
| 50.000 | Resumen por DNI, sin filtros | 4.592,462 ms | 203,043 ms |
| 50.000 | Resumen por DNI, lote y producto | 1.689,444 ms | 102,934 ms |
| 50.000 | Resumen por operador | 4.464,782 ms | 108,541 ms |

En el resumen completo de 16.000 lecturas, los recorridos de trabajadores bajaron
de 16.000 a uno y los bloques compartidos encontrados en caché bajaron de 64.355
a 359. El resumen por operador nuevo no accede a trabajadores.

Estos resultados son locales, no tiempos prometidos para producción. El servidor
puede añadir demoras por disco lleno, memoria/swap, bloqueos, conexiones o red.
No se ha obtenido un plan de ejecución ni una medición de extremo a extremo del
servidor desplegado.

## Regresión

155 pruebas Python aprobadas. Se verifica además que DNIs equivalentes con
espacios no multipliquen lecturas y sigan eligiendo al trabajador prioritario.
Los agregados que no muestran nombres deben solicitar
`production_cte(include_workers=False)`.

La corrección necesita desplegar backend. No requiere reinstalar la APK, cambiar
la fuente Arial ni modificar el Print Agent.
