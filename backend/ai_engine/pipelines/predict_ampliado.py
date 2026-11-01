"""Genera un pronóstico no negativo y un intervalo para el siguiente mes."""

import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb

from ai_engine.config import DATA_MODELS, DATA_PROCESSED
from ai_engine.pipelines.forecast_utils import (
    FEATURES_VENTAS,
    agregar_rezagos_calendario,
    siguiente_periodo,
)


MODEL_PATH = DATA_MODELS / "modelo_ventas_ampliado.json"
METADATA_PATH = DATA_MODELS / "modelo_ventas_ampliado.metadata.json"


def cargar_modelo_y_metadata():
    with METADATA_PATH.open(encoding="utf-8") as file:
        metadata = json.load(file)
    if metadata.get("features") != FEATURES_VENTAS:
        raise ValueError("El esquema del modelo no coincide con el código")
    if metadata.get("estado") != "aprobado" and os.getenv("AI_ALLOW_UNVALIDATED_MODEL") != "1":
        reasons = "; ".join(metadata.get("razones_rechazo", []))
        raise RuntimeError(f"Modelo rechazado por la compuerta de calidad: {reasons}")
    model = xgb.XGBRegressor()
    model.load_model(MODEL_PATH)
    return model, metadata


def construir_features_siguiente_mes(df: pd.DataFrame):
    panel = df[["store_id", "line_id", "anio", "mes", "venta"]].drop_duplicates()
    panel["periodo"] = panel["anio"] * 100 + panel["mes"]
    last_period = int(panel["periodo"].max())
    year, month = siguiente_periodo(last_period)
    active_pairs = panel.loc[
        panel["periodo"] == last_period, ["store_id", "line_id"]
    ].drop_duplicates()
    targets = active_pairs.assign(anio=year, mes=month)
    features = agregar_rezagos_calendario(panel.drop(columns="periodo"), targets)
    features = features.dropna(subset=["venta_lag_1"])
    if features.empty:
        raise ValueError("No hay tiendas con venta del último mes cerrado")
    return features, year, month, last_period


def generar_predicciones_ampliadas(model, metadata, df):
    features, year, month, last_period = construir_features_siguiente_mes(df)
    predicted_log = model.predict(features[FEATURES_VENTAS])
    predicted = np.maximum(0.0, np.expm1(predicted_log))

    backtest = metadata["backtest"]
    p10 = np.maximum(0.0, np.expm1(predicted_log + backtest["residuo_log_p10"]))
    p90 = np.maximum(0.0, np.expm1(predicted_log + backtest["residuo_log_p90"]))
    lower, upper = np.minimum(p10, p90), np.maximum(p10, p90)

    result = features[["store_id", "line_id"]].copy()
    result["anio"] = year
    result["mes"] = month
    result["venta_predicha"] = predicted
    result["venta_predicha_p10"] = lower
    result["venta_predicha_p90"] = upper
    result["modelo_version"] = metadata["modelo_version"]

    if result.duplicated(["store_id", "line_id", "anio", "mes"]).any():
        raise ValueError("La predicción produjo claves duplicadas")
    if not np.isfinite(result[["venta_predicha", "venta_predicha_p10", "venta_predicha_p90"]]).all().all():
        raise ValueError("La predicción produjo números inválidos")

    output = DATA_PROCESSED / "predicciones_ampliado.parquet"
    result.to_parquet(output, index=False)
    print(f"Datos hasta {last_period}; pronóstico para {year}{month:02d}")
    print(f"Predicciones: {len(result)}; total: {result['venta_predicha'].sum():,.0f}")
    print(f"Intervalo agregado orientativo: {lower.sum():,.0f} a {upper.sum():,.0f}")
    return result


def main():
    model, metadata = cargar_modelo_y_metadata()
    df = pd.read_parquet(DATA_PROCESSED / "dataset_ampliado.parquet")
    generar_predicciones_ampliadas(model, metadata, df)


if __name__ == "__main__":
    main()
