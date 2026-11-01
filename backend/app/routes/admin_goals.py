from functools import wraps

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func

from app.extensions import db
from app.models import Advisor, AdvisorGoal, AdvisorPerformance
from app.models.daily_sales import DailySales
from app.models.compliance import Compliance
from app.models.store import Store
from app.models.user import User
from app.services.advisor_goal_service import (
    calcular_metas_asesoras,
    guardar_distribucion_periodo,
    obtener_meta_tienda,
)


admin_goals_bp = Blueprint("admin_goals", __name__, url_prefix="/admin")
ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}
ROLES_TIENDA = {"TIENDA", "STORE"}


def _usuario_admin():
    usuario = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    rol = (
        usuario.role.nombre.upper().strip()
        if usuario and usuario.role else ""
    )
    if not usuario:
        abort(401)
    if rol not in ROLES_ADMIN:
        abort(403)
    return usuario


def _usuario_metas():
    """Permite administrar metas a administradores y a la tienda propia."""
    usuario = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    rol = usuario.role.nombre.upper().strip() if usuario and usuario.role else ""
    if not usuario:
        abort(401)
    if rol not in ROLES_ADMIN | ROLES_TIENDA:
        abort(403)
    if rol in ROLES_TIENDA and not usuario.store_id:
        abort(403)
    return usuario, rol


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        _usuario_admin()
        return view(*args, **kwargs)
    return wrapped


def metas_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        usuario, rol = _usuario_metas()
        return view(*args, **kwargs)
    return wrapped


def _periodo():
    periodo = (
        Compliance.query.with_entities(Compliance.anio, Compliance.mes)
        .order_by(Compliance.anio.desc(), Compliance.mes.desc())
        .first()
    )
    return (
        request.args.get("anio", type=int, default=periodo.anio if periodo else 2026),
        request.args.get("mes", type=int, default=periodo.mes if periodo else 1),
    )


def _vendedores_unicos(store_id, anio, mes):
    if not store_id:
        return []
    return (
        db.session.query(
            Advisor.id.label("advisor_id"),
            Advisor.nombre.label("nombre"),
            func.sum(AdvisorPerformance.venta).label("venta"),
            func.sum(AdvisorPerformance.facturas).label("facturas"),
            func.sum(AdvisorPerformance.unidades).label("unidades"),
        )
        .join(AdvisorPerformance, Advisor.id == AdvisorPerformance.advisor_id)
        .filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.activo.is_(True),
            Advisor.nombre.ilike("%VENDEDOR UNICO%"),
        )
        .group_by(Advisor.id, Advisor.nombre)
        .order_by(func.sum(AdvisorPerformance.venta).desc())
        .all()
    )


def _consulta_ventas_diarias(store_id, anio, mes, meta_tienda):
    if not store_id:
        return {"filas": [], "venta_anterior": 0, "venta_actual": 0,
                "diferencia": 0, "incremento": 0}
    registros = (
        DailySales.query
        .filter_by(store_id=store_id, anio=anio, mes=mes, activo=True)
        .order_by(DailySales.dia.asc())
        .all()
    )
    meta_diaria = float(meta_tienda or 0) / 30 if meta_tienda else 0
    filas = []
    anterior = actual = 0.0
    for registro in registros:
        venta_anterior = float(registro.venta_2025 or 0)
        venta_actual = float(registro.venta_2026 or 0)
        diferencia = venta_actual - venta_anterior
        incremento = (
            diferencia / venta_anterior * 100 if venta_anterior > 0 else 0
        )
        anterior += venta_anterior
        actual += venta_actual
        filas.append({
            "dia": registro.dia,
            "venta_anterior": venta_anterior,
            "venta_actual": venta_actual,
            "diferencia": diferencia,
            "incremento": incremento,
            "meta_diaria": meta_diaria,
            "cumplimiento": (
                venta_actual / meta_diaria * 100 if meta_diaria > 0 else 0
            ),
        })
    diferencia = actual - anterior
    return {
        "filas": filas,
        "venta_anterior": anterior,
        "venta_actual": actual,
        "diferencia": diferencia,
        "incremento": diferencia / anterior * 100 if anterior > 0 else 0,
    }


