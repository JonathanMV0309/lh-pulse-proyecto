"""Importa correctamente la hoja INF4: ventas mensuales por tienda y línea."""

from pathlib import Path

import numpy as np
import pandas as pd

from ai_engine.config import DATA_RAW


RUTA_EXCEL = DATA_RAW / "historico_2024_2025" / "historico_2024_2025.xlsx"
MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}


def limpiar_texto(value):
    if pd.isna(value):
        return None
    text = " ".join(str(value).strip().upper().split())
    if not text or text.startswith("TOTAL"):
        return None
    replacements = {
        "Ã‘": "Ñ", "Ã‰": "É", "Ã“": "Ó", "ÃÍ": "Í", "Â": "",
        "PEQUEÃ‘O": "PEQUEÑO", "MEDELLÃN": "MEDELLÍN",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _columnas_mensuales(df: pd.DataFrame) -> list[tuple[int, int, int]]:
    """Detecta cada bloque por sus encabezados reales, sin posiciones mágicas."""
    columns = []
    for col in range(df.shape[1] - 1):
        month_name = limpiar_texto(df.iat[2, col])
        if month_name not in MESES:
            continue
        year_1 = pd.to_numeric(df.iat[3, col], errors="coerce")
        year_2 = pd.to_numeric(df.iat[3, col + 1], errors="coerce")
        if pd.isna(year_1) or pd.isna(year_2) or int(year_1) != 2024 or int(year_2) != 2025:
            raise ValueError(f"Encabezado inesperado para {month_name}: {year_1}, {year_2}")
        columns.append((MESES[month_name], col, col + 1))
    if len(columns) != 12:
        raise ValueError(f"INF4 debe contener 12 meses; encontrados: {len(columns)}")
    return columns


def procesar_inf4(ruta_excel: Path = RUTA_EXCEL) -> pd.DataFrame:
    df = pd.read_excel(ruta_excel, sheet_name="INF4", header=None)
    df.iloc[:, 0] = df.iloc[:, 0].ffill()
    monthly_columns = _columnas_mensuales(df)
    records = []

    for _, row in df.iloc[4:].iterrows():
        line = limpiar_texto(row.iloc[0])
        store = limpiar_texto(row.iloc[1])
        if not line or not store or not store.startswith(("S-", "S ")):
            continue
        for month, col_2024, col_2025 in monthly_columns:
            for year, col in ((2024, col_2024), (2025, col_2025)):
                value = pd.to_numeric(row.iloc[col], errors="coerce")
                records.append({
                    "linea": line,
                    "tienda": store,
                    "mes": month,
                    "anio": year,
                    "venta_pesos": float(value) if pd.notna(value) else np.nan,
                })

    result = pd.DataFrame(records)
    if result.empty:
        raise ValueError("INF4 no produjo registros")
    return result


def main():
    result = procesar_inf4()
    output = DATA_RAW / "historico_inf4_mensual_pesos_linea.parquet"
    result.to_parquet(output, index=False)
    valid = result["venta_pesos"].dropna()
    print(f"INF4 guardado: {len(result)} filas -> {output}")
    print(f"Ventas válidas: {len(valid)}; total: {valid.sum():,.0f}")


if __name__ == "__main__":
    main()
