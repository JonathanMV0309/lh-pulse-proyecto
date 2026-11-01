"""Coherencia entre tráfico, conversión, facturas y ticket."""

import numpy as np
import pandas as pd


def build_conversion_history(operations):
    frame = operations[["store_id", "anio", "mes", "trafico", "facturas"]].copy()
    frame["trafico"] = pd.to_numeric(frame["trafico"], errors="coerce")
    frame["facturas"] = pd.to_numeric(frame["facturas"], errors="coerce")
    valid = (
        frame["trafico"].gt(0)
        & frame["facturas"].ge(0)
        & frame["facturas"].le(frame["trafico"])
    )
    frame["conversion"] = np.where(
        valid, frame["facturas"] / frame["trafico"] * 100.0, np.nan
    )
    return frame[["store_id", "anio", "mes", "conversion"]], int((~valid).sum())


def make_operations_coherent(store_rows, conversion_prediction, conversion_history):
    """Deriva facturas desde tráfico × conversión y devuelve métricas consistentes."""
    result = store_rows.merge(
        conversion_prediction[["store_id", "p50", "confidence"]].rename(
            columns={"p50": "conversion_modelo", "confidence": "confianza_conversion"}
        ),
        on="store_id", how="left",
    )
    references = conversion_history.dropna(subset=["conversion"]).groupby(
        "store_id", as_index=False
    )["conversion"].median().rename(columns={"conversion": "conversion_referencia"})
    valid_values = conversion_history["conversion"].dropna()
    global_reference = float(valid_values.median()) if not valid_values.empty else 15.0
    global_reference = float(np.clip(global_reference, 2.0, 70.0))
    result = result.merge(references, on="store_id", how="left")
    result["conversion_referencia"] = result["conversion_referencia"].fillna(global_reference).clip(2, 70)
    result["conversion_modelo"] = result["conversion_modelo"].fillna(
        result["conversion_referencia"]
    )

    # La referencia de cada tienda estabiliza el modelo cuando faltan meses de
    # facturas. Los límites siguen siendo específicos por tienda y nunca > 85%.
    blended = 0.60 * result["conversion_modelo"] + 0.40 * result["conversion_referencia"]
    lower = (result["conversion_referencia"] * 0.55).clip(lower=1.0)
    upper = np.maximum(
        result["conversion_referencia"] * 1.60,
        result["conversion_referencia"] + 5.0,
    ).clip(upper=85.0)
    result["conversion_predicha"] = blended.clip(lower=lower, upper=upper)
    result["trafico_predicho"] = pd.to_numeric(
        result["trafico_predicho"], errors="coerce"
    ).fillna(0.0).clip(lower=0.0)
    result["facturas_predichas"] = (
        result["trafico_predicho"] * result["conversion_predicha"] / 100.0
    ).clip(lower=0.0)
    result["ticket_predicho"] = np.where(
        result["facturas_predichas"] > 0,
        result["venta_p50"] / result["facturas_predichas"],
        0.0,
    )
    return result


def completar_operaciones(operations, compliance, today_period):
    """Deja solo meses de tráfico/facturas completos y corrige los parciales.

    Un mes cuenta como completo si ya terminó y además:
    - ``compliance`` tiene su corte de cierre (se usan esos valores si el
      registro horario quedó corto), o
    - el registro horario tiene al menos 90% de las horas habituales.
    Devuelve ``(operaciones, reporte)``.
    """
    import calendar

    frame = operations.copy()
    for column in ("trafico", "facturas", "horas"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "horas" not in frame:
        frame["horas"] = np.nan
    frame["anio"] = frame["anio"].astype(int)
    frame["mes"] = frame["mes"].astype(int)
    current_index = int(today_period[0]) * 12 + int(today_period[1]) - 1
    frame = frame[frame["anio"] * 12 + frame["mes"] - 1 < current_index].copy()

    closed = pd.DataFrame(columns=["store_id", "anio", "mes", "trafico_cierre", "facturas_cierre"])
    if compliance is not None and not compliance.empty and "trafico" in compliance:
        comp = compliance.copy()
        comp["dia_corte"] = pd.to_numeric(comp["dia_corte"], errors="coerce")
        days = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(comp["anio"], comp["mes"])]
        is_closed = comp["es_cierre"].fillna(False).astype(bool) | (comp["dia_corte"].fillna(0) >= days)
        comp = comp[is_closed & (pd.to_numeric(comp["trafico"], errors="coerce") > 0)]
        closed = comp[["store_id", "anio", "mes", "trafico", "facturas"]].rename(
            columns={"trafico": "trafico_cierre", "facturas": "facturas_cierre"}
        )
        closed["anio"] = closed["anio"].astype(int)
        closed["mes"] = closed["mes"].astype(int)
    frame = frame.merge(closed, on=["store_id", "anio", "mes"], how="left")

    # Percentil 75: la mediana se contamina si varios meses tienen el sensor caído.
    typical_hours = frame[frame["horas"] > 0].groupby("store_id")["horas"].quantile(0.75)
    expected_hours = frame["store_id"].map(typical_hours)
    hours_ok = (frame["horas"] >= 0.9 * expected_hours) & expected_hours.notna()
    has_closed = frame["trafico_cierre"].notna()
    # Registro horario corto con cierre disponible: se usa el cierre oficial.
    use_closed = has_closed & ~hours_ok
    frame.loc[use_closed, "trafico"] = frame.loc[use_closed, "trafico_cierre"]
    frame.loc[use_closed, "facturas"] = frame.loc[use_closed, "facturas_cierre"]
    # Sin horas registradas (meses solo desde compliance) cuentan si hay cierre.
    complete = hours_ok | has_closed
    report = {
        "meses_corregidos_con_cierre": int(use_closed.sum()),
        "meses_incompletos_excluidos": int((~complete).sum()),
    }
    frame = frame[complete].drop(columns=["trafico_cierre", "facturas_cierre"])
    return frame.reset_index(drop=True), report


def ultimo_mes_operaciones(operations, stores, cutoff_period, min_share=0.9, max_lookback=3):
    """Último mes ≤ corte con datos operativos completos para la mayoría de tiendas."""
    total = max(len(stores), 1)
    year, month = cutoff_period
    for step in range(max_lookback):
        index = year * 12 + month - 1 - step
        period = (index // 12, index % 12 + 1)
        found = operations[(operations["anio"] == period[0]) & (operations["mes"] == period[1])]
        found = found[pd.to_numeric(found["trafico"], errors="coerce") > 0]["store_id"].nunique()
        if found / total >= min_share:
            return period
    return None
