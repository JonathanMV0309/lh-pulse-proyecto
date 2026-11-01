"""Ajuste al corte para no volver a pronosticar ventas que ya ocurrieron."""

import calendar

import numpy as np
import pandas as pd


# Una curva solo se usa si a ese día la tienda suele llevar entre 4% y 97% del
# mes; fuera de ese rango la división amplifica demasiado el ruido.
SHARE_LIMITS = (0.04, 0.97)


def build_progress_shares(daily, year, month, day):
    """Fracción del mes que cada tienda suele llevar vendida al día ``day``.

    Usa ``daily_store_sales`` de meses cerrados anteriores. Prioridad:
    1. el mismo mes calendario de años anteriores (captura quincenas, prima,
       diciembre, Día de la Madre);
    2. la mediana de los últimos meses cerrados de la tienda;
    3. la mediana de la red para ese mes, o para cualquier mes.
    Devuelve ``(shares_por_tienda, share_red)``; vacío si no hay datos.
    """
    if daily is None or daily.empty or not day:
        return {}, None
    frame = daily.copy()
    for column in ("anio", "mes", "dia", "dia_corte"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["venta"] = pd.to_numeric(frame["venta"], errors="coerce").fillna(0).clip(lower=0)
    frame = frame.dropna(subset=["anio", "mes", "dia"])
    target_index = int(year) * 12 + int(month) - 1
    frame["_p"] = frame["anio"].astype(int) * 12 + frame["mes"].astype(int) - 1
    frame = frame[frame["_p"] < target_index]
    if frame.empty:
        return {}, None

    # Para cada tienda/mes se toma la versión más avanzada del archivo.
    latest = frame.groupby(["store_id", "anio", "mes"])["dia_corte"].transform("max")
    frame = frame[frame["dia_corte"] == latest]
    days = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(frame["anio"], frame["mes"])]
    closed = frame["es_cierre"].fillna(False).astype(bool) | (frame["dia_corte"] >= np.asarray(days))
    frame = frame[closed]
    if frame.empty:
        return {}, None

    rows = []
    for (store_id, y, m), group in frame.groupby(["store_id", "anio", "mes"]):
        total = group["venta"].sum()
        if total <= 0:
            continue
        month_days = calendar.monthrange(int(y), int(m))[1]
        # Mismo día relativo si el mes tiene otro número de días.
        equivalent = min(int(round(day * month_days / calendar.monthrange(int(year), int(month))[1])), month_days)
        share = group.loc[group["dia"] <= equivalent, "venta"].sum() / total
        rows.append({"store_id": int(store_id), "anio": int(y), "mes": int(m), "share": float(share)})
    shares = pd.DataFrame(rows)
    if shares.empty:
        return {}, None
    shares = shares[shares["share"].between(*SHARE_LIMITS)]
    if shares.empty:
        return {}, None

    same_month = shares[shares["mes"] == int(month)]
    network_same = float(same_month["share"].median()) if not same_month.empty else None
    network_any = float(shares["share"].median())
    result = {}
    for store_id, group in shares.groupby("store_id"):
        own_same = group[group["mes"] == int(month)].sort_values("anio")
        if not own_same.empty:
            result[int(store_id)] = float(own_same["share"].iloc[-1])
        else:
            recent = group.sort_values(["anio", "mes"]).tail(6)["share"]
            store_value = float(recent.median())
            # Combina la forma propia de la tienda con la estacionalidad de la red.
            if network_same is not None:
                store_value = 0.5 * store_value + 0.5 * network_same
            result[int(store_id)] = store_value
    return result, (network_same if network_same is not None else network_any)


def _central_at_cutoff(actual, baseline, day, days_in_month, max_daily_factor=1.35, share=None):
    actual = max(float(actual or 0), 0.0)
    baseline = max(float(baseline or 0), 0.0)
    day = int(np.clip(day or 0, 1, days_in_month))
    remaining_days = max(days_in_month - day, 0)
    if remaining_days == 0:
        return actual

    completion = day / days_in_month
    if share is not None and SHARE_LIMITS[0] <= share <= SHARE_LIMITS[1]:
        # Curva real: lo vendido ÷ la fracción del mes que suele llevarse a
        # este día (los finales de mes y diciembre no son lineales).
        pace_projection = actual / share
        completion = share
    else:
        daily_pace = actual / day
        pace_projection = actual + daily_pace * remaining_days
    # El histórico mensual pierde peso conforme conocemos más del mes real.
    model_weight = float(np.clip((1.0 - completion) * 0.55, 0.05, 0.50))
    central = model_weight * baseline + (1.0 - model_weight) * pace_projection
    # Para vender por encima de este límite tendría que acelerarse más de 35%
    # frente al ritmo esperado; esa aceleración no se presume.
    upper = actual + max(pace_projection - actual, 0.0) * max_daily_factor
    return float(np.clip(central, actual, max(upper, actual)))


