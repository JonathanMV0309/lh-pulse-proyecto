"""Entrenamiento y backtesting temporal del pronóstico mensual de ventas."""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import xgboost as xgb

from ai_engine.config import DATA_MODELS, DATA_PROCESSED
from ai_engine.pipelines.forecast_utils import (
    FEATURES_VENTAS,
    baseline_temporal,
    metricas_regresion,
)


MODEL_PATH = DATA_MODELS / "modelo_ventas_ampliado.json"
METADATA_PATH = DATA_MODELS / "modelo_ventas_ampliado.metadata.json"
METRICS_PATH = DATA_MODELS / "metricas_ampliado.json"


def cargar_dataset() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PROCESSED / "dataset_ampliado.parquet")
    if "periodo" not in df:
        df["periodo"] = df["anio"] * 100 + df["mes"]
    missing = sorted(set(FEATURES_VENTAS + ["venta", "periodo"]) - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas de entrenamiento: {missing}")
    return df.sort_values(["periodo", "store_id", "line_id"]).reset_index(drop=True)


def crear_modelo(n_estimators=500, early_stopping_rounds=None):
    return xgb.XGBRegressor(
        n_estimators=n_estimators,
        max_depth=4,
        learning_rate=0.03,
        min_child_weight=5,
        subsample=0.85,
        colsample_bytree=0.90,
        reg_alpha=0.10,
        reg_lambda=5.0,
        objective="reg:squarederror",
        eval_metric="mae",
        early_stopping_rounds=early_stopping_rounds,
        random_state=42,
        n_jobs=max(1, min(4, os.cpu_count() or 1)),
    )


def _predecir_escala_ventas(model, X):
    return np.maximum(0.0, np.expm1(model.predict(X)))


def ejecutar_backtest(df: pd.DataFrame, max_folds: int = 6):
    periods = sorted(int(p) for p in df["periodo"].unique())
    if len(periods) < 5:
        raise ValueError("Se necesitan al menos 5 meses para una validación temporal")
    validation_periods = periods[-min(max_folds, len(periods) - 3):]
    folds, all_actual, all_predicted, all_baseline, log_residuals, best_rounds = [], [], [], [], [], []

    for period in validation_periods:
        train = df[df["periodo"] < period]
        test = df[df["periodo"] == period]
        if train.empty or test.empty:
            continue
        tuning_period = int(train["periodo"].max())
        fit_train = train[train["periodo"] < tuning_period]
        tuning = train[train["periodo"] == tuning_period]
        if fit_train.empty or tuning.empty:
            continue
        tuning_model = crear_modelo(early_stopping_rounds=30)
        tuning_model.fit(
            fit_train[FEATURES_VENTAS],
            np.log1p(fit_train["venta"]),
            eval_set=[(tuning[FEATURES_VENTAS], np.log1p(tuning["venta"]))],
            verbose=False,
        )
        selected_trees = int(getattr(tuning_model, "best_iteration", 299)) + 1
        model = crear_modelo(n_estimators=selected_trees)
        model.fit(train[FEATURES_VENTAS], np.log1p(train["venta"]), verbose=False)
        predicted = _predecir_escala_ventas(model, test[FEATURES_VENTAS])
        baseline = baseline_temporal(test)
        model_metrics = metricas_regresion(test["venta"], predicted)
        baseline_metrics = metricas_regresion(test["venta"], baseline)
        folds.append({
            "periodo": period,
            "filas": len(test),
            "modelo": model_metrics,
            "baseline": baseline_metrics,
            "gana_modelo": model_metrics["wape"] < baseline_metrics["wape"],
        })
        all_actual.extend(test["venta"].astype(float))
        all_predicted.extend(predicted)
        all_baseline.extend(baseline)
        log_residuals.extend(np.log1p(test["venta"]) - np.log1p(predicted))
        best_rounds.append(selected_trees)

    if len(folds) < 3:
        raise ValueError("No fue posible construir al menos 3 ventanas de backtesting")
    return {
        "folds": folds,
        "modelo_global": metricas_regresion(all_actual, all_predicted),
        "baseline_global": metricas_regresion(all_actual, all_baseline),
        "residuo_log_p10": float(np.quantile(log_residuals, 0.10)),
        "residuo_log_p90": float(np.quantile(log_residuals, 0.90)),
        "residuo_log_media": float(np.mean(log_residuals)),
        "residuo_log_sigma": float(np.std(log_residuals, ddof=1)),
        "arboles_recomendados": int(np.median(best_rounds)),
    }


def evaluar_compuerta(backtest: dict) -> tuple[bool, list[str]]:
    model_wape = backtest["modelo_global"]["wape"]
    baseline_wape = backtest["baseline_global"]["wape"]
    minimum_improvement = float(os.getenv("AI_MIN_MODEL_IMPROVEMENT", "0.02"))
    improvement = (baseline_wape - model_wape) / baseline_wape if baseline_wape else -1
    wins = sum(fold["gana_modelo"] for fold in backtest["folds"])
    required_wins = int(np.ceil(len(backtest["folds"]) / 2))
    reasons = []
    if improvement < minimum_improvement:
        reasons.append(f"Mejora contra baseline insuficiente: {improvement:.1%}")
    if wins < required_wins:
        reasons.append(f"El modelo ganó solamente {wins}/{len(backtest['folds'])} meses")
    if model_wape > 0.50:
        reasons.append(f"WAPE global demasiado alto: {model_wape:.1%}")
    return not reasons, reasons


def entrenar_modelo_ampliado():
    df = cargar_dataset()
    backtest = ejecutar_backtest(df)
    approved, reasons = evaluar_compuerta(backtest)
    trees = max(80, min(700, backtest["arboles_recomendados"]))

    model = crear_modelo(n_estimators=trees)
    model.fit(df[FEATURES_VENTAS], np.log1p(df["venta"]), verbose=False)
    candidate_path = MODEL_PATH.with_name(MODEL_PATH.stem + ".candidate.json")
    model.save_model(candidate_path)

    metadata = {
        "modelo_version": "ventas_xgb_v2",
        "formato": "xgboost-json",
        "xgboost_version": xgb.__version__,
        "fecha_entrenamiento": datetime.now(timezone.utc).isoformat(),
        "periodo_inicio": int(df["periodo"].min()),
        "periodo_fin": int(df["periodo"].max()),
        "filas": len(df),
        "features": FEATURES_VENTAS,
        "target_transform": "log1p",
        "estado": "aprobado" if approved else "rechazado",
        "razones_rechazo": reasons,
        "backtest": backtest,
    }
    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)

    print(f"Estado de calidad: {metadata['estado'].upper()}")
    print(f"WAPE modelo: {backtest['modelo_global']['wape']:.2%}")
    print(f"WAPE baseline: {backtest['baseline_global']['wape']:.2%}")
    if reasons:
        print("; ".join(reasons))
        candidate_path.unlink(missing_ok=True)
        raise RuntimeError("El candidato no superó la compuerta; se conserva el modelo anterior")

    os.replace(candidate_path, MODEL_PATH)
    temporary_metadata = METADATA_PATH.with_suffix(".metadata.tmp")
    with temporary_metadata.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)
    os.replace(temporary_metadata, METADATA_PATH)
    print(f"Modelo aprobado y publicado: {MODEL_PATH}")
    return model, metadata


if __name__ == "__main__":
    entrenar_modelo_ampliado()
