"""
Importa el archivo histórico 2024-2025 (COMPARATIVO) a Parquet.
Procesa las hojas INF1, INF2, INF3, INF6.
Genera dataset consolidado con ventas mensuales por tienda en pesos y unidades.
Incluye limpieza de nombres con mojibake.
"""

import pandas as pd
import numpy as np
from pathlib import Path

RUTA_EXCEL = Path("ai_engine/data/raw/historico_2024_2025/historico_2024_2025.xlsx")
DATA_RAW = Path("ai_engine/data/raw")

MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
         "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]


def limpiar_nombre_tienda(valor):
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto.startswith("Total") or texto.startswith("TOTAL") or texto == "":
        return None
    # Reemplazar mojibake común
    replacements = {
        "Ã‘": "Ñ", "Ã‰": "É", "Ã“": "Ó", "Ãº": "ú", "Ã©": "é",
        "Ã“": "Ó", "Ã": "Í", "Â": "", "â€": "–", "Ã¼": "ü",
        "PEQUEÃ‘O": "PEQUEÑO", "MEDELLÃN": "MEDELLÍN",
        "BUCARAMANGA": "BUCARAMANGA"  # ya bien
    }
    for old, new in replacements.items():
        texto = texto.replace(old, new)
    return texto


def procesar_inf1_anual():
    """Extrae ventas totales anuales por tienda en pesos."""
    df = pd.read_excel(RUTA_EXCEL, sheet_name="INF1", header=None)
    df = df.iloc[4:, [0, 1, 2, 3]].copy()
    df.columns = ["cluster", "tienda", "venta_2024", "venta_2025"]
    df["tienda"] = df["tienda"].apply(limpiar_nombre_tienda)
    df = df.dropna(subset=["tienda"])
    df = df[df["tienda"].str.startswith(("S-", "S "), na=False)]  # solo tiendas
    df["venta_2024"] = pd.to_numeric(df["venta_2024"], errors="coerce").fillna(0)
    df["venta_2025"] = pd.to_numeric(df["venta_2025"], errors="coerce").fillna(0)
    return df


def procesar_inf2_anual():
    """Extrae ventas totales anuales por tienda en unidades."""
    df = pd.read_excel(RUTA_EXCEL, sheet_name="INF2", header=None)
    df = df.iloc[4:, [0, 1, 2, 3]].copy()
    df.columns = ["cluster", "tienda", "unidades_2024", "unidades_2025"]
    df["tienda"] = df["tienda"].apply(limpiar_nombre_tienda)
    df = df.dropna(subset=["tienda"])
    df = df[df["tienda"].str.startswith(("S-", "S "), na=False)]
    df["unidades_2024"] = pd.to_numeric(df["unidades_2024"], errors="coerce").fillna(0)
    df["unidades_2025"] = pd.to_numeric(df["unidades_2025"], errors="coerce").fillna(0)
    return df


def procesar_inf3_mensual():
    """Extrae ventas mensuales por tienda en pesos (2024 y 2025)."""
    df = pd.read_excel(RUTA_EXCEL, sheet_name="INF3", header=None)
    columnas_meses = []
    for col in range(df.shape[1] - 1):
        encabezado = str(df.iat[2, col]).strip().upper()
        if encabezado in MESES:
            anio_1 = pd.to_numeric(df.iat[3, col], errors="coerce")
            anio_2 = pd.to_numeric(df.iat[3, col + 1], errors="coerce")
            if pd.isna(anio_1) or pd.isna(anio_2) or int(anio_1) != 2024 or int(anio_2) != 2025:
                raise ValueError(f"Encabezado inesperado en INF3 para {encabezado}")
            columnas_meses.append((encabezado, col, col + 1))
    if len(columnas_meses) != 12:
        raise ValueError(f"INF3 debe contener 12 meses; encontrados: {len(columnas_meses)}")

    filas = df.iloc[4:].copy()
    registros_mensuales = []

    for _, fila in filas.iterrows():
        tienda = limpiar_nombre_tienda(fila[1])
        if tienda is None or not tienda.startswith(("S-", "S ")):
            continue

        for mes, col_2024, col_2025 in columnas_meses:
            venta_2024 = fila[col_2024]
            venta_2025 = fila[col_2025]
            registros_mensuales.append({
                "tienda": tienda,
                "mes": mes,
                "anio": 2024,
                "venta_pesos": pd.to_numeric(venta_2024, errors="coerce")
            })
            registros_mensuales.append({
                "tienda": tienda,
                "mes": mes,
                "anio": 2025,
                "venta_pesos": pd.to_numeric(venta_2025, errors="coerce")
            })

    return pd.DataFrame(registros_mensuales)


def procesar_inf6_mensual():
    """Extrae ventas mensuales por tienda en unidades (2024 y 2025)."""
    df = pd.read_excel(RUTA_EXCEL, sheet_name="INF6", header=None)
    num_columnas = df.shape[1]
    num_meses = (num_columnas - 6) // 4
    meses_disponibles = MESES[:num_meses]

    filas = df.iloc[4:].copy()
    registros_mensuales = []

    for _, fila in filas.iterrows():
        tienda = limpiar_nombre_tienda(fila[1])
        if tienda is None or not tienda.startswith(("S-", "S ")):
            continue

        for i, mes in enumerate(meses_disponibles):
            base_col = 6 + i * 4
            unidades_2024 = fila[base_col]
            unidades_2025 = fila[base_col + 1]
            registros_mensuales.append({
                "tienda": tienda,
                "mes": mes,
                "anio": 2024,
                "venta_unidades": pd.to_numeric(unidades_2024, errors="coerce")
            })
            registros_mensuales.append({
                "tienda": tienda,
                "mes": mes,
                "anio": 2025,
                "venta_unidades": pd.to_numeric(unidades_2025, errors="coerce")
            })

    return pd.DataFrame(registros_mensuales)


def main():
    print("Procesando archivo histórico...")

    print("INF1 (pesos anual)...")
    inf1 = procesar_inf1_anual()
    print("INF2 (unidades anual)...")
    inf2 = procesar_inf2_anual()

    print("INF3 (pesos mensual)...")
    inf3_mensual = procesar_inf3_mensual()
    print("INF6 (unidades mensual)...")
    inf6_mensual = procesar_inf6_mensual()

    # Guardar Parquets individuales
    inf1.to_parquet(DATA_RAW / "historico_inf1_anual_pesos.parquet", index=False)
    inf2.to_parquet(DATA_RAW / "historico_inf2_anual_unidades.parquet", index=False)
    inf3_mensual.to_parquet(DATA_RAW / "historico_inf3_mensual_pesos.parquet", index=False)
    inf6_mensual.to_parquet(DATA_RAW / "historico_inf6_mensual_unidades.parquet", index=False)

    # Consolidar mensual combinando pesos y unidades
    consolidado = inf3_mensual.merge(
        inf6_mensual,
        on=["tienda", "mes", "anio"],
        how="outer"
    )
    consolidado = consolidado.fillna(0)
    consolidado["venta_pesos"] = pd.to_numeric(consolidado["venta_pesos"], errors="coerce")
    consolidado["venta_unidades"] = pd.to_numeric(consolidado["venta_unidades"], errors="coerce")
    consolidado.to_parquet(DATA_RAW / "historico_2024_2025_mensual_consolidado.parquet", index=False)

    print("Guardados todos los archivos en ai_engine/data/raw/")
    print("Consolidado mensual:", consolidado.shape)
    print(consolidado.head(10))


if __name__ == "__main__":
    main()
