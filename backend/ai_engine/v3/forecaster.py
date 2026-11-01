"""Pronosticador global con validación mes a mes y ensamble conservador.

Flujo:
1. Variables con horizonte ``h`` (meses entre el último dato cerrado y el mes
   pronosticado); nunca se usa información posterior al corte.
2. Validación rodante: para cada uno de los últimos meses observados se
   entrena con lo conocido ``h`` meses antes y se pronostica ese mes.
3. Los pesos del ensamble, la corrección de sesgo y los intervalos salen de
   esos errores fuera de muestra.
4. El modelo final se reentrena con TODO el histórico antes de pronosticar.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from .features import build_features, complete_panel


MAX_BACKTEST_FOLDS = 6
MIN_TRAIN_ROWS = 30
INTERVAL_SHRINK = 4.0          # observaciones "virtuales" del rango global
INTERVAL_LOW_BOUNDS = (0.45, 0.97)
INTERVAL_HIGH_BOUNDS = (1.03, 1.80)
BIAS_LIMITS = (0.92, 1.08)


@dataclass
class ForecastResult:
    rows: pd.DataFrame
    diagnostics: dict


def _wape(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denominator = np.abs(actual).sum()
    if denominator <= 0:
        return float("inf")
    return float(np.abs(actual - predicted).sum() / denominator)


def _months_between(start, end):
    return (end.year - start.year) * 12 + (end.month - start.month)


def _baseline_predictions(frame, target, horizon):
    """Referencias simples; deben ganarle al modelo para quedarse con peso."""
    lag_h = frame.get(f"{target}_lag_{horizon}")
    if lag_h is None:
        lag_h = pd.Series(np.nan, index=frame.index)
    seasonal = frame[f"{target}_lag_12"] if f"{target}_lag_12" in frame else pd.Series(np.nan, index=frame.index)
    recent = frame[f"{target}_mean_3"]
    seasonal_growth = frame[f"{target}_seasonal_growth"]

    seasonal = seasonal.fillna(recent).fillna(lag_h).fillna(0.0)
    recent = recent.fillna(lag_h).fillna(seasonal).fillna(0.0)
    seasonal_growth = seasonal_growth.fillna(seasonal).fillna(0.0)
    return {
        "estacional": seasonal.clip(lower=0).to_numpy(dtype=float),
        "reciente": recent.clip(lower=0).to_numpy(dtype=float),
        "estacional_crecimiento": seasonal_growth.clip(lower=0).to_numpy(dtype=float),
    }


def _model_matrix(frame, keys, target, columns=None):
    excluded = {target, "period", "tienda", "linea"}
    candidates = [column for column in frame.columns if column not in excluded]
    matrix = frame[candidates].copy()
    # Pandas 3 usa con frecuencia string[pyarrow] en lugar de object. Detectar
    # por capacidad numérica evita intentar convertir códigos como "S-31".
    categorical = [
        column for column in matrix.columns
        if column in keys or not is_numeric_dtype(matrix[column].dtype)
    ]
    matrix = pd.get_dummies(matrix, columns=categorical, dummy_na=True, dtype=float)
    # Los vacíos numéricos se conservan: el gradient boosting aprende qué
    # hacer con un dato faltante, en lugar de confundirlo con un cero.
    matrix = matrix.replace([np.inf, -np.inf], np.nan)
    if columns is not None:
        matrix = matrix.reindex(columns=columns, fill_value=0.0)
    return matrix.astype(float)


def _ml_models():
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except ImportError:
        return {}

    # Pérdida Poisson sobre la venta directa: pondera cada tienda por su
    # tamaño, igual que el WAPE con el que se evalúa. (La variante sobre el
    # logaritmo no ganó peso en el backtest y duplicaba el tiempo.)
    def poisson(rows):
        return HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.08, max_iter=160,
            max_leaf_nodes=15, min_samples_leaf=max(10, min(30, rows // 40)),
            l2_regularization=1.0, early_stopping=False, random_state=42,
        )

    return {"ml": ("poisson", poisson)}


def _fit_predict(builder, kind, train, targets, keys, target):
    """Entrena con ``train`` y pronostica cada DataFrame de ``targets``."""
    x_train = _model_matrix(train, keys, target)
    # Una columna sin ningún dato (p. ej. turismo sin archivo externo) no
    # aporta y el gradient boosting no puede calcular sus cortes.
    x_train = x_train.loc[:, x_train.notna().any()]
    y = train[target].clip(lower=0).to_numpy(dtype=float)
    model = builder(len(train))
    if kind == "poisson":
        if y.sum() <= 0:
            return None
        model.fit(x_train, y)
        transform = lambda values: values
    else:
        model.fit(x_train, np.log1p(y))
        transform = np.expm1
    outputs = []
    for frame in targets:
        x = _model_matrix(frame, keys, target, x_train.columns)
        outputs.append(np.clip(transform(model.predict(x)), 0, None))
    return outputs


def _ensemble_weights(scores):
    finite = {name: score for name, score in scores.items() if np.isfinite(score)}
    if not finite:
        return {"estacional": 0.6, "reciente": 0.4}
    best = min(finite.values())
    # Un candidato claramente peor no debe arrastrar el pronóstico.
    eligible = {
        name: score for name, score in finite.items()
        if score <= max(best * 1.30, best + 0.03)
    }
    inverse = {name: 1.0 / max(score, 0.005) for name, score in eligible.items()}
    total = sum(inverse.values())
    return {name: value / total for name, value in inverse.items()}


def _backtest_periods(observed, horizon, folds):
    """Últimos meses evaluables. Con poca historia se aceptan meses cuyo
    entrenamiento es corto: ahí solo compiten las referencias simples."""
    periods = sorted(observed["period"].unique())
    usable = []
    for period in reversed(periods):
        train_rows = (observed["period"] <= period - horizon).sum()
        if train_rows >= MIN_TRAIN_ROWS:
            usable.append(period)
        if len(usable) >= folds:
            break
    if len(usable) < 2:
        usable = [period for period in periods[-folds:] if period - horizon >= periods[0]]
    return sorted(usable)


def _interval_ratios(backtest, keys):
    """Cuantiles P10/P90 de real/pronóstico por entidad, encogidos al global."""
    frame = backtest[backtest["pred"] > 0].copy()
    frame["ratio"] = frame["actual"] / frame["pred"]
    frame = frame[np.isfinite(frame["ratio"])]
    if frame.empty:
        return None, (0.75, 1.25)
    global_low = float(frame["ratio"].quantile(0.10))
    global_high = float(frame["ratio"].quantile(0.90))
    per_entity = frame.groupby(keys)["ratio"].agg(
        low=lambda values: values.quantile(0.10),
        high=lambda values: values.quantile(0.90),
        n="size",
    ).reset_index()
    weight = per_entity["n"] / (per_entity["n"] + INTERVAL_SHRINK)
    per_entity["low"] = weight * per_entity["low"] + (1 - weight) * global_low
    per_entity["high"] = weight * per_entity["high"] + (1 - weight) * global_high
    return per_entity[keys + ["low", "high"]], (global_low, global_high)


def forecast_panel(
    history,
    entities,
    dimensions,
    keys,
    target,
    cutoff_period,
    forecast_period,
    validation_months=6,
    min_history_months=12,
    external=None,
):
    """Pronostica un mes por entidad sin mezclar el futuro en el entrenamiento."""
    if history.empty:
        raise ValueError(f"No hay histórico para {target}")

    history = history.copy()
    history[target] = pd.to_numeric(history[target], errors="coerce")
    history_dates = pd.to_datetime({
        "year": history["anio"].astype(int),
        "month": history["mes"].astype(int),
        "day": 1,
    })
    history_periods = history_dates.dt.to_period("M")
    start_period = history_periods.min()
    cutoff = pd.Period(f"{cutoff_period[0]}-{cutoff_period[1]:02d}", freq="M")
    future_period = pd.Period(f"{forecast_period[0]}-{forecast_period[1]:02d}", freq="M")
    horizon = max(_months_between(cutoff, future_period), 1)
    panel = complete_panel(history, entities, keys, target, start_period, future_period)
    # Nada posterior al corte entra a las variables, aunque exista en la tabla.
    panel.loc[panel["period"] > cutoff, target] = np.nan
    features = build_features(panel, dimensions, keys, target, external, horizon)

    future = features[features["period"] == future_period].copy()
    observed = features[(features["period"] <= cutoff) & features[target].notna()].copy()
    if observed.empty or future.empty:
        raise ValueError(f"Histórico insuficiente para validar {target}")

    folds = _backtest_periods(observed, horizon, max(int(validation_months), 2))
    if not folds:
        raise ValueError(f"Histórico insuficiente para validar {target}")

    models = _ml_models()
    candidate_names = ["estacional", "reciente", "estacional_crecimiento"] + list(models)
    fold_rows = []
    fold_predictions = {name: [] for name in candidate_names}
    for period in folds:
        test = observed[observed["period"] == period]
        train = observed[observed["period"] <= period - horizon]
        baselines = _baseline_predictions(test, target, horizon)
        for name, values in baselines.items():
            fold_predictions[name].append(values)
        for name, (kind, builder) in models.items():
            output = None
            if len(train) >= MIN_TRAIN_ROWS:
                output = _fit_predict(builder, kind, train, [test], keys, target)
            fold_predictions[name].append(output[0] if output else np.full(len(test), np.nan))
        fold_rows.append(test[keys + ["period", target]])

    validation = pd.concat(fold_rows, ignore_index=True)
    actual = validation[target].to_numpy(dtype=float)
    validation_candidates = {
        name: np.concatenate(values) for name, values in fold_predictions.items()
    }
    validation_candidates = {
        name: values for name, values in validation_candidates.items()
        if np.isfinite(values).all()
    }
    scores = {name: _wape(actual, values) for name, values in validation_candidates.items()}
    weights = _ensemble_weights(scores)
    validation_prediction = sum(weights[name] * validation_candidates[name] for name in weights)

    # Corrección de sesgo: solo la mitad del sesgo medido y dentro de ±8%, y
    # únicamente si mejora el error fuera de muestra.
    raw_bias = actual.sum() / max(validation_prediction.sum(), 1.0)
    bias = float(np.clip(1 + 0.5 * (raw_bias - 1), *BIAS_LIMITS))
    if _wape(actual, validation_prediction * bias) >= _wape(actual, validation_prediction):
        bias = 1.0
    validation_prediction = validation_prediction * bias

    # Modelo final: reentrenado con todo lo observado.
    future_candidates = _baseline_predictions(future, target, horizon)
    for name, (kind, builder) in models.items():
        if name in weights:
            output = _fit_predict(builder, kind, observed, [future], keys, target)
            if output:
                future_candidates[name] = output[0]
    missing = [name for name in weights if name not in future_candidates]
    if missing:
        weights = {name: value for name, value in weights.items() if name not in missing}
        total = sum(weights.values()) or 1.0
        weights = {name: value / total for name, value in weights.items()}
    prediction = sum(weights[name] * future_candidates[name] for name in weights) * bias

    backtest = validation[keys].copy()
    backtest["actual"] = actual
    backtest["pred"] = validation_prediction
    per_entity, (global_low, global_high) = _interval_ratios(backtest, keys)
    future["p50"] = np.maximum(prediction, 0.0)
    if per_entity is not None:
        future = future.merge(per_entity, on=keys, how="left")
    else:
        future["low"], future["high"] = np.nan, np.nan
    future["low"] = future["low"].fillna(global_low).clip(*INTERVAL_LOW_BOUNDS)
    future["high"] = future["high"].fillna(global_high).clip(*INTERVAL_HIGH_BOUNDS)
    future["p10"] = future["p50"] * future["low"]
    future["p90"] = future["p50"] * future["high"]
    total_wape = _wape(actual, validation_prediction)
    future["confidence"] = float(np.clip(1.0 - total_wape, 0.0, 1.0))

    ratios = np.divide(actual, validation_prediction, out=np.full(len(actual), np.nan),
                       where=validation_prediction > 0)
    inside = (ratios >= np.clip(global_low, *INTERVAL_LOW_BOUNDS)) & (
        ratios <= np.clip(global_high, *INTERVAL_HIGH_BOUNDS)
    )
    by_period = {}
    for period in folds:
        mask = (validation["period"] == period).to_numpy()
        by_period[str(period)] = _wape(actual[mask], validation_prediction[mask])

    keep = keys + ["anio", "mes", "p10", "p50", "p90", "confidence"]
    diagnostics = {
        "target": target,
        "model": "+".join(name for name in weights if name.startswith("ml")) or "referencias",
        "horizon_months": int(horizon),
        "validation_rows": int(len(validation)),
        "training_rows": int(len(observed)),
        "backtest_folds": [str(period) for period in folds],
        "wape": total_wape,
        "wape_by_month": by_period,
        "candidate_wape": {name: float(value) for name, value in scores.items()},
        "weights": {name: float(value) for name, value in weights.items()},
        "bias_factor": bias,
        "interval_error_ratio": float((np.clip(global_high, *INTERVAL_HIGH_BOUNDS)
                                       - np.clip(global_low, *INTERVAL_LOW_BOUNDS)) / 2),
        "interval_coverage_backtest": float(np.nanmean(inside)) if len(inside) else None,
    }
    return ForecastResult(future[keep].copy(), diagnostics)


def goal_probability(p50, p10, p90, goal):
    """Probabilidad aproximada de superar una meta a partir del intervalo P10–P90.

    El intervalo puede ser asimétrico: se usa la mitad baja o alta según la
    meta esté por debajo o por encima del pronóstico central.
    """
    values = [p50, p10, p90, goal]
    if any(value is None or not np.isfinite(float(value)) for value in values) or goal <= 0:
        return None
    p50, p10, p90, goal = (float(value) for value in values)
    spread = (p90 - p50) if goal >= p50 else (p50 - p10)
    sigma = max(spread / 1.2816, p50 * 0.03, 1.0)
    z = (goal - p50) / sigma
    # Aproximación logística de la normal (1.702·z).
    return float(np.clip(1.0 / (1.0 + np.exp(np.clip(1.702 * z, -30, 30))), 0.0, 1.0))
