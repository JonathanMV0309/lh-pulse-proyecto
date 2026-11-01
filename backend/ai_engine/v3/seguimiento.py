"""Seguimiento real: cada pronóstico publicado frente a la venta que ocurrió.

Solo lectura. Compara el P50 por tienda de cada ejecución publicada contra el
total cerrado del mes en ``compliance``. Es la medida honesta de precisión:
el WAPE de validación estima, este lo comprueba.
"""

import numpy as np
import pandas as pd
from sqlalchemy import text

from .historia import totales_cerrados


def evaluar_pronosticos(engine, compliance=None, limit=12):
    runs = pd.read_sql(text("""
        SELECT r.id AS run_id, r.anio, r.mes, r.model_version, r.created_at, r.wape AS wape_validacion
        FROM ai_v3_runs r
        WHERE r.status = 'SUCCESS'
          AND r.id IN (SELECT MAX(id) FROM ai_v3_runs WHERE status = 'SUCCESS' GROUP BY anio, mes)
        ORDER BY r.anio DESC, r.mes DESC
        LIMIT :limit
    """), engine, params={"limit": int(limit)})
    if runs.empty:
        return []
    forecasts = pd.read_sql(text("""
        SELECT run_id, store_id,
               SUM(venta_p10)::double precision AS p10,
               SUM(venta_p50)::double precision AS p50,
               SUM(venta_p90)::double precision AS p90
        FROM ai_v3_forecasts
        WHERE run_id = ANY(:ids)
        GROUP BY run_id, store_id
    """), engine, params={"ids": [int(value) for value in runs["run_id"]]})
    if compliance is None:
        from .data_sources import load_compliance_totals
        compliance = load_compliance_totals(engine)
    return resumir_seguimiento(runs, forecasts, totales_cerrados(compliance))


def resumir_seguimiento(runs, forecasts, closed_totals):
    """Calcula error, sesgo y cobertura del rango por ejecución."""
    results = []
    for run in runs.itertuples(index=False):
        rows = forecasts[forecasts["run_id"] == run.run_id]
        truth = closed_totals[
            (closed_totals["anio"] == int(run.anio)) & (closed_totals["mes"] == int(run.mes))
        ][["store_id", "venta_cerrada"]]
        merged = rows.merge(truth, on="store_id", how="inner")
        if merged.empty:
            continue
        actual = merged["venta_cerrada"].to_numpy(dtype=float)
        p50 = merged["p50"].to_numpy(dtype=float)
        inside = (actual >= merged["p10"].to_numpy(dtype=float)) & (actual <= merged["p90"].to_numpy(dtype=float))
        results.append({
            "run_id": int(run.run_id),
            "periodo": f"{int(run.anio)}-{int(run.mes):02d}",
            "version": run.model_version,
            "tiendas_evaluadas": int(len(merged)),
            "wape_real": float(np.abs(actual - p50).sum() / max(actual.sum(), 1.0)),
            "wape_validacion": None if pd.isna(run.wape_validacion) else float(run.wape_validacion),
            "sesgo_pct": float((p50.sum() / max(actual.sum(), 1.0) - 1) * 100),
            "cobertura_p10_p90": float(inside.mean()),
            "venta_real": float(actual.sum()),
            "venta_pronosticada": float(p50.sum()),
        })
    return results