@admin_goals_bp.route("/metas", methods=["GET"])
@metas_required
def admin_metas():
    usuario, rol = _usuario_metas()
    if rol in ROLES_TIENDA:
        tiendas = Store.query.filter_by(id=usuario.store_id, estado="ACTIVA").order_by(Store.codigo).all()
    else:
        tiendas = Store.query.filter_by(estado="ACTIVA").order_by(Store.codigo).all()
    store_id = request.args.get("store_id", type=int)
    if rol in ROLES_TIENDA:
        store_id = usuario.store_id
    anio, mes = _periodo()
    filtro_nombre = request.args.get("q", "").strip()

    distribucion = None
    ultima_meta = None
    ultimo_usuario = None
    ventas_diarias = None
    if store_id:
        distribucion = calcular_metas_asesoras(
            store_id, anio, mes, obtener_meta_tienda(store_id, anio, mes)
        )
        ultima_meta = (
            AdvisorGoal.query
            .filter_by(store_id=store_id, anio=anio, mes=mes)
            .order_by(AdvisorGoal.updated_at.desc())
            .first()
        )
        if ultima_meta and ultima_meta.updated_by_user_id:
            ultimo_usuario = db.session.get(User, ultima_meta.updated_by_user_id)
        ventas_diarias = _consulta_ventas_diarias(
            store_id, anio, mes, distribucion["meta_tienda"]
        )

    return render_template(
        "admin_goals.html",
        usuario=usuario,
        tiendas=tiendas,
        store_id_actual=store_id,
        anio_actual=anio,
        mes_actual=mes,
        filtro_nombre=filtro_nombre,
        distribucion=distribucion,
        vendedores=_vendedores_unicos(store_id, anio, mes),
        ultima_meta=ultima_meta,
        ultimo_usuario=ultimo_usuario,
        ventas_diarias=ventas_diarias,
    )


@admin_goals_bp.route("/metas/guardar-distribucion", methods=["POST"])
@metas_required
def guardar_distribucion_unificada():
    usuario, rol = _usuario_metas()
    data = request.get_json(silent=True) or {}
    try:
        store_id = int(data.get("store_id"))
        anio = int(data.get("anio"))
        mes = int(data.get("mes"))
    except (TypeError, ValueError):
        return jsonify(success=False, error="Tienda o período inválido."), 400
    if rol in ROLES_TIENDA and store_id != usuario.store_id:
        return jsonify(success=False, error="Solo puedes editar las metas de tu propia tienda."), 403

    asignaciones = data.get("asignaciones")
    if not isinstance(asignaciones, list) or not asignaciones:
        return jsonify(success=False, error="No hay asesoras para guardar."), 400

    guardadas, error = guardar_distribucion_periodo(
        store_id, anio, mes, asignaciones, usuario.id
    )
    if error:
        return jsonify(success=False, error=error), 400

    distribucion = calcular_metas_asesoras(
        store_id, anio, mes, obtener_meta_tienda(store_id, anio, mes)
    )
    return jsonify(
        success=True,
        guardadas=guardadas,
        ultima_actualizacion=(
            distribucion["ultima_actualizacion"].isoformat()
            if distribucion["ultima_actualizacion"] else None
        ),
    )


# Compatibilidad con el JavaScript y enlaces anteriores.
@admin_goals_bp.route("/metas/guardar", methods=["POST"])
@metas_required
def guardar_metas():
    usuario, rol = _usuario_metas()
    data = request.get_json(silent=True) or {}
    metas = data.get("metas") or []
    try:
        store_id = int(data.get("store_id"))
        anio = int(data.get("anio"))
        mes = int(data.get("mes"))
    except (TypeError, ValueError):
        return jsonify(success=False, error="Tienda o período inválido."), 400
    if rol in ROLES_TIENDA and store_id != usuario.store_id:
        return jsonify(success=False, error="Solo puedes editar las metas de tu propia tienda."), 403

    cambios = {int(item["advisor_id"]): item for item in metas}
    actual = calcular_metas_asesoras(
        store_id, anio, mes, obtener_meta_tienda(store_id, anio, mes)
    )
    asignaciones = []
    for asesora in actual["asesoras"]:
        cambio = cambios.get(asesora["advisor_id"], {})
        asignaciones.append({
            "advisor_id": asesora["advisor_id"],
            "meta_venta": cambio.get("meta_venta", asesora["meta"]),
            "tipo_asesora": asesora["tipo_asesora"],
        })
    guardadas, error = guardar_distribucion_periodo(
        store_id, anio, mes, asignaciones, usuario.id
    )
    if error:
        return jsonify(success=False, error=error), 400
    return jsonify(success=True, resultados=asignaciones, guardadas=guardadas)


@admin_goals_bp.route("/distribucion-metas", methods=["GET"])
@admin_required
def distribucion_metas():
    params = request.args.to_dict()
    return redirect(url_for("admin_goals.admin_metas", **params) + "#distribucion")


@admin_goals_bp.route("/distribucion-metas", methods=["POST"])
@admin_required
def guardar_distribucion_metas():
    flash("Usa la tabla unificada para revisar y guardar la distribución.", "info")
    return redirect(url_for("admin_goals.admin_metas") + "#distribucion")
