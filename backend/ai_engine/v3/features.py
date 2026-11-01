import math

import numpy as np
import pandas as pd

from .calendar_co import CALENDAR_COLUMNS, month_calendar_features


# Rezagos en meses respecto al mes pronosticado. Con horizonte h solo se usan
# los rezagos >= h (pronóstico directo: nunca se mira un mes que aún no se
# conoce en la fecha de corte).
LAGS = (1, 2, 3, 6, 12, 13, 14, 15, 24)
ROLLING_WINDOWS = (3, 6, 12)
EXTERNAL_COLUMNS = (
    "tourism_index", "temperature_avg", "rain_mm",
    "event_index", "promotion_index",
)
GROWTH_CLIP = (0.35, 2.8)


def add_period(frame):
    result = frame.copy()
    dates = pd.to_datetime({
        "year": result["anio"].astype(int),
        "month": result["mes"].astype(int),
        "day": 1,
    })
    result["period"] = dates.dt.to_period("M")
    return result


def complete_panel(history, entities, keys, target, start_period, end_period):
    periods = pd.period_range(start=start_period, end=end_period, freq="M")
    left = entities[keys].drop_duplicates().assign(_join=1)
    right = pd.DataFrame({"period": periods, "_join": 1})
    panel = left.merge(right, on="_join").drop(columns="_join")
    source = add_period(history)
    panel = panel.merge(source[keys + ["period", target]], on=keys + ["period"], how="left")
    panel["anio"] = panel["period"].dt.year.astype(int)
    panel["mes"] = panel["period"].dt.month.astype(int)
    return panel


def _ratio(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    ratio = numerator / denominator.where(denominator > 0)
    return ratio.clip(*GROWTH_CLIP)


def add_lag_features(panel, keys, target, horizon=1):
    """Rezagos, medias móviles y crecimiento interanual con horizonte ``horizon``.

    Todas las ventanas terminan ``horizon`` meses antes del mes pronosticado,
    así las mismas columnas sirven para entrenar y para pronosticar.
    """
    horizon = max(int(horizon), 1)
    result = panel.sort_values(keys + ["period"]).copy()
    grouped = result.groupby(keys, observed=True, sort=False)[target]
    lags = {}
    for lag in sorted(set(LAGS) | set(range(horizon, horizon + 3)) | set(range(horizon + 12, horizon + 15))):
        if lag < horizon:
            continue
        lags[lag] = grouped.shift(lag)
        if lag in LAGS:
            result[f"{target}_lag_{lag}"] = lags[lag]

    base = lags[horizon]
    group_keys = [result[key] for key in keys]
    for window in ROLLING_WINDOWS:
        rolling = base.groupby(group_keys, observed=True)
        result[f"{target}_mean_{window}"] = rolling.transform(
            lambda values: values.rolling(window, min_periods=1).mean()
        )
        result[f"{target}_std_{window}"] = rolling.transform(
            lambda values: values.rolling(window, min_periods=2).std()
        )

    # Crecimiento interanual reciente: últimos 3 meses conocidos frente a los
    # mismos 3 meses del año anterior. Es la señal más estable en retail.
    recent = sum(lags[horizon + offset].fillna(0) for offset in range(3))
    recent_count = sum(lags[horizon + offset].notna().astype(int) for offset in range(3))
    last_year = sum(lags[horizon + 12 + offset].fillna(0) for offset in range(3))
    last_year_count = sum(lags[horizon + 12 + offset].notna().astype(int) for offset in range(3))
    valid = (recent_count == 3) & (last_year_count == 3)
    result[f"{target}_growth_3"] = _ratio(recent.where(valid), last_year.where(valid))
    result[f"{target}_growth_1"] = _ratio(lags[horizon], lags[horizon + 12])

    # Referencia estacional ajustada por crecimiento: mismo mes del año pasado
    # multiplicado por el crecimiento reciente (o 1 si no se puede medir).
    seasonal = result[f"{target}_lag_12"] if horizon <= 12 else pd.Series(np.nan, index=result.index)
    growth = result[f"{target}_growth_3"].fillna(result[f"{target}_growth_1"]).fillna(1.0)
    result[f"{target}_seasonal_growth"] = seasonal * growth
    result[f"{target}_seasonal_ratio"] = _ratio(seasonal, result[f"{target}_mean_12"])
    return result


def add_time_features(frame):
    result = frame.copy()
    result["month_sin"] = np.sin(2 * math.pi * result["mes"] / 12)
    result["month_cos"] = np.cos(2 * math.pi * result["mes"] / 12)
    result["trend"] = (result["anio"] - result["anio"].min()) * 12 + result["mes"]
    calendar_rows = {
        (int(year), int(month)): month_calendar_features(int(year), int(month))
        for year, month in result[["anio", "mes"]].drop_duplicates().itertuples(index=False)
    }
    for name in CALENDAR_COLUMNS:
        result[name] = [calendar_rows[(int(y), int(m))][name] for y, m in zip(result["anio"], result["mes"])]
    return result


def attach_dimensions(frame, dimensions, keys, external=None):
    result = frame.merge(dimensions.drop_duplicates(keys), on=keys, how="left")
    if "ciudad" not in result:
        result["ciudad"] = "SIN CIUDAD"
    result["ciudad"] = result["ciudad"].fillna("SIN CIUDAD").astype(str).str.upper()
    if external is not None and not external.empty:
        result = result.merge(external, on=["ciudad", "anio", "mes"], how="left")
    for column in EXTERNAL_COLUMNS:
        # Sin dato externo el valor queda vacío (NaN), no en cero: cero
        # significaría "nada de turismo" o "nada de lluvia".
        if column not in result:
            result[column] = np.nan
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def build_features(panel, dimensions, keys, target, external=None, horizon=1):
    result = add_lag_features(panel, keys, target, horizon)
    result = add_time_features(result)
    result = attach_dimensions(result, dimensions, keys, external)
    return result
