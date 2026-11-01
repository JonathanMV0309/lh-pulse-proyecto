# Inteligencia Predictiva L&H V3

V3 pronostica el siguiente mes para cada tienda y línea usando ventas, tráfico,
facturas, calendario colombiano y dimensiones de tienda. Publica intervalos
P10/P50/P90, conversión, ticket, metas recomendadas, probabilidad de cumplimiento
y alertas. El panel permite comparar hasta cuatro tiendas.

Desde V3.1 las compras se derivan de `tráfico × conversión validada`. Se excluyen
meses imposibles donde las facturas superan el tráfico, evitando conversiones
mayores al 100% y tickets artificialmente bajos.

## Novedades de lh-v3.3 (precisión)

Backtest con datos reales, marzo–agosto 2026, error por tienda (WAPE) frente
al total cerrado de `compliance`, sin la fila "TOTAL": **23,2% → 15,7%**; error
del total de la red **19,2% → 10,2%**. Tal como corría en producción (con la
fila TOTAL dentro de la referencia de la red) el error era 44,2%.

0. **Fila TOTAL excluida.** Los archivos traen una fila "TOTAL" de la red que
   se guarda como tienda. Antes entraba en la referencia de la red, la
   duplicaba y la reconciliación inflaba el pronóstico. Ahora el motor usa solo
   tiendas activas en todos los pasos.

1. **Histórico limpio** (`v3/historia.py`). `sales_history_lines` guarda el
   acumulado al día del último archivo (los tableros lo necesitan así). Para
   entrenar, el motor toma el total cerrado por tienda/mes de `compliance` como
   verdad y del histórico solo la proporción entre líneas. Así corrige meses
   parciales (un corte del día 6 sobre un cierre), meses inflados, mezclas de
   líneas con columnas corridas y años mal etiquetados (archivos de 2025
   guardados como 2026 por el importador anterior). No modifica la base.
2. **Importador corregido.** Usa el año del archivo (antes 2025/2026 fijos) y
   no deja que un archivo más viejo pise un corte más avanzado del mismo mes.
3. **Corte real y horizonte.** Si el último mes no tiene cobertura, usa el
   anterior completo y pronostica a 2 meses sin mirar datos posteriores.
4. **Validación mes a mes** (6 meses) y **reentrenamiento con todo** el
   histórico antes de pronosticar.
5. **Referencia estacional × crecimiento** (mismo mes del año pasado por el
   crecimiento de los últimos 3 meses), también en la reconciliación: ya no se
   subestiman diciembre, mayo o junio.
6. **Gradient boosting con pérdida Poisson**: pondera las tiendas por tamaño,
   igual que el WAPE. Solo recibe peso si le gana a las referencias.
7. **Calendario colombiano comercial**: Día de la Madre y del Padre, Amor y
   Amistad, Black Friday, prima, Semana Santa, puentes y quincenas en fin de
   semana.
8. **Intervalos propios por tienda/línea** a partir de los errores fuera de
   muestra (asimétricos), y probabilidad de meta calibrada.
9. **Nowcast con curva diaria** (`daily_store_sales`): proyecta lo que falta
   del mes con la fracción que la tienda suele llevar vendida a ese día.
10. **Tráfico y facturas solo de meses completos**; si el sensor horario quedó
    corto se usa el cierre oficial.
11. **Seguimiento real**: `python -m ai_engine.v3.run --evaluar` compara cada
    pronóstico publicado con la venta cerrada. El diagnóstico de cada ejecución
    incluye `data_quality`, `data_cutoff`, `tracking` y el error por mes.

## Por qué evita pronósticos incompletos

- Exige la cobertura configurada de tiendas por líneas para el mes de corte.
- Compara un modelo de gradiente con referencias estacionales y recientes.
- Los pesos se eligen con validación temporal; un modelo peor se descarta.
- Reconcilia líneas, tiendas y total de red contra una referencia independiente.
- Si falla un control, no publica ni reemplaza el último resultado válido.
- Cada ejecución queda guardada con versión, WAPE, cobertura y diagnóstico JSON.

## Instalación en el servidor

Desde `C:\Proyectos\LH_SCORE\backend`, con el entorno virtual activado:

```powershell
python -m pip install -r ai_engine\requirements-ai-v3.txt
python -m flask --app run db upgrade
python -m ai_engine.v3.run --validar
python -m ai_engine.v3.run
python -m ai_engine.v3.run --evaluar
python -m flask --app run run --host=0.0.0.0
```

También puede generarse desde el botón **Generar V3** de `/ai/`. La primera
ejecución debe hacerse por consola para ver el diagnóstico completo.

## Fecha de corte

Por defecto usa el último mes calendario terminado. Para forzar un corte:

```env
AI_DATA_CUTOFF=202608
AI_V3_VALIDATION_MONTHS=6
AI_V3_MIN_COVERAGE=0.95
```

La cobertura se mide sobre las combinaciones tienda/línea que vendieron en los
últimos 12 meses (una tienda que nunca vende una línea no cuenta como
faltante). Si el mes de corte no llega al mínimo, se usa el mes anterior
completo y el diagnóstico lo indica en `data_cutoff`.

## Turismo, clima, eventos y promociones

Son fuentes opcionales y nunca se inventan. Copie el ejemplo:

`ai_engine/data/external/city_month_features.example.csv`

como:

`ai_engine/data/external/city_month_features.csv`

y agregue una fila por ciudad/mes. Los índices deben conservar la misma escala
entre meses. Si el archivo no existe, o falta un mes, esas variables quedan
vacías (no en cero) y el diagnóstico muestra `external_features_loaded: false`.

## Interpretación

- **P10:** escenario prudente.
- **P50:** pronóstico central.
- **P90:** escenario alto.
- **Confianza:** `1 - WAPE` de la validación temporal; no es una garantía.
- **Probabilidad de meta:** aproximación basada en P10–P90 y la meta efectiva.

## Reversión

V3 escribe en tablas nuevas y mantiene las tablas V2 por compatibilidad. Para
volver al código anterior, restaure los dos archivos reemplazados
`ai_engine/api/routes_ai.py` y `app/templates/ai_dashboard.html`. No es necesario
borrar los datos V3.
