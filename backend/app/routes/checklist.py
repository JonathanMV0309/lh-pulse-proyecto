import os
from datetime import date
from flask import Blueprint, render_template, request, jsonify, session, abort
from sqlalchemy import func
from app.extensions import db
from app.models.user import User
from app.models.store import Store
from app.models.compliance import Compliance
from app.models.advisor import Advisor
from app.models.advisor_performance import AdvisorPerformance
from app.models.sales_history_line import SalesHistoryLine
from app.models.line import Line
from app.models.meta_line import MetaLine
from app.models.checklist import ChecklistVisita
from app.services.advisor_goal_service import (
    calcular_metas_asesoras,
    obtener_meta_tienda,
)

checklist_bp = Blueprint("checklist", __name__, url_prefix="/checklist")

# Correos con acceso a la evaluación de visitas: se leen del .env (CORREOS_SUPERVISORAS).
EMAILS_SUPERVISORAS = {
    c.strip().lower()
    for c in os.getenv("CORREOS_SUPERVISORAS", "").split(",")
    if c.strip()
}

def _obtener_usuario_autorizado():
    if "user_id" not in session:
        abort(401)
    usuario = User.query.get(session["user_id"])
    if not usuario or usuario.correo.lower() not in EMAILS_SUPERVISORAS:
        abort(403)
    return usuario


def _obtener_unidades_tienda(store_id, anio, mes):
    """Suma las unidades activas de todas las asesoras de una tienda."""
    return int(
        db.session.query(func.sum(AdvisorPerformance.unidades)).filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.activo.is_(True)
        ).scalar() or 0
    )


def _metas_asesoras_para_checklist(store_id, anio, mes):
    """Usa la misma fuente de metas que los dashboards y rankings."""
    distribucion = calcular_metas_asesoras(
        store_id=store_id,
        anio=anio,
        mes=mes,
        meta_tienda=obtener_meta_tienda(store_id, anio, mes),
    )
    return {
        item["advisor_id"]: item
        for item in distribucion.get("asesoras", [])
    }

@checklist_bp.route("/")
def index():
    usuario = _obtener_usuario_autorizado()
    tiendas = Store.query.filter_by(estado="ACTIVA").order_by(Store.codigo).all()
    return render_template("checklist.html", tiendas=tiendas, usuario=usuario, hoy=date.today().isoformat())

