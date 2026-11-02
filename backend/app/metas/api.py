"""API REST de metas (/api/v1). Solo traduce HTTP <-> ServicioMetas: aquí no hay consultas a la base
de datos ni reglas de negocio. Respuestas siempre en JSON: {"ok": true, ...} o {"ok": false, "error", "campo"}.

    GET    /api/v1/tiendas                       tiendas activas
    GET    /api/v1/metas?anio=2026&mes=11        resumen del mes (HU-05)
    GET    /api/v1/metas/<id>                    una meta
    POST   /api/v1/metas                         crear (HU-06)    {tienda_id, anio, mes, valor, nota}
    PUT    /api/v1/metas/<id>                    ajustar (HU-06)  {valor, nota}
    DELETE /api/v1/metas/<id>                    eliminar
    GET    /api/v1/metas/<id>/historial          cambios de la meta (HU-07)
"""
from datetime import date
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError

from app.metas.dto import MetaEntradaDTO
from app.metas.servicio import ServicioMetas
from app.metas.validaciones import ErrorValidacion

api_metas_bp = Blueprint("api_metas", __name__, url_prefix="/api/v1")

ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}


def _error(mensaje, estado, campo=None):
    return jsonify({"ok": False, "error": mensaje, "campo": campo}), estado


def solo_administracion(vista):
    """Como admin_required, pero responde JSON (401/403) en lugar de redirigir."""
    @wraps(vista)
    def envuelta(*args, **kwargs):
        if "user_id" not in session:
            return _error("Inicia sesión para usar la API.", 401)
        if str(session.get("rol", "")).strip().upper() not in ROLES_ADMIN:
            return _error("Solo la administración puede gestionar las metas.", 403)
        return vista(*args, **kwargs)
    return envuelta


def servicio():
    # Una fachada por petición; la fábrica de DAO (y su caché de tiendas) se comparte en la app
    if "metas_fabrica" not in current_app.extensions:
        from app.metas.fabrica import fabrica_configurada
        current_app.extensions["metas_fabrica"] = fabrica_configurada()
    return ServicioMetas(current_app.extensions["metas_fabrica"])


def _usuario():
    return session.get("nombre") or f"usuario {session.get('user_id')}"


def _entero(nombre, defecto):
    valor = request.args.get(nombre, defecto)
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion(f"El parámetro {nombre} debe ser un número.", nombre)


def _json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorValidacion("El cuerpo debe ser un objeto JSON.", None)
    return datos


@api_metas_bp.errorhandler(ErrorValidacion)
def _validacion(e):
    return _error(e.mensaje, e.estado_http, e.campo)


@api_metas_bp.errorhandler(SQLAlchemyError)
def _base_de_datos(e):
    from app.extensions import db
    db.session.rollback()
    current_app.logger.exception("Error de base de datos en la API de metas")
    return _error("No se pudo completar la operación en la base de datos. Intenta de nuevo.", 503)


@api_metas_bp.get("/tiendas")
@solo_administracion
def tiendas():
    return jsonify({"ok": True, "tiendas": [t.a_dict() for t in servicio().listar_tiendas()]})


@api_metas_bp.get("/metas")
@solo_administracion
def resumen():
    hoy = date.today()
    anio, mes = _entero("anio", hoy.year), _entero("mes", hoy.month)
    s = servicio()
    filas = s.resumen_del_mes(anio, mes)
    return jsonify({"ok": True, "anio": anio, "mes": mes, "semaforo": s.estrategia.descripcion,
                    "tiendas": [f.a_dict() for f in filas]})


@api_metas_bp.get("/metas/<int:meta_id>")
@solo_administracion
def obtener(meta_id):
    return jsonify({"ok": True, "meta": servicio().obtener(meta_id).a_dict()})


@api_metas_bp.post("/metas")
@solo_administracion
def crear():
    meta = servicio().crear(MetaEntradaDTO.desde_json(_json()), _usuario())
    return jsonify({"ok": True, "mensaje": f"Meta de {meta.tienda_codigo} para {meta.mes:02d}/{meta.anio} creada.",
                    "meta": meta.a_dict()}), 201


@api_metas_bp.put("/metas/<int:meta_id>")
@solo_administracion
def ajustar(meta_id):
    meta = servicio().ajustar(meta_id, MetaEntradaDTO.desde_json(_json()), _usuario())
    return jsonify({"ok": True, "mensaje": f"Meta de {meta.tienda_codigo} ajustada.", "meta": meta.a_dict()})


@api_metas_bp.delete("/metas/<int:meta_id>")
@solo_administracion
def eliminar(meta_id):
    meta = servicio().eliminar(meta_id, _usuario())
    return jsonify({"ok": True, "mensaje": f"Meta de {meta.tienda_codigo} para {meta.mes:02d}/{meta.anio} eliminada."})


@api_metas_bp.get("/metas/<int:meta_id>/historial")
@solo_administracion
def historial(meta_id):
    return jsonify({"ok": True, "historial": [h.a_dict() for h in servicio().historial_de(meta_id)]})
