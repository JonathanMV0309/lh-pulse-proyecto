"""Controles de cobertura y reconciliación jerárquica tienda/línea/red."""

import numpy as np
import pandas as pd


def expected_coverage(sales, entities, cutoff_year, cutoff_month):
    expected = len(entities.drop_duplicates(["store_id", "line_id"]))
    current = sales[
        (sales["anio"].astype(int) == int(cutoff_year))
        & (sales["mes"].astype(int) == int(cutoff_month))
    ][["store_id", "line_id"]].drop_duplicates()
    return (len(current) / expected if expected else 0.0), expected, len(current)


def _store_reference(sales, cutoff_year, cutoff_month, forecast_year=None, forecast_month=None):
    """Referencia independiente por tienda: mismo mes del año pasado × crecimiento.

    El crecimiento compara los últimos 3 meses conocidos contra esos mismos
    meses del año anterior. Antes se mezclaba el promedio de los últimos 3
    meses sin ajuste de temporada, lo que arrastraba hacia abajo diciembre,
    junio o mayo.
    """
    frame = sales.copy()
    dates = pd.to_datetime({
        "year": frame["anio"].astype(int),
        "month": frame["mes"].astype(int),
        "day": 1,
    })
    frame["period"] = dates.dt.to_period("M")
    cutoff = pd.Period(f"{cutoff_year}-{cutoff_month:02d}", freq="M")
    if forecast_year is None:
        target = cutoff + 1
    else:
        target = pd.Period(f"{forecast_year}-{forecast_month:02d}", freq="M")
    store_month = frame.groupby(["store_id", "period"], as_index=False)["venta"].sum()
    references = []
    for store_id, group in store_month.groupby("store_id"):
        values = group.set_index("period")["venta"].sort_index()
        values = values[values.index <= cutoff]
        seasonal = float(values.get(target - 12, np.nan))
        recent_periods = [cutoff - offset for offset in range(3)]
        recent = [values.get(period, np.nan) for period in recent_periods]
        last_year = [values.get(period - 12, np.nan) for period in recent_periods]
        growth = np.nan
        if np.isfinite(recent).all() and np.isfinite(last_year).all() and sum(last_year) > 0:
            growth = float(np.clip(sum(recent) / sum(last_year), 0.5, 2.0))
        recent_mean = float(np.nanmean(recent)) if np.isfinite(recent).any() else np.nan
        if np.isfinite(seasonal):
            reference = seasonal * (growth if np.isfinite(growth) else 1.0)
        elif np.isfinite(recent_mean):
            reference = recent_mean
        else:
            continue
        references.append({"store_id": store_id, "reference": max(float(reference), 0.0)})
    return pd.DataFrame(references, columns=["store_id", "reference"])


def reconcile_sales(forecasts, sales, config, cutoff=None, forecast_period=None):
    """Conserva la mezcla por línea pero impide totales incompletos o absurdos."""
    result = forecasts.copy()
    cutoff = cutoff or (config.cutoff_year, config.cutoff_month)
    forecast_period = forecast_period or config.forecast_period
    references = _store_reference(sales, cutoff[0], cutoff[1], *forecast_period)
    # La referencia de la red solo suma las tiendas que se pronostican (nunca
    # una fila "TOTAL" ni tiendas inactivas presentes en el histórico).
    references = references[references["store_id"].isin(set(result["store_id"]))]
    result = result.merge(references, on="store_id", how="left")
    result["reference"] = result["reference"].fillna(0.0)

    bottom_up = result.groupby("store_id")["p50"].transform("sum")
    # El ancla combina la señal de líneas con la referencia independiente de tienda.
    anchor = 0.70 * bottom_up + 0.30 * result["reference"]
    lower = result["reference"] * config.total_ratio_min
    upper = result["reference"] * config.total_ratio_max
    anchor = np.where(result["reference"] > 0, np.clip(anchor, lower, upper), bottom_up)

    line_count = result.groupby("store_id")["line_id"].transform("count").clip(lower=1)
    fallback_share = 1.0 / line_count
    shares = np.where(bottom_up > 0, result["p50"] / bottom_up, fallback_share)
    reconciled = np.maximum(anchor * shares, 0.0)
    factor = np.divide(reconciled, result["p50"], out=np.ones(len(result)), where=result["p50"] > 0)
    for column in ("p10", "p50", "p90"):
        result[column] = np.maximum(result[column] * factor, 0.0)

    network_reference = float(references["reference"].sum()) if not references.empty else 0.0
    network_total = float(result["p50"].sum())
    ratio = network_total / network_reference if network_reference > 0 else 1.0
    fallback_used = False
    if network_reference > 0 and not (config.total_ratio_min <= ratio <= config.total_ratio_max):
        fallback_used = True
        network_anchor = float(np.clip(network_total, network_reference * config.total_ratio_min,
                                       network_reference * config.total_ratio_max))
        network_factor = network_anchor / max(network_total, 1.0)
        for column in ("p10", "p50", "p90"):
            result[column] *= network_factor
        network_total = float(result["p50"].sum())

    diagnostics = {
        "reference_total": network_reference,
        "forecast_total": network_total,
        "forecast_reference_ratio": network_total / network_reference if network_reference else None,
        "fallback_used": fallback_used,
    }
    return result.drop(columns=["reference"]), diagnostics
