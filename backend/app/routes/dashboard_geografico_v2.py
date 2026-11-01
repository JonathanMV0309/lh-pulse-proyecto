"""Rutas existentes del Dashboard Geográfico V2."""
from functools import wraps
from flask import Blueprint, render_template, session, request, jsonify, abort, current_app
from app.models.user import User
from app.services.dashboard_geografico_v2_data_service import obtener_dashboard_geografico
from app.services.dashboard_geografico_v2_periodos import resolver_periodo
from app.services.dashboard_geografico_v2_service import (
    obtener_tiendas_para_mapa, obtener_contexto_tienda, obtener_oportunidades,
    obtener_alertas, obtener_analisis_clima_ventas, obtener_analisis_trafico_ventas,
    obtener_comparacion,
)

dashboard_geografico_v2_bp = Blueprint("dashboard_geografico_v2", __name__)
ROLES_PERMITIDOS = {"ADMINISTRADOR", "TIENDA"}


def _validar_usuario():
    if "user_id" not in session:
        abort(401)
    usuario = User.query.get(session["user_id"])
    if not usuario:
        abort(404)
    rol = usuario.role.nombre.upper().strip() if usuario.role else ""
    if rol not in ROLES_PERMITIDOS:
        abort(403)
    return usuario


def _filtros():
    ciudad = request.args.get("ciudad", "").strip()
    clima = request.args.get("clima", "").strip()
    tienda = request.args.get("tienda", "").strip()
    if len(ciudad) > 80 or len(clima) > 30:
        raise ValueError("Filtro inválido")
    try:
        tienda_id = int(tienda) if tienda else None
        if tienda_id is not None and tienda_id <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError("Tienda inválida") from None
    seleccion = resolver_periodo(
        anio=request.args.get("anio") or None, mes=request.args.get("mes") or None,
        dia_corte=request.args.get("dia_corte") or None, periodo=request.args.get("periodo") or None)
    return {"ciudad": None if ciudad.upper() in ("", "TODAS") else ciudad,
            "clima": None if clima.upper() in ("", "TODOS") else clima,
            "tienda_id": tienda_id, "periodo": seleccion["periodo"]}


def _api(func):
    @wraps(func)
    def view(*args, **kwargs):
        _validar_usuario()
        try:
            result = func(*args, **kwargs)
            response = current_app.make_response(result)
            response.headers["Cache-Control"] = "private, no-store"
            return response
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception:
            # No volcar excepciones: podrían contener URLs con claves externas.
            current_app.logger.error("Geo V2: error interno en %s", func.__name__)
            return jsonify({"error": "No se pudo completar la consulta"}), 500
    return view


@dashboard_geografico_v2_bp.route("/dashboard/geografico-v2")
def dashboard_geografico_v2():
    usuario = _validar_usuario()
    try:
        datos = obtener_dashboard_geografico(**_filtros())
    except ValueError as error:
        return render_template("admin/dashboard_geografico_v2_error.html", mensaje=str(error), usuario=usuario), 400
    datos["usuario"] = usuario
    return render_template("admin/dashboard_geografico_v2.html", **datos)


@dashboard_geografico_v2_bp.route("/api/v2/tiendas")
@_api
def api_tiendas():
    return jsonify(obtener_tiendas_para_mapa(**_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/contexto/<int:store_id>")
@_api
def api_contexto(store_id):
    contexto = obtener_contexto_tienda(store_id, **_filtros(),
        incluir_externo=request.args.get("externo", "1") != "0",
        solo_externo=request.args.get("solo_externo") == "1")
    if contexto is None:
        return jsonify({"error": "Tienda no encontrada en la selección"}), 404
    return jsonify(contexto)


@dashboard_geografico_v2_bp.route("/api/v2/oportunidades")
@_api
def api_oportunidades():
    return jsonify(obtener_oportunidades(**_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/alertas")
@_api
def api_alertas():
    return jsonify(obtener_alertas(**_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/analisis/clima-ventas")
@_api
def api_clima_ventas():
    return jsonify(obtener_analisis_clima_ventas(**_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/analisis/trafico-ventas")
@_api
def api_trafico_ventas():
    return jsonify(obtener_analisis_trafico_ventas(**_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/comparacion")
@_api
def api_comparacion():
    ids = request.args.get("ids", "")
    if not ids or len(ids) > 120:
        raise ValueError("Indica las tiendas que deseas comparar")
    return jsonify(obtener_comparacion(ids, **_filtros()))


@dashboard_geografico_v2_bp.route("/api/v2/mapa-plus")
def api_mapa_plus():
    """Datos extra del mapa (meta, proyección, asesoras, visitas). Solo administradores."""
    usuario = _validar_usuario()
    rol = usuario.role.nombre.upper().strip() if usuario.role else ""
    if rol not in {"ADMIN", "ADMINISTRADOR"}:
        abort(403)
    periodo = request.args.get("periodo") or ""
    partes = periodo.split("-")
    anio = mes = dia = None
    if len(partes) == 3 and all(p.isdigit() for p in partes):
        anio, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
    try:
        from app.services.mapa_plus_service import mapa_plus
        respuesta = jsonify(mapa_plus(anio, mes, dia))
    except Exception:
        from app.extensions import db
        db.session.rollback()
        current_app.logger.error("Geo V2: no se pudo armar mapa-plus")
        respuesta = jsonify({"ok": False, "motivo": "error"})
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta
