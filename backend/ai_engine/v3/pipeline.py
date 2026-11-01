"""Pipeline completo del motor L&H V3."""

import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text

from . import VERSION
from .config import ForecastConfig
from .data_sources import (
    load_actual_line_sales,
    load_actual_snapshot,
    load_compliance_totals,
    load_daily_sales,
    load_external_city_features,
    load_goals,
    load_lines,
    load_sales,
    load_store_operations,
    load_stores,
)
from .historia import armar_historia, ultimo_mes_completo
from .db import get_engine
from .forecaster import forecast_panel, goal_probability
from .operational import (
    build_conversion_history,
    completar_operaciones,
    make_operations_coherent,
    ultimo_mes_operaciones,
)
from .nowcast import apply_operations_nowcast, apply_sales_nowcast
from .reconciliation import reconcile_sales
from .serialization import json_safe


def _sales_entities(stores, lines):
    return stores[["store_id"]].assign(_join=1).merge(
        lines[["line_id"]].assign(_join=1), on="_join"
    ).drop(columns="_join")


def _sales_dimensions(entities, stores, lines):
    return entities.merge(stores, on="store_id", how="left").merge(lines, on="line_id", how="left")


def _historical_store_metrics(sales, operations, year, month):
    sales_store = sales.groupby(["store_id", "anio", "mes"], as_index=False)["venta"].sum()
    current = sales_store[(sales_store["anio"] == year) & (sales_store["mes"] == month)][
        ["store_id", "venta"]
    ].rename(columns={"venta": "venta_ultimo_mes"})
    previous = sales_store[(sales_store["anio"] == year - 1) & (sales_store["mes"] == month)][
        ["store_id", "venta"]
    ].rename(columns={"venta": "venta_anio_anterior"})
    ops_current = operations[(operations["anio"] == year - 1) & (operations["mes"] == month)][
        ["store_id", "trafico", "facturas"]
    ].rename(columns={"trafico": "trafico_ultimo_mes", "facturas": "facturas_ultimo_mes"})
    return current.merge(previous, on="store_id", how="outer").merge(
        ops_current, on="store_id", how="outer"
    ).fillna(0.0)


def _recommended_goal(p50, p90, official):
    if official and official > 0:
        return float(official)
    return float(min(p50 * 1.03, p90))


def _build_alerts(store_rows):
    alerts = []
    for row in store_rows.to_dict("records"):
        store_id = int(row["store_id"])
        store = row.get("tienda") or f"Tienda {store_id}"
        growth = float(row.get("crecimiento_pct") or 0.0)
        if growth <= -10:
            alerts.append((store_id, None, "VENTA", "ALTA",
                           f"{store}: venta pronosticada {abs(growth):.1f}% menor frente al año anterior."))
        traffic_growth = float(row.get("crecimiento_trafico_pct") or 0.0)
        if traffic_growth <= -10:
            alerts.append((store_id, None, "TRAFICO", "MEDIA",
                           f"{store}: el tráfico podría bajar {abs(traffic_growth):.1f}%."))
        conversion = float(row.get("conversion_predicha") or 0.0)
        if conversion > 0 and conversion < 10:
            alerts.append((store_id, None, "CONVERSION", "MEDIA",
                           f"{store}: conversión pronosticada baja ({conversion:.1f}%)."))
        probability = row.get("probabilidad_cumplimiento")
        if probability is not None and float(probability) < 0.40:
            alerts.append((store_id, None, "META", "ALTA",
                           f"{store}: riesgo alto de no alcanzar la meta ({float(probability) * 100:.1f}%)."))
    return alerts


