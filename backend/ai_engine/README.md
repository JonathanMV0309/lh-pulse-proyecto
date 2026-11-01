# Motor de pronóstico L&H SCORE — versión 2

Este motor pronostica **ventas mensuales en pesos por tienda y línea**. No
pronostica el precio de productos individuales.

## Cambios de la versión 2

- Corrige la lectura de `INF4`: los meses se detectan desde los encabezados.
- Da prioridad a la base de datos cuando el histórico se solapa con datos actuales.
- Impide claves tienda-línea-mes duplicadas.
- Calcula rezagos por mes calendario, incluso cuando hay meses faltantes.
- Usa estacionalidad cíclica, rezagos 1/2/3/6/12 y media móvil de 3 meses.
- Entrena sobre `log1p(venta)` y nunca entrega ventas negativas.
- Ejecuta backtesting rodante contra un baseline temporal.
- No publica un modelo que no supere la compuerta mínima de calidad.
- Entrega intervalos P10–P90 orientativos.
- Calcula cumplimiento únicamente con meta oficial y error histórico validado.
- Guarda XGBoost en JSON para evitar incompatibilidades de `joblib`.

## Instalación

```powershell
pip install -r ai_engine/requirements-ai.txt
```

Variables opcionales:

```dotenv
# Último mes cerrado. Si se omite, usa automáticamente el mes anterior.
AI_DATA_CUTOFF=202608

# Mejora mínima contra baseline, por defecto 2%.
AI_MIN_MODEL_IMPROVEMENT=0.02
```

No configure `AI_ALLOW_UNVALIDATED_MODEL=1` en producción. Solamente existe
para diagnósticos controlados.

## Pipeline completo

```powershell
python -m ai_engine.pipelines.extract
python -m ai_engine.pipelines.importar_historico
python -m ai_engine.pipelines.importar_historico_lineas
python -m ai_engine.pipelines.preparar_dataset_ampliado
python -m ai_engine.pipelines.train_ampliado
python -m ai_engine.pipelines.predict_ampliado
python -m ai_engine.pipelines.predict_compliance
python -m ai_engine.pipelines.guardar_predicciones_ampliadas
python -m ai_engine.pipelines.guardar_cumplimiento
```

El botón `/ai/reentrenar` ejecuta este mismo orden.

## Pruebas

```powershell
python -m unittest discover -s ai_engine/tests -v
```

## Visualización de probabilidades ausentes

En `ai_dashboard.html`, una probabilidad `None` significa que no existe meta
oficial. Debe mostrarse así:

```jinja2
{% if fila.probabilidad is not none %}
  {{ "%.1f"|format(fila.probabilidad * 100) }}%
{% else %}
  No disponible · sin meta oficial
{% endif %}
```

No debe convertirse `venta_predicha / meta_estimada` en una probabilidad.