@checklist_bp.route("/api/datos")
def api_datos():
    usuario = _obtener_usuario_autorizado()
    store_id = request.args.get("store_id", type=int)
    fecha_str = request.args.get("fecha")

    try:
        if not store_id or not fecha_str:
            return jsonify({"error": "Faltan parámetros"}), 400

        fecha = date.fromisoformat(fecha_str)
        store = Store.query.get(store_id)
        if not store:
            return jsonify({"error": "Tienda no encontrada"}), 404

        compliance = Compliance.query.filter_by(
            store_id=store_id,
            anio=fecha.year,
            mes=fecha.month
        ).filter(Compliance.activo == True).order_by(Compliance.dia_corte.desc()).first()

        if not compliance:
            compliance = Compliance.query.filter_by(
                store_id=store_id,
                anio=fecha.year,
                mes=fecha.month
            ).order_by(Compliance.dia_corte.desc()).first()

        if not compliance:
            return jsonify({"error": "No hay datos de compliance para el período"}), 404

        venta_2025 = float(compliance.venta_anterior or 0)
        venta_2026 = float(compliance.venta_actual or 0)
        diferencia = venta_2026 - venta_2025
        variacion = (diferencia / venta_2025 * 100) if venta_2025 > 0 else 0

        cuota_total = float(getattr(compliance, "cuota_total", 0) or 0)
        dias_mes = 30
        dias_transcurridos = fecha.day if fecha.day <= dias_mes else dias_mes
        cuota_proporcional = cuota_total * (dias_transcurridos / dias_mes) if cuota_total > 0 else 0
        cumplimiento_proporcional = (venta_2026 / cuota_proporcional * 100) if cuota_proporcional > 0 else 0
        falta_cuota_total = max(cuota_total - venta_2026, 0)
        dias_restantes = dias_mes - dias_transcurridos
        meta_promedio_dia = (falta_cuota_total / dias_restantes) if dias_restantes > 0 else 0

        trafico_2025 = int(getattr(compliance, "trafico", 0) or 0)
        trafico_2026 = int(getattr(compliance, "trafico", 0) or 0)
        facturas_2025 = int(getattr(compliance, "facturas", 0) or 0)
        facturas_2026 = int(getattr(compliance, "facturas", 0) or 0)
        conversion = (facturas_2026 / trafico_2026 * 100) if trafico_2026 > 0 else 0

        unidades_2025 = _obtener_unidades_tienda(store_id, fecha.year - 1, fecha.month)
        unidades_2026 = _obtener_unidades_tienda(store_id, fecha.year, fecha.month)
        ticket_promedio = (venta_2026 / facturas_2026) if facturas_2026 > 0 else 0
        ticket_unidades = (unidades_2026 / facturas_2026) if facturas_2026 > 0 else 0

        categorias = []
        lineas = Line.query.filter(Line.id.in_([1, 2, 3, 4])).all()
        for linea in lineas:
            venta_2025_linea = float(db.session.query(
                func.sum(SalesHistoryLine.venta)
            ).filter(
                SalesHistoryLine.store_id == store_id,
                SalesHistoryLine.line_id == linea.id,
                SalesHistoryLine.anio == 2025,
                SalesHistoryLine.mes == fecha.month
            ).scalar() or 0)
            venta_2026_linea = float(db.session.query(
                func.sum(SalesHistoryLine.venta)
            ).filter(
                SalesHistoryLine.store_id == store_id,
                SalesHistoryLine.line_id == linea.id,
                SalesHistoryLine.anio == 2026,
                SalesHistoryLine.mes == fecha.month
            ).scalar() or 0)
            meta_linea = float(db.session.query(
                MetaLine.meta
            ).filter(
                MetaLine.store_id == store_id,
                MetaLine.line_id == linea.id,
                MetaLine.anio == fecha.year,
                MetaLine.mes == fecha.month
            ).scalar() or 0)
            meta_proporcional_linea = meta_linea * (dias_transcurridos / dias_mes) if meta_linea > 0 else 0
            cumplimiento_linea = (venta_2026_linea / meta_proporcional_linea * 100) if meta_proporcional_linea > 0 else 0

            categorias.append({
                "nombre": linea.nombre,
                "venta_2025": venta_2025_linea,
                "venta_2026": venta_2026_linea,
                "diferencia": venta_2026_linea - venta_2025_linea,
                "variacion": ((venta_2026_linea - venta_2025_linea) / venta_2025_linea * 100) if venta_2025_linea > 0 else 0,
                "meta": meta_linea,
                "meta_proporcional": meta_proporcional_linea,
                "cumplimiento": cumplimiento_linea
            })

        asesores = []
        performances = AdvisorPerformance.query.filter_by(
            store_id=store_id,
            anio=fecha.year,
            mes=fecha.month
        ).filter(AdvisorPerformance.activo == True).all()
        metas_asesoras = _metas_asesoras_para_checklist(
            store_id, fecha.year, fecha.month
        )

        for perf in performances:
            venta_asesor = float(perf.venta or 0)
            unidades_asesor = int(perf.unidades or 0)
            facturas_asesor = int(perf.facturas or 0)
            ticket_asesor = (venta_asesor / facturas_asesor) if facturas_asesor > 0 else 0
            ticket_unid_asesor = (unidades_asesor / facturas_asesor) if facturas_asesor > 0 else 0
            participacion = (venta_asesor / venta_2026 * 100) if venta_2026 > 0 else 0
            meta_info = metas_asesoras.get(perf.advisor_id, {})
            meta_total_asesor = float(meta_info.get("meta", 0) or 0)
            meta_proporcional_asesor = (
                meta_total_asesor * (dias_transcurridos / dias_mes)
                if meta_total_asesor > 0 else 0
            )
            cumplimiento_asesor = (
                venta_asesor / meta_proporcional_asesor * 100
                if meta_proporcional_asesor > 0 else 0
            )

            asesores.append({
                "nombre": perf.advisor.nombre if perf.advisor else "Sin nombre",
                "venta": venta_asesor,
                "unidades": unidades_asesor,
                "facturas": facturas_asesor,
                "ticket": ticket_asesor,
                "ticket_unid": ticket_unid_asesor,
                "participacion": participacion,
                "meta": meta_total_asesor,
                "tipo_asesora": meta_info.get("tipo_asesora", "FIJA"),
                "cumplimiento": cumplimiento_asesor
            })

        checklist_existente = ChecklistVisita.query.filter_by(
            store_id=store_id,
            fecha_visita=fecha,
            supervisor_email=usuario.correo.lower()
        ).first()

        return jsonify({
            "seccion_a": {
                "venta_2025": venta_2025,
                "venta_2026": venta_2026,
                "diferencia": diferencia,
                "variacion": variacion,
                "cuota_total": cuota_total,
                "dias_mes": dias_mes,
                "dias_transcurridos": dias_transcurridos,
                "cuota_proporcional": cuota_proporcional,
                "cumplimiento_proporcional": cumplimiento_proporcional,
                "falta_cuota_total": falta_cuota_total,
                "dias_restantes": dias_restantes,
                "meta_promedio_dia": meta_promedio_dia
            },
            "seccion_b": {
                "trafico_2025": trafico_2025,
                "trafico_2026": trafico_2026,
                "facturas_2025": facturas_2025,
                "facturas_2026": facturas_2026,
                "conversion": conversion
            },
            "seccion_c": {
                "anio_anterior": fecha.year - 1,
                "anio_actual": fecha.year,
                "unidades_2025": unidades_2025,
                "unidades_2026": unidades_2026,
                "ticket_promedio": ticket_promedio,
                "ticket_unidades": ticket_unidades
            },
            "seccion_d": categorias,
            "seccion_e": asesores,
            "checklist_respuestas": checklist_existente.respuestas if checklist_existente else None,
            "cumplimiento_checklist": checklist_existente.cumplimiento_pct if checklist_existente else 0,
            "items_no": checklist_existente.items_no if checklist_existente else 0
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@checklist_bp.route("/api/guardar", methods=["POST"])
def api_guardar():
    usuario = _obtener_usuario_autorizado()
    data = request.get_json()
    store_id = data.get("store_id")
    fecha_str = data.get("fecha")
    respuestas = data.get("respuestas")
    cumplimiento_pct = data.get("cumplimiento_pct", 0)
    items_no = data.get("items_no", 0)

    if not store_id or not fecha_str:
        return jsonify({"error": "Faltan parámetros"}), 400

    fecha = date.fromisoformat(fecha_str)

    checklist = ChecklistVisita.query.filter_by(
        store_id=store_id,
        fecha_visita=fecha,
        supervisor_email=usuario.correo.lower()
    ).first()

    if not checklist:
        checklist = ChecklistVisita(
            store_id=store_id,
            fecha_visita=fecha,
            supervisor_email=usuario.correo.lower()
        )
        db.session.add(checklist)

    checklist.respuestas = respuestas
    checklist.cumplimiento_pct = cumplimiento_pct or 0
    checklist.items_no = items_no or 0

    db.session.commit()
    return jsonify({"success": True, "message": "Checklist guardado correctamente."})

@checklist_bp.route("/api/datos_historial/<int:id>")
def api_datos_historial(id):
    usuario = _obtener_usuario_autorizado()
    checklist = ChecklistVisita.query.get_or_404(id)
    store_id = checklist.store_id
    fecha = checklist.fecha_visita

    # Reutilizamos la misma lógica que api_datos
    # Se puede refactorizar, pero para no romper, duplicamos mínimo.
    # (Puedes extraer a una función si prefieres)
    compliance = Compliance.query.filter_by(
        store_id=store_id,
        anio=fecha.year,
        mes=fecha.month
    ).filter(Compliance.activo == True).order_by(Compliance.dia_corte.desc()).first()

    if not compliance:
        compliance = Compliance.query.filter_by(
            store_id=store_id,
            anio=fecha.year,
            mes=fecha.month
        ).order_by(Compliance.dia_corte.desc()).first()

    if not compliance:
        return jsonify({"error": "No hay datos de compliance para el período"}), 404

    venta_2025 = float(compliance.venta_anterior or 0)
    venta_2026 = float(compliance.venta_actual or 0)
    diferencia = venta_2026 - venta_2025
    variacion = (diferencia / venta_2025 * 100) if venta_2025 > 0 else 0

    cuota_total = float(getattr(compliance, "cuota_total", 0) or 0)
    dias_mes = 30
    dias_transcurridos = fecha.day if fecha.day <= dias_mes else dias_mes
    cuota_proporcional = cuota_total * (dias_transcurridos / dias_mes) if cuota_total > 0 else 0
    cumplimiento_proporcional = (venta_2026 / cuota_proporcional * 100) if cuota_proporcional > 0 else 0
    falta_cuota_total = max(cuota_total - venta_2026, 0)
    dias_restantes = dias_mes - dias_transcurridos
    meta_promedio_dia = (falta_cuota_total / dias_restantes) if dias_restantes > 0 else 0

    trafico_2025 = int(getattr(compliance, "trafico", 0) or 0)
    trafico_2026 = int(getattr(compliance, "trafico", 0) or 0)
    facturas_2025 = int(getattr(compliance, "facturas", 0) or 0)
    facturas_2026 = int(getattr(compliance, "facturas", 0) or 0)
    conversion = (facturas_2026 / trafico_2026 * 100) if trafico_2026 > 0 else 0

    unidades_2025 = _obtener_unidades_tienda(store_id, fecha.year - 1, fecha.month)
    unidades_2026 = _obtener_unidades_tienda(store_id, fecha.year, fecha.month)
    ticket_promedio = (venta_2026 / facturas_2026) if facturas_2026 > 0 else 0
    ticket_unidades = (unidades_2026 / facturas_2026) if facturas_2026 > 0 else 0

    categorias = []
    lineas = Line.query.filter(Line.id.in_([1, 2, 3, 4])).all()
    for linea in lineas:
        venta_2025_linea = float(db.session.query(
            func.sum(SalesHistoryLine.venta)
        ).filter(
            SalesHistoryLine.store_id == store_id,
            SalesHistoryLine.line_id == linea.id,
            SalesHistoryLine.anio == 2025,
            SalesHistoryLine.mes == fecha.month
        ).scalar() or 0)
        venta_2026_linea = float(db.session.query(
            func.sum(SalesHistoryLine.venta)
        ).filter(
            SalesHistoryLine.store_id == store_id,
            SalesHistoryLine.line_id == linea.id,
            SalesHistoryLine.anio == 2026,
            SalesHistoryLine.mes == fecha.month
        ).scalar() or 0)
        meta_linea = float(db.session.query(
            MetaLine.meta
        ).filter(
            MetaLine.store_id == store_id,
            MetaLine.line_id == linea.id,
            MetaLine.anio == fecha.year,
            MetaLine.mes == fecha.month
        ).scalar() or 0)
        meta_proporcional_linea = meta_linea * (dias_transcurridos / dias_mes) if meta_linea > 0 else 0
        cumplimiento_linea = (venta_2026_linea / meta_proporcional_linea * 100) if meta_proporcional_linea > 0 else 0

        categorias.append({
            "nombre": linea.nombre,
            "venta_2025": venta_2025_linea,
            "venta_2026": venta_2026_linea,
            "diferencia": venta_2026_linea - venta_2025_linea,
            "variacion": ((venta_2026_linea - venta_2025_linea) / venta_2025_linea * 100) if venta_2025_linea > 0 else 0,
            "meta": meta_linea,
            "meta_proporcional": meta_proporcional_linea,
            "cumplimiento": cumplimiento_linea
        })

    asesores = []
    performances = AdvisorPerformance.query.filter_by(
        store_id=store_id,
        anio=fecha.year,
        mes=fecha.month
    ).filter(AdvisorPerformance.activo == True).all()
    metas_asesoras = _metas_asesoras_para_checklist(
        store_id, fecha.year, fecha.month
    )

    for perf in performances:
        venta_asesor = float(perf.venta or 0)
        unidades_asesor = int(perf.unidades or 0)
        facturas_asesor = int(perf.facturas or 0)
        ticket_asesor = (venta_asesor / facturas_asesor) if facturas_asesor > 0 else 0
        ticket_unid_asesor = (unidades_asesor / facturas_asesor) if facturas_asesor > 0 else 0
        participacion = (venta_asesor / venta_2026 * 100) if venta_2026 > 0 else 0
        meta_info = metas_asesoras.get(perf.advisor_id, {})
        meta_total_asesor = float(meta_info.get("meta", 0) or 0)
        meta_proporcional_asesor = (
            meta_total_asesor * (dias_transcurridos / dias_mes)
            if meta_total_asesor > 0 else 0
        )
        cumplimiento_asesor = (
            venta_asesor / meta_proporcional_asesor * 100
            if meta_proporcional_asesor > 0 else 0
        )

        asesores.append({
            "nombre": perf.advisor.nombre if perf.advisor else "Sin nombre",
            "venta": venta_asesor,
            "unidades": unidades_asesor,
            "facturas": facturas_asesor,
            "ticket": ticket_asesor,
            "ticket_unid": ticket_unid_asesor,
            "participacion": participacion,
            "meta": meta_total_asesor,
            "tipo_asesora": meta_info.get("tipo_asesora", "FIJA"),
            "cumplimiento": cumplimiento_asesor
        })

    return jsonify({
        "seccion_a": {
            "venta_2025": venta_2025,
            "venta_2026": venta_2026,
            "diferencia": diferencia,
            "variacion": variacion,
            "cuota_total": cuota_total,
            "dias_mes": dias_mes,
            "dias_transcurridos": dias_transcurridos,
            "cuota_proporcional": cuota_proporcional,
            "cumplimiento_proporcional": cumplimiento_proporcional,
            "falta_cuota_total": falta_cuota_total,
            "dias_restantes": dias_restantes,
            "meta_promedio_dia": meta_promedio_dia
        },
        "seccion_b": {
            "trafico_2025": trafico_2025,
            "trafico_2026": trafico_2026,
            "facturas_2025": facturas_2025,
            "facturas_2026": facturas_2026,
            "conversion": conversion
        },
        "seccion_c": {
            "anio_anterior": fecha.year - 1,
            "anio_actual": fecha.year,
            "unidades_2025": unidades_2025,
            "unidades_2026": unidades_2026,
            "ticket_promedio": ticket_promedio,
            "ticket_unidades": ticket_unidades
        },
        "seccion_d": categorias,
        "seccion_e": asesores,
        "checklist_respuestas": checklist.respuestas or {},
        "cumplimiento_checklist": checklist.cumplimiento_pct or 0,
        "items_no": checklist.items_no or 0
    })


    
@checklist_bp.route("/historial")
def historial():
    usuario = _obtener_usuario_autorizado()

    # Obtener todos los checklists guardados, con información de tienda
    registros = ChecklistVisita.query.join(
        Store, Store.id == ChecklistVisita.store_id
    ).add_columns(
        Store.codigo,
        Store.nombre
    ).order_by(
        ChecklistVisita.fecha_visita.desc(),
        ChecklistVisita.supervisor_email
    ).all()

    historial = []
    for checklist, codigo, nombre_tienda in registros:
        historial.append({
            "id": checklist.id,
            "fecha": checklist.fecha_visita,
            "tienda_codigo": codigo,
            "tienda_nombre": nombre_tienda,
            "supervisor": checklist.supervisor_email,
            "cumplimiento": checklist.cumplimiento_pct,
            "items_no": checklist.items_no
        })

    return render_template(
        "checklist_historial.html",
        historial=historial,
        usuario=usuario
    )


@checklist_bp.route("/historial/<int:id>")
def detalle_historial(id):
    usuario = _obtener_usuario_autorizado()

    checklist = ChecklistVisita.query.get_or_404(id)
    tienda = Store.query.get(checklist.store_id)

    return render_template(
        "checklist_detalle.html",
        checklist=checklist,
        tienda=tienda,
        usuario=usuario
    )