def _persist(engine, result, store_rows, alerts, diagnostics, config, data_cutoff=None):
    year, month = config.forecast_period
    cutoff_year, cutoff_month = data_cutoff or (config.cutoff_year, config.cutoff_month)
    now = datetime.now(timezone.utc)
    safe_diagnostics = json_safe(diagnostics)
    with engine.begin() as connection:
        run_id = connection.execute(text("""
            INSERT INTO ai_v3_runs (
                anio, mes, cutoff_anio, cutoff_mes, created_at, model_version,
                status, coverage, wape, reference_total, forecast_total, diagnostics
            ) VALUES (
                :anio, :mes, :cutoff_anio, :cutoff_mes, :created_at, :model_version,
                'SUCCESS', :coverage, :wape, :reference_total, :forecast_total,
                CAST(:diagnostics AS JSONB)
            ) RETURNING id
        """), {
            "anio": year, "mes": month,
            "cutoff_anio": cutoff_year, "cutoff_mes": cutoff_month,
            "created_at": now, "model_version": VERSION,
            "coverage": safe_diagnostics["coverage"],
            "wape": safe_diagnostics["sales"]["wape"],
            "reference_total": safe_diagnostics["reconciliation"]["reference_total"],
            "forecast_total": safe_diagnostics["reconciliation"]["forecast_total"],
            "diagnostics": json.dumps(
                safe_diagnostics, ensure_ascii=False, allow_nan=False
            ),
        }).scalar_one()

        store_lookup = store_rows.set_index("store_id").to_dict("index")
        for row in result.to_dict("records"):
            store = store_lookup[int(row["store_id"])]
            official = float(row.get("meta") or 0.0)
            goal = _recommended_goal(float(row["p50"]), float(row["p90"]), official)
            probability = goal_probability(row["p50"], row["p10"], row["p90"], goal)
            connection.execute(text("""
                INSERT INTO ai_v3_forecasts (
                    run_id, store_id, line_id, anio, mes,
                    venta_p10, venta_p50, venta_p90, trafico_predicho,
                    facturas_predichas, conversion_predicha, ticket_predicho,
                    meta_oficial, meta_recomendada, probabilidad_cumplimiento,
                    confianza, crecimiento_pct
                ) VALUES (
                    :run_id, :store_id, :line_id, :anio, :mes,
                    :p10, :p50, :p90, :trafico, :facturas, :conversion, :ticket,
                    :meta_oficial, :meta_recomendada, :probabilidad, :confianza,
                    :crecimiento
                )
            """), {
                "run_id": run_id, "store_id": int(row["store_id"]),
                "line_id": int(row["line_id"]), "anio": year, "mes": month,
                "p10": float(row["p10"]), "p50": float(row["p50"]), "p90": float(row["p90"]),
                "trafico": float(store["trafico_predicho"]),
                "facturas": float(store["facturas_predichas"]),
                "conversion": float(store["conversion_predicha"]),
                "ticket": float(store["ticket_predicho"]),
                "meta_oficial": official or None, "meta_recomendada": goal,
                "probabilidad": probability, "confianza": float(row["confidence"]),
                "crecimiento": float(store["crecimiento_pct"]),
            })
            # Compatibilidad con el panel V2 durante la transición.
            legacy_params = {
                "store_id": int(row["store_id"]),
                "line_id": int(row["line_id"]),
                "anio": year,
                "mes": month,
                "venta": float(row["p50"]),
                "probabilidad": probability,
                "fecha": now,
                "version": VERSION,
            }
            connection.execute(text("""
                DELETE FROM ai_forecast_results
                WHERE store_id = :store_id AND line_id = :line_id
                  AND anio = :anio AND mes = :mes
            """), legacy_params)
            connection.execute(text("""
                INSERT INTO ai_forecast_results
                    (store_id, line_id, anio, mes, venta_predicha, fecha_generacion, modelo_version)
                VALUES (:store_id, :line_id, :anio, :mes, :venta, :fecha, :version)
            """), legacy_params)
            connection.execute(text("""
                DELETE FROM ai_compliance_predictions
                WHERE store_id = :store_id AND line_id = :line_id
                  AND anio = :anio AND mes = :mes
            """), legacy_params)
            connection.execute(text("""
                INSERT INTO ai_compliance_predictions
                    (store_id, line_id, anio, mes, probabilidad_cumplimiento,
                     fecha_generacion, modelo_version)
                VALUES (:store_id, :line_id, :anio, :mes, :probabilidad, :fecha, :version)
            """), legacy_params)

        for store_id, line_id, kind, severity, message in alerts:
            connection.execute(text("""
                INSERT INTO ai_v3_alerts
                    (run_id, store_id, line_id, tipo, severidad, mensaje, data)
                VALUES (:run_id, :store_id, :line_id, :tipo, :severidad, :mensaje, '{}'::jsonb)
            """), {"run_id": run_id, "store_id": store_id, "line_id": line_id,
                     "tipo": kind, "severidad": severity, "mensaje": message})
    return int(run_id)


