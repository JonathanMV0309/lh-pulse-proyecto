"""Panel de Inteligencia Predictiva L&H V3."""

import json
import threading

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import text

from app.utils.permissions import admin_required
from ai_engine.utils.db import get_engine
from ai_engine.v3.forecaster import goal_probability
from ai_engine.v3.pipeline import run_forecast


ai_dashboard_bp = Blueprint("ai_dashboard", __name__, url_prefix="/ai")
_forecast_lock = threading.Lock()


def _run_and_redirect():
    if not _forecast_lock.acquire(blocking=False):
        flash("Ya existe una actualización de pronósticos en curso.", "warning")
        return redirect(url_for("ai_dashboard.dashboard_ia"))
    try:
        output = run_forecast()
        flash(
            f"Pronóstico V3 publicado: {len(output['stores'])} tiendas, "
            f"ejecución #{output['run_id']}.", "success"
        )
    except Exception:
        current_app.logger.exception("No fue posible ejecutar el pronóstico IA V3")
        flash("No se publicó el pronóstico. Revisa cobertura, migraciones y registro del servidor.", "danger")
    finally:
        _forecast_lock.release()
    return redirect(url_for("ai_dashboard.dashboard_ia"))


@ai_dashboard_bp.route("/actualizar", methods=["POST"])
@admin_required
def actualizar_datos():
    return _run_and_redirect()


@ai_dashboard_bp.route("/reentrenar", methods=["POST"])
@admin_required
def reentrenar_modelos():
    return _run_and_redirect()


def _periods(connection):
    return connection.execute(text("""
        SELECT anio, mes, MAX(id) AS run_id
        FROM ai_v3_runs
        WHERE status = 'SUCCESS'
        GROUP BY anio, mes
        ORDER BY anio DESC, mes DESC
    """)).mappings().all()


def _selected_run(periods):
    if not periods:
        return None
    year = request.args.get("anio", type=int)
    month = request.args.get("mes", type=int)
    return next((row for row in periods if row["anio"] == year and row["mes"] == month), periods[0])


@ai_dashboard_bp.route("/")
@admin_required
def dashboard_ia():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            periods = _periods(connection)
            selected = _selected_run(periods)
            if selected is None:
                return render_template("ai_dashboard.html", periodos=[], tiendas=[], comparacion=[],
                                       lineas=[], alertas=[], run=None,
                                       error="Aún no hay un pronóstico V3 publicado.")
            run_id = int(selected["run_id"])
            run = connection.execute(text("SELECT * FROM ai_v3_runs WHERE id = :id"),
                                     {"id": run_id}).mappings().one()
            stores = connection.execute(text("""
                SELECT f.store_id, s.codigo, s.nombre AS tienda, s.ciudad,
                       SUM(f.venta_p10)::double precision AS venta_p10,
                       SUM(f.venta_p50)::double precision AS venta_p50,
                       SUM(f.venta_p90)::double precision AS venta_p90,
                       MAX(f.trafico_predicho)::double precision AS trafico,
                       MAX(f.facturas_predichas)::double precision AS facturas,
                       MAX(f.conversion_predicha)::double precision AS conversion,
                       MAX(f.ticket_predicho)::double precision AS ticket,
                       SUM(f.meta_recomendada)::double precision AS meta_recomendada,
                       AVG(f.probabilidad_cumplimiento)::double precision AS probabilidad,
                       AVG(f.confianza)::double precision AS confianza,
                       MAX(f.crecimiento_pct)::double precision AS crecimiento
                FROM ai_v3_forecasts f
                JOIN stores s ON s.id = f.store_id
                WHERE f.run_id = :run_id
                GROUP BY f.store_id, s.codigo, s.nombre, s.ciudad
                ORDER BY venta_p50 DESC
            """), {"run_id": run_id}).mappings().all()
            lines = connection.execute(text("""
                SELECT f.store_id, s.nombre AS tienda, l.nombre AS linea,
                       f.venta_p10::double precision AS venta_p10,
                       f.venta_p50::double precision AS venta_p50,
                       f.venta_p90::double precision AS venta_p90,
                       f.meta_oficial::double precision AS meta_oficial,
                       f.meta_recomendada::double precision AS meta_recomendada,
                       f.probabilidad_cumplimiento, f.confianza
                FROM ai_v3_forecasts f
                JOIN stores s ON s.id = f.store_id
                JOIN lines l ON l.id = f.line_id
                WHERE f.run_id = :run_id
                ORDER BY s.nombre, f.venta_p50 DESC
            """), {"run_id": run_id}).mappings().all()
            alerts = connection.execute(text("""
                SELECT a.severidad, a.tipo, a.mensaje, s.nombre AS tienda
                FROM ai_v3_alerts a
                LEFT JOIN stores s ON s.id = a.store_id
                WHERE a.run_id = :run_id
                ORDER BY CASE a.severidad WHEN 'ALTA' THEN 1 WHEN 'MEDIA' THEN 2 ELSE 3 END, a.id
            """), {"run_id": run_id}).mappings().all()
    except Exception:
        current_app.logger.exception("Error leyendo el panel IA V3")
        return render_template("ai_dashboard.html", periodos=[], tiendas=[], comparacion=[],
                               lineas=[], alertas=[], run=None,
                               error="No fue posible leer IA V3. Ejecuta primero las migraciones.")

    stores = [dict(row) for row in stores]
    for row in stores:
        row["probabilidad"] = goal_probability(
            row["venta_p50"], row["venta_p10"], row["venta_p90"], row["meta_recomendada"]
        )
    requested_ids = request.args.getlist("comparar", type=int)
    allowed = {int(row["store_id"]) for row in stores}
    selected_ids = [value for value in requested_ids if value in allowed][:4]
    if not selected_ids:
        selected_ids = [int(row["store_id"]) for row in stores[:3]]
    comparison = [row for row in stores if int(row["store_id"]) in selected_ids]
    diagnostics = run.get("diagnostics") or {}
    if isinstance(diagnostics, str):
        diagnostics = json.loads(diagnostics)
    totals = {
        "venta_p10": sum(float(row["venta_p10"] or 0) for row in stores),
        "venta_p50": sum(float(row["venta_p50"] or 0) for row in stores),
        "venta_p90": sum(float(row["venta_p90"] or 0) for row in stores),
        "trafico": sum(float(row["trafico"] or 0) for row in stores),
        "facturas": sum(float(row["facturas"] or 0) for row in stores),
        "meta": sum(float(row["meta_recomendada"] or 0) for row in stores),
    }
    totals["conversion"] = totals["facturas"] / totals["trafico"] * 100 if totals["trafico"] else 0
    totals["ticket"] = totals["venta_p50"] / totals["facturas"] if totals["facturas"] else 0
    return render_template(
        "ai_dashboard.html", periodos=periods, anio=int(selected["anio"]),
        mes=int(selected["mes"]), tiendas=stores,
        comparacion=comparison, seleccionadas=selected_ids, lineas=[dict(row) for row in lines],
        alertas=[dict(row) for row in alerts], run=dict(run), diagnostico=diagnostics,
        totales=totals, error=None,
    )
