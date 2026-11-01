"""
Extraccion de datos desde la base de datos en modo solo lectura.
Solo extrae las 4 lineas principales (FEMENINO, PLUS-SIZE, MASCULINO, ACCESORIOS).
Los datos se guardan en ai_engine/data/raw/ como archivos Parquet.
"""

import pandas as pd
from sqlalchemy import text
from ai_engine.utils.db import get_engine
from ai_engine.config import DATA_RAW


def extract_table(table_name, query):
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    output_path = DATA_RAW / f"{table_name}.parquet"
    df.to_parquet(output_path, index=False)
    print(f"Guardado {table_name}: {len(df)} filas -> {output_path}")
    return df


def main():
    print("Iniciando extraccion de datos historicos (solo 4 lineas principales)...")

    # 1) Historico de ventas por linea (solo lineas 1-4)
    extract_table(
        "sales_history_lines",
        """
        SELECT
            store_id,
            line_id,
            anio,
            mes,
            venta
        FROM sales_history_lines
        WHERE line_id IN (1, 2, 3, 4)
        ORDER BY store_id, line_id, anio, mes
        """
    )

    # 2) Metas por linea (solo lineas 1-4)
    extract_table(
        "meta_lines",
        """
        SELECT
            store_id,
            line_id,
            anio,
            mes,
            meta,
            meta_proporcional,
            venta,
            cumplimiento_pct
        FROM meta_lines
        WHERE line_id IN (1, 2, 3, 4)
        ORDER BY store_id, line_id, anio, mes
        """
    )

    # 3) Indicadores de tienda por corte (compliances)
    extract_table(
        "compliances",
        """
        SELECT
            store_id,
            anio,
            mes,
            dia_corte,
            es_cierre,
            venta_actual,
            venta_anterior,
            incremento,
            cuota_total,
            cumplimiento_pct,
            trafico,
            facturas,
            conversion,
            ticket_promedio,
            venta_promedio_dia,
            activo,
            nombre_archivo
        FROM compliance
        WHERE activo = true
        ORDER BY store_id, anio, mes, dia_corte
        """
    )

    print("Extraccion completada.")


if __name__ == "__main__":
    main()