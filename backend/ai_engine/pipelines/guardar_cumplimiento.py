"""
Guarda las probabilidades de cumplimiento en la tabla ai_compliance_predictions.
La tabla se crea automaticamente si no existe.
No modifica ninguna tabla existente.
"""

import pandas as pd
from sqlalchemy import text
from datetime import datetime
from ai_engine.config import DATA_PROCESSED
from ai_engine.utils.db import get_engine


def crear_tabla_si_no_existe(engine):
    """Crea la tabla ai_compliance_predictions si no existe."""
    sql = """
    CREATE TABLE IF NOT EXISTS ai_compliance_predictions (
        id SERIAL PRIMARY KEY,
        store_id INTEGER NOT NULL,
        line_id INTEGER NOT NULL,
        anio INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        probabilidad_cumplimiento NUMERIC(5,4),
        fecha_generacion TIMESTAMP DEFAULT NOW(),
        modelo_version VARCHAR(50),
        UNIQUE(store_id, line_id, anio, mes)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("Tabla ai_compliance_predictions verificada/creada.")


def guardar_probabilidades():
    engine = get_engine()
    crear_tabla_si_no_existe(engine)

    # Cargar predicciones
    ruta_pred = DATA_PROCESSED / "predicciones_cumplimiento.parquet"
    df = pd.read_parquet(ruta_pred)
    if df.empty:
        forecast = pd.read_parquet(DATA_PROCESSED / "predicciones_ampliado.parquet")
        if forecast.empty:
            print("No hay probabilidades ni pronósticos para guardar.")
            return
        anio, mes = int(forecast.iloc[0]["anio"]), int(forecast.iloc[0]["mes"])
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM ai_compliance_predictions WHERE anio = :anio AND mes = :mes"),
                {"anio": anio, "mes": mes},
            )
        print(f"No hay metas oficiales; probabilidades anteriores eliminadas para {anio}-{mes:02d}.")
        return

    registros = []
    fecha_gen = datetime.now()
    for _, fila in df.iterrows():
        registros.append({
            "store_id": int(fila["store_id"]),
            "line_id": int(fila["line_id"]),
            "anio": int(fila["anio"]),
            "mes": int(fila["mes"]),
            "probabilidad_cumplimiento": float(fila["probabilidad_cumplimiento"]),
            "fecha_generacion": fecha_gen,
            "modelo_version": str(fila.get("modelo_version", "ventas_xgb_v2_prob_meta"))
        })

    # Reemplazo atómico del periodo.
    anio = registros[0]["anio"]
    mes = registros[0]["mes"]
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM ai_compliance_predictions WHERE anio = :anio AND mes = :mes"),
            {"anio": anio, "mes": mes},
        )
        conn.execute(
            text("""
                INSERT INTO ai_compliance_predictions
                    (store_id, line_id, anio, mes, probabilidad_cumplimiento, fecha_generacion, modelo_version)
                VALUES
                    (:store_id, :line_id, :anio, :mes, :probabilidad_cumplimiento, :fecha_generacion, :modelo_version)
            """),
            registros,
        )

    print(f"Se guardaron {len(registros)} probabilidades en ai_compliance_predictions para {anio}-{mes:02d}.")


if __name__ == "__main__":
    guardar_probabilidades()
