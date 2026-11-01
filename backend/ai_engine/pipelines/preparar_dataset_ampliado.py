"""Construye el panel mensual limpio usado por el pronóstico de ventas."""

import re

import numpy as np
import pandas as pd
from sqlalchemy import text

from ai_engine.config import DATA_PROCESSED, DATA_RAW
from ai_engine.pipelines.forecast_utils import (
    agregar_rezagos_calendario,
    periodo_cerrado_actual,
    validar_claves_unicas,
)
from ai_engine.utils.db import get_engine


KEYS = ["store_id", "line_id", "anio", "mes"]


def normalizar_nombre(value) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().upper().replace("-", " ").split())


def normalizar_codigo(value) -> str:
    match = re.search(r"\bS\s*[- ]?\s*(\d+)\b", str(value).upper())
    return f"S-{int(match.group(1)):02d}" if match else ""


def obtener_mapeos():
    with get_engine().connect() as connection:
        stores = connection.execute(text("SELECT id, codigo, nombre FROM stores")).fetchall()
        lines = connection.execute(text("SELECT id, nombre FROM lines")).fetchall()

    store_by_code = {
        normalizar_codigo(row.codigo): int(row.id)
        for row in stores
        if normalizar_codigo(row.codigo)
    }
    store_by_name = {normalizar_nombre(row.nombre): int(row.id) for row in stores}
    line_by_name = {normalizar_nombre(row.nombre): int(row.id) for row in lines}
    return store_by_code, store_by_name, line_by_name


def mapear_historico(
    historical: pd.DataFrame,
    store_by_code: dict,
    store_by_name: dict,
    line_by_name: dict,
) -> pd.DataFrame:
    result = historical.copy()
    result["codigo_norm"] = result["tienda"].map(normalizar_codigo)
    result["tienda_norm"] = result["tienda"].map(normalizar_nombre)
    result["linea_norm"] = result["linea"].map(normalizar_nombre)
    result["store_id"] = result["codigo_norm"].map(store_by_code)
    result["store_id"] = result["store_id"].fillna(result["tienda_norm"].map(store_by_name))
    result["line_id"] = result["linea_norm"].map(line_by_name)

    unmatched = result[result["store_id"].isna() | result["line_id"].isna()]
    if not unmatched.empty:
        examples = unmatched[["tienda", "linea"]].drop_duplicates().head(10)
        print(f"ADVERTENCIA: {len(unmatched)} filas históricas sin mapeo")
        print(examples.to_string(index=False))

    result = result.dropna(subset=["store_id", "line_id", "anio", "mes", "venta_pesos"])
    result = result.rename(columns={"venta_pesos": "venta"})
    result = result[["store_id", "line_id", "anio", "mes", "venta"]]
    result["fuente_prioridad"] = 0
    return result


def consolidar_panel(historical: pd.DataFrame, current: pd.DataFrame, cutoff: int) -> pd.DataFrame:
    actual = current[["store_id", "line_id", "anio", "mes", "venta"]].copy()
    actual["fuente_prioridad"] = 1
    panel = pd.concat([historical, actual], ignore_index=True)

    for column in ("store_id", "line_id", "anio", "mes"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    panel["venta"] = pd.to_numeric(panel["venta"], errors="coerce")
    panel = panel.replace([np.inf, -np.inf], np.nan)
    panel = panel.dropna(subset=KEYS + ["venta"])
    panel = panel[
        (panel["store_id"] > 0)
        & (panel["line_id"] > 0)
        & panel["mes"].between(1, 12)
        & (panel["venta"] >= 0)
    ].copy()
    panel[KEYS] = panel[KEYS].astype(int)
    panel["periodo"] = panel["anio"] * 100 + panel["mes"]
    removed_future = int((panel["periodo"] > cutoff).sum())
    panel = panel[panel["periodo"] <= cutoff]

    before = len(panel)
    panel = panel.sort_values(KEYS + ["fuente_prioridad"])
    panel = panel.drop_duplicates(KEYS, keep="last")
    removed_duplicates = before - len(panel)
    panel = panel.drop(columns=["fuente_prioridad", "periodo"])
    panel = panel.sort_values(KEYS).reset_index(drop=True)
    validar_claves_unicas(panel)
    print(f"Corte cerrado: {cutoff}")
    print(f"Filas futuras/parciales excluidas: {removed_future}")
    print(f"Duplicados resueltos con prioridad a BD: {removed_duplicates}")
    return panel


def preparar_dataset_ampliado():
    historical_raw = pd.read_parquet(DATA_RAW / "historico_inf4_mensual_pesos_linea.parquet")
    current = pd.read_parquet(DATA_RAW / "sales_history_lines.parquet")
    mappings = obtener_mapeos()
    historical = mapear_historico(historical_raw, *mappings)
    panel = consolidar_panel(historical, current, periodo_cerrado_actual())
    dataset = agregar_rezagos_calendario(panel)

    # Un mes inmediatamente anterior es el requisito mínimo. Los demás rezagos
    # pueden faltar para tiendas nuevas y XGBoost los maneja explícitamente.
    dataset = dataset.dropna(subset=["venta", "venta_lag_1"])
    dataset["periodo"] = dataset["anio"] * 100 + dataset["mes"]
    dataset = dataset.sort_values(KEYS).reset_index(drop=True)

    output = DATA_PROCESSED / "dataset_ampliado.parquet"
    dataset.to_parquet(output, index=False)
    print(f"Dataset limpio guardado: {len(dataset)} filas -> {output}")
    print(f"Períodos: {dataset['periodo'].min()} a {dataset['periodo'].max()}")
    return dataset


if __name__ == "__main__":
    preparar_dataset_ampliado()