def run_forecast(config=None, engine=None, persist=True, today=None):
    config = config or ForecastConfig.from_environment()
    engine = engine or get_engine()
    today = today or date.today()
    today_period = (today.year, today.month)
    stores = load_stores(engine)
    lines = load_lines(engine, config.lines)
    # Se carga todo el histórico (sin filtro de corte) para detectar registros
    # con el año corrido; el corte se aplica al armar la historia limpia.
    raw_sales = load_sales(engine, 999912)
    compliance = load_compliance_totals(engine)
    raw_operations = load_store_operations(engine, config.cutoff_period)
    daily = load_daily_sales(engine)
    external = load_external_city_features()
    if stores.empty or lines.empty:
        raise ValueError("No existen tiendas o líneas activas para pronosticar")

    # Solo tiendas activas reales. Los archivos traen una fila "TOTAL" de la
    # red que se guarda como si fuera una tienda; si entra a la historia o a
    # la referencia, duplica el total y descuadra la reconciliación.
    active_ids = set(stores["store_id"].astype(int))
    raw_sales = raw_sales[raw_sales["store_id"].astype(int).isin(active_ids)]
    compliance = compliance[compliance["store_id"].astype(int).isin(active_ids)]
    raw_operations = raw_operations[raw_operations["store_id"].astype(int).isin(active_ids)]
    daily = daily[daily["store_id"].astype(int).isin(active_ids)] if not daily.empty else daily

    entities = _sales_entities(stores, lines)
    cutoff_period = (config.cutoff_year, config.cutoff_month)
    sales, data_quality = armar_historia(raw_sales, compliance, today_period, cutoff_period)
    data_cutoff, (coverage, expected, found) = ultimo_mes_completo(
        sales, entities, cutoff_period, config.min_coverage
    )
    if data_cutoff is None:
        raise ValueError(
            f"Cobertura insuficiente en {config.cutoff_year}-{config.cutoff_month:02d}: "
            f"{found}/{expected} ({coverage * 100:.1f}%) y ninguno de los dos meses "
            "anteriores está completo. No se publicaron resultados."
        )

    future_period = config.forecast_period
    actual_snapshot = load_actual_snapshot(engine, *future_period)
    actual_line_sales = load_actual_line_sales(engine, *future_period)
    sales_forecast = forecast_panel(
        sales, entities, _sales_dimensions(entities, stores, lines),
        ["store_id", "line_id"], "venta",
        data_cutoff, future_period,
        config.validation_months, config.min_history_months, external,
    )
    result, reconciliation = reconcile_sales(
        sales_forecast.rows, sales, config, cutoff=data_cutoff, forecast_period=future_period
    )
    result, nowcast = apply_sales_nowcast(
        result, actual_snapshot, actual_line_sales, *future_period, daily=daily
    )
    reconciliation["forecast_total_before_nowcast"] = reconciliation["forecast_total"]
    reconciliation["forecast_total"] = float(result["p50"].sum())
    if reconciliation.get("reference_total"):
        reconciliation["forecast_reference_ratio"] = (
            reconciliation["forecast_total"] / reconciliation["reference_total"]
        )

    operations, operations_quality = completar_operaciones(raw_operations, compliance, today_period)
    operations_cutoff = ultimo_mes_operaciones(operations, stores, cutoff_period) or data_cutoff
    store_entities = stores[["store_id"]]
    store_dimensions = stores.copy()
    traffic_forecast = forecast_panel(
        operations[["store_id", "anio", "mes", "trafico"]], store_entities,
        store_dimensions, ["store_id"], "trafico",
        operations_cutoff, future_period,
        config.validation_months, config.min_history_months, external,
    )
    conversion_history, invalid_operation_rows = build_conversion_history(operations)
    conversion_forecast = forecast_panel(
        conversion_history, store_entities,
        store_dimensions, ["store_id"], "conversion",
        operations_cutoff, future_period,
        config.validation_months, config.min_history_months, external,
    )

    store_rows = result.groupby("store_id", as_index=False).agg(
        venta_p10=("p10", "sum"), venta_p50=("p50", "sum"), venta_p90=("p90", "sum")
    )
    store_rows = store_rows.merge(
        traffic_forecast.rows[["store_id", "p50"]].rename(columns={"p50": "trafico_predicho"}),
        on="store_id", how="left"
    ).merge(stores, on="store_id", how="left")
    store_rows = make_operations_coherent(
        store_rows, conversion_forecast.rows, conversion_history
    )
    store_rows = apply_operations_nowcast(
        store_rows, actual_snapshot, *future_period
    )
    historical = _historical_store_metrics(
        sales, operations, *future_period
    )
    store_rows = store_rows.merge(historical, on="store_id", how="left").fillna(0.0)
    store_rows["crecimiento_pct"] = np.where(
        store_rows["venta_anio_anterior"] > 0,
        (store_rows["venta_p50"] / store_rows["venta_anio_anterior"] - 1) * 100, 0.0
    )
    store_rows["crecimiento_trafico_pct"] = np.where(
        store_rows["trafico_ultimo_mes"] > 0,
        (store_rows["trafico_predicho"] / store_rows["trafico_ultimo_mes"] - 1) * 100, 0.0
    )

    goals = load_goals(engine, *future_period)
    result = result.merge(goals, on=["store_id", "line_id"], how="left")
    result["meta"] = result["meta"].fillna(0.0)
    store_goals = result.assign(
        meta_efectiva=result.apply(
            lambda row: _recommended_goal(row["p50"], row["p90"], row["meta"]), axis=1
        )
    ).groupby("store_id", as_index=False)["meta_efectiva"].sum()
    store_rows = store_rows.merge(store_goals, on="store_id", how="left")
    store_rows["probabilidad_cumplimiento"] = store_rows.apply(
        lambda row: goal_probability(row["venta_p50"], row["venta_p10"],
                                     row["venta_p90"], row["meta_efectiva"]), axis=1
    )
    alerts = _build_alerts(store_rows)

    tracking = []
    try:
        from .seguimiento import evaluar_pronosticos
        tracking = evaluar_pronosticos(engine, compliance, limit=6)
    except Exception as error:  # el seguimiento nunca debe impedir publicar
        tracking = [{"error": str(error)[:200]}]

    diagnostics = {
        "coverage": coverage, "expected_combinations": expected, "found_combinations": found,
        "data_cutoff": f"{data_cutoff[0]}-{data_cutoff[1]:02d}",
        "requested_cutoff": f"{cutoff_period[0]}-{cutoff_period[1]:02d}",
        "operations_cutoff": f"{operations_cutoff[0]}-{operations_cutoff[1]:02d}",
        "external_features_loaded": not external.empty,
        "data_quality": data_quality,
        "operations_quality": operations_quality,
        "sales": sales_forecast.diagnostics,
        "nowcast": nowcast,
        "traffic": traffic_forecast.diagnostics,
        "conversion": conversion_forecast.diagnostics,
        "invoices": {
            "strategy": "trafico_por_conversion_coherente",
            "invalid_history_rows_excluded": invalid_operation_rows,
        },
        "reconciliation": reconciliation,
        "tracking": tracking,
    }
    run_id = (
        _persist(engine, result, store_rows, alerts, diagnostics, config, data_cutoff)
        if persist else None
    )
    return {"run_id": run_id, "forecast": result, "stores": store_rows,
            "alerts": alerts, "diagnostics": diagnostics}
