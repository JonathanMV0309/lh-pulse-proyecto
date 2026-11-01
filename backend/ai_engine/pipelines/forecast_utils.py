"""Utilidades compartidas del pronóstico mensual de ventas."""

from __future__ import annotations

import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


LAGS_VENTA = (1, 2, 3, 6, 12)
FEATURES_VENTAS = [
    "store_id",
    "line_id",
    "mes_sin",
    "mes_cos",
    "tendencia_meses",
    "venta_lag_1",
    "venta_lag_2",
    "venta_lag_3",
    "venta_lag_6",
    "venta_lag_12",
    "venta_media_3",
]


def periodo_cerrado_actual() -> int:
    """Último mes cerrado; puede fijarse con AI_DATA_CUTOFF=AAAAMM."""
    configured = os.getenv("AI_DATA_CUTOFF", "").strip()
    if configured:
        if len(configured) != 6 or not configured.isdigit():
            raise ValueError("AI_DATA_CUTOFF debe tener formato AAAAMM")
        year, month = int(configured[:4]), int(configured[4:])
        if not 1 <= month <= 12:
            raise ValueError("Mes inválido en AI_DATA_CUTOFF")
        return year * 100 + month

    now = datetime.now(ZoneInfo("America/Bogota"))
    if now.month == 1:
        return (now.year - 1) * 100 + 12
    return now.year * 100 + now.month - 1


def agregar_variables_temporales(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    month = result["mes"].astype(int)
    result["mes_sin"] = np.sin(2 * np.pi * month / 12)
    result["mes_cos"] = np.cos(2 * np.pi * month / 12)
    result["tendencia_meses"] = (result["anio"].astype(int) - 2020) * 12 + month
    return result


def validar_claves_unicas(df: pd.DataFrame) -> None:
    keys = ["store_id", "line_id", "anio", "mes"]
    duplicated = df.duplicated(keys, keep=False)
    if duplicated.any():
        examples = df.loc[duplicated, keys].head(5).to_dict("records")
        raise ValueError(f"Hay claves tienda-línea-mes duplicadas: {examples}")


def agregar_rezagos_calendario(
    panel: pd.DataFrame,
    fechas_objetivo: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Crea rezagos por mes calendario, no por posición de fila."""
    sales = panel[["store_id", "line_id", "anio", "mes", "venta"]].copy()
    validar_claves_unicas(sales)
    sales["fecha"] = pd.to_datetime(
        dict(year=sales["anio"].astype(int), month=sales["mes"].astype(int), day=1)
    )

    if fechas_objetivo is None:
        result = sales.copy()
    else:
        result = fechas_objetivo[["store_id", "line_id", "anio", "mes"]].copy()
        result["fecha"] = pd.to_datetime(
            dict(year=result["anio"].astype(int), month=result["mes"].astype(int), day=1)
        )
        result = result.merge(
            sales[["store_id", "line_id", "fecha", "venta"]],
            on=["store_id", "line_id", "fecha"],
            how="left",
        )

    lookup = sales[["store_id", "line_id", "fecha", "venta"]]
    for lag in LAGS_VENTA:
        shifted = lookup.copy()
        shifted["fecha"] = shifted["fecha"] + pd.DateOffset(months=lag)
        shifted = shifted.rename(columns={"venta": f"venta_lag_{lag}"})
        result = result.merge(
            shifted,
            on=["store_id", "line_id", "fecha"],
            how="left",
            validate="one_to_one",
        )

    result["venta_media_3"] = result[
        ["venta_lag_1", "venta_lag_2", "venta_lag_3"]
    ].mean(axis=1, skipna=False)
    result = agregar_variables_temporales(result)
    return result.drop(columns="fecha")


def siguiente_periodo(periodo: int) -> tuple[int, int]:
    year, month = divmod(int(periodo), 100)
    return (year + 1, 1) if month == 12 else (year, month + 1)


def metricas_regresion(actual, predicted) -> dict:
    y = np.asarray(actual, dtype=float)
    pred = np.asarray(predicted, dtype=float)
    abs_error = np.abs(y - pred)
    smape_den = np.abs(y) + np.abs(pred)
    total = np.abs(y).sum()
    return {
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(math.sqrt(mean_squared_error(y, pred))),
        "r2": float(r2_score(y, pred)) if len(y) > 1 else None,
        "wape": float(abs_error.sum() / total) if total else None,
        "smape": float(np.mean(np.where(smape_den > 0, 2 * abs_error / smape_den, 0))),
        "sesgo_total": float((pred.sum() - y.sum()) / y.sum()) if y.sum() else None,
        "total_real": float(y.sum()),
        "total_predicho": float(pred.sum()),
        "predicciones_negativas": int((pred < 0).sum()),
    }


def baseline_temporal(df: pd.DataFrame) -> np.ndarray:
    """Mismo mes del año anterior cuando existe; si no, último mes."""
    seasonal = df["venta_lag_12"]
    return seasonal.where(seasonal.notna(), df["venta_lag_1"]).to_numpy(dtype=float)
