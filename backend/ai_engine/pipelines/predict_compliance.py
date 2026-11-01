"""Estima P(venta >= meta) usando el pronóstico y su error de backtesting."""

import json
import math
from statistics import NormalDist

import pandas as pd

from ai_engine.config import DATA_MODELS, DATA_PROCESSED, DATA_RAW


def generar_probabilidades():
    forecasts = pd.read_parquet(DATA_PROCESSED / "predicciones_ampliado.parquet")
    metas = pd.read_parquet(DATA_RAW / "meta_lines.parquet")
    with (DATA_MODELS / "modelo_ventas_ampliado.metadata.json").open(encoding="utf-8") as file:
        metadata = json.load(file)

    keys = ["store_id", "line_id", "anio", "mes"]
    duplicate_metas = metas.duplicated(keys, keep=False)
    if duplicate_metas.any():
        raise ValueError("Hay metas oficiales duplicadas para tienda-línea-período")
    metas = metas[keys + ["meta"]].copy()
    metas["meta"] = pd.to_numeric(metas["meta"], errors="coerce")
    result = forecasts.merge(metas, on=keys, how="left", validate="one_to_one")
    result = result[result["meta"].notna() & (result["meta"] > 0)].copy()

    error = metadata["backtest"]
    mean = float(error.get("residuo_log_media", 0.0))
    sigma = max(0.05, float(error["residuo_log_sigma"]))
    normal = NormalDist()

    def probability(row):
        threshold = math.log1p(float(row["meta"])) - math.log1p(float(row["venta_predicha"]))
        return min(1.0, max(0.0, 1.0 - normal.cdf((threshold - mean) / sigma)))

    result["probabilidad_cumplimiento"] = result.apply(probability, axis=1)
    result["modelo_version"] = metadata["modelo_version"] + "_prob_meta"
    output_columns = keys + ["probabilidad_cumplimiento", "modelo_version"]
    result = result[output_columns]
    output = DATA_PROCESSED / "predicciones_cumplimiento.parquet"
    result.to_parquet(output, index=False)
    print(f"Probabilidades con meta oficial: {len(result)} -> {output}")
    print(f"Sin meta oficial: {len(forecasts) - len(result)}")
    return result


def main():
    generar_probabilidades()


if __name__ == "__main__":
    main()