def apply_sales_nowcast(forecasts, actual_stores, actual_lines, year, month, daily=None):
    """Combina pronóstico mensual con ventas reales y estima solo lo restante."""
    result = forecasts.copy()
    if actual_stores.empty:
        return result, {"active": False, "reason": "sin_corte_real"}
    snapshot_days = pd.to_numeric(actual_stores.get("dia_corte"), errors="coerce").dropna()
    curve_day = int(snapshot_days.max()) if not snapshot_days.empty else 0
    shares, network_share = build_progress_shares(daily, year, month, curve_day)
    curve_stores = 0

    days_in_month = calendar.monthrange(int(year), int(month))[1]
    actual_lookup = actual_stores.set_index("store_id").to_dict("index")
    line_lookup = {}
    if not actual_lines.empty:
        for store_id, group in actual_lines.groupby("store_id"):
            line_lookup[int(store_id)] = {
                int(row.line_id): max(float(row.venta_actual_linea or 0), 0.0)
                for row in group.itertuples()
            }

    adjusted = []
    active_stores = 0
    cutoff_days = []
    actual_total = 0.0
    baseline_total = float(pd.to_numeric(result["p50"], errors="coerce").fillna(0).sum())
    for store_id, group in result.groupby("store_id", sort=False):
        group = group.copy()
        snapshot = actual_lookup.get(int(store_id))
        if not snapshot or float(snapshot.get("venta_actual") or 0) <= 0:
            adjusted.append(group)
            continue

        actual = max(float(snapshot["venta_actual"]), 0.0)
        day = int(snapshot.get("dia_corte") or 0)
        if day <= 0:
            adjusted.append(group)
            continue
        day = min(day, days_in_month)
        baseline = float(group["p50"].sum())
        share = None
        if day == curve_day:
            share = shares.get(int(store_id), network_share)
        elif shares or network_share:
            store_shares, store_network = build_progress_shares(daily, year, month, day)
            share = store_shares.get(int(store_id), store_network)
        if share is not None:
            curve_stores += 1
        central = _central_at_cutoff(actual, baseline, day, days_in_month, share=share)
        remaining = max(central - actual, 0.0)

        baseline_shares = pd.to_numeric(group["p50"], errors="coerce").fillna(0).clip(lower=0)
        if baseline_shares.sum() <= 0:
            baseline_shares = pd.Series(1.0, index=group.index)
        baseline_shares = baseline_shares / baseline_shares.sum()

        raw_lines = line_lookup.get(int(store_id), {})
        raw = pd.Series(
            [raw_lines.get(int(line_id), 0.0) for line_id in group["line_id"]],
            index=group.index, dtype=float,
        )
        actual_shares = raw / raw.sum() if raw.sum() > 0 else baseline_shares
        actual_by_line = actual * actual_shares

        original_p50 = pd.to_numeric(group["p50"], errors="coerce").fillna(0).clip(lower=0)
        low_ratio = np.divide(
            pd.to_numeric(group["p10"], errors="coerce").fillna(0),
            original_p50, out=np.full(len(group), 0.75), where=original_p50 > 0,
        )
        high_ratio = np.divide(
            pd.to_numeric(group["p90"], errors="coerce").fillna(0),
            original_p50, out=np.full(len(group), 1.25), where=original_p50 > 0,
        )
        remaining_by_line = remaining * baseline_shares
        group["p50"] = actual_by_line + remaining_by_line
        group["p10"] = actual_by_line + remaining_by_line * np.clip(low_ratio, 0.45, 1.0)
        group["p90"] = actual_by_line + remaining_by_line * np.clip(high_ratio, 1.0, 1.55)
        adjusted.append(group)
        active_stores += 1
        cutoff_days.append(day)
        actual_total += actual

    output = pd.concat(adjusted, ignore_index=True) if adjusted else result
    return output, {
        "active": active_stores > 0,
        "method": "actual_mas_curva_diaria" if curve_stores else "actual_mas_ritmo_restante_acotado",
        "stores_with_daily_curve": curve_stores,
        "stores_with_actuals": active_stores,
        "cutoff_day": max(cutoff_days) if cutoff_days else None,
        "days_in_month": days_in_month,
        "actual_sales_total": actual_total,
        "model_total_before_nowcast": baseline_total,
        "forecast_total_after_nowcast": float(output["p50"].sum()),
        "remaining_sales_forecast": max(float(output["p50"].sum()) - actual_total, 0.0),
    }


def apply_operations_nowcast(store_rows, actual_stores, year, month):
    """Ajusta tráfico/facturas al corte y mantiene conversión y ticket coherentes."""
    if actual_stores.empty:
        return store_rows
    result = store_rows.copy()
    metric_columns = (
        "venta_p50", "trafico_predicho", "facturas_predichas",
        "conversion_predicha", "ticket_predicho",
    )
    for column in metric_columns:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0).astype(float)
    lookup = actual_stores.set_index("store_id").to_dict("index")
    days_in_month = calendar.monthrange(int(year), int(month))[1]
    for index, row in result.iterrows():
        snapshot = lookup.get(int(row["store_id"]))
        if not snapshot:
            continue
        day = int(snapshot.get("dia_corte") or 0)
        if day <= 0:
            continue
        traffic_actual = max(float(snapshot.get("trafico_actual") or 0), 0.0)
        invoices_actual = max(float(snapshot.get("facturas_actual") or 0), 0.0)
        if traffic_actual > 0:
            traffic = _central_at_cutoff(
                traffic_actual, row.get("trafico_predicho", 0), day, days_in_month
            )
            result.at[index, "trafico_predicho"] = traffic
        else:
            traffic = max(float(row.get("trafico_predicho") or 0), 0.0)

        # Solo se usa el acumulado de facturas si es compatible con el tráfico.
        valid_invoices = traffic_actual > 0 and 0 <= invoices_actual <= traffic_actual
        if valid_invoices:
            invoices = _central_at_cutoff(
                invoices_actual, row.get("facturas_predichas", 0), day, days_in_month
            )
            invoices = min(invoices, traffic * 0.85)
        else:
            invoices = min(max(float(row.get("facturas_predichas") or 0), 0.0), traffic * 0.85)
        result.at[index, "facturas_predichas"] = invoices
        result.at[index, "conversion_predicha"] = invoices / traffic * 100 if traffic else 0.0
        result.at[index, "ticket_predicho"] = (
            float(row.get("venta_p50") or 0) / invoices if invoices else 0.0
        )
    return result
