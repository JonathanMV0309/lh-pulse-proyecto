"""
Guarda las predicciones ampliadas en la tabla ai_forecast_results.
Reemplaza las predicciones del mismo mes/año.
"""

import pandas as pd
from sqlalchemy import text
from datetime import datetime
from ai_engine.config import DATA_PROCESSED
from ai_engine.utils.db import get_engine


def guardar_predicciones_ampliadas():
    engine = get_engine()

    # Cargar predicciones ampliadas
    ruta_pred = DATA_PROCESSED / "predicciones_ampliado.parquet"
    df = pd.read_parquet(ruta_pred)
    if df.empty:
        print("No hay predicciones ampliadas para guardar.")
        return

    if df[["anio", "mes"]].drop_duplicates().shape[0] != 1:
        raise ValueError("El archivo contiene más de un periodo")
    if df.duplicated(["store_id", "line_id", "anio", "mes"]).any():
        raise ValueError("El archivo contiene predicciones duplicadas")

    # Defensa adicional: el modelo v2 ya genera resultados no negativos.
    df["venta_predicha"] = df["venta_predicha"].clip(lower=0)

    # Determinar año y mes
    anio = int(df.iloc[0]["anio"])
    mes = int(df.iloc[0]["mes"])
    print(f"Guardando predicciones para {anio}-{mes:02d}")

    fecha_gen = datetime.now()
    registros = []
    for _, fila in df.iterrows():
        registros.append({
            "store_id": int(fila["store_id"]),
            "line_id": int(fila["line_id"]),
            "anio": int(fila["anio"]),
            "mes": int(fila["mes"]),
            "venta_predicha": float(fila["venta_predicha"]),
            "fecha_generacion": fecha_gen,
            "modelo_version": str(fila.get("modelo_version", "ventas_xgb_v2"))
        })

    # DELETE + INSERT en una sola transacción: nunca queda el mes a medias.
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM ai_forecast_results WHERE anio = :anio AND mes = :mes"),
            {"anio": anio, "mes": mes},
        )
        conn.execute(
            text("""
                INSERT INTO ai_forecast_results
                    (store_id, line_id, anio, mes, venta_predicha, fecha_generacion, modelo_version)
                VALUES
                    (:store_id, :line_id, :anio, :mes, :venta_predicha, :fecha_generacion, :modelo_version)
            """),
            registros,
        )

    print(f"Se guardaron {len(registros)} predicciones ampliadas en ai_forecast_results.")


if __name__ == "__main__":
    guardar_predicciones_ampliadas()
