"""Retos de la red (batallas de la semana, récords, hora dorada…). Solo lectura."""
from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from app.extensions import db
from app.models.user import User

retos_bp = Blueprint("retos", __name__)
ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}


def _usuario():
    usuario = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not usuario or usuario.activo is False:
        abort(401)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    if rol not in ROLES_ADMIN and rol != "TIENDA":
        abort(403)
    return usuario, rol


def _corte():
    anio, mes, dia = request.args.get("anio", type=int), request.args.get("mes", type=int), request.args.get("dia_corte", type=int)
    partes = (request.args.get("periodo") or "").split("-")
    if len(partes) == 3 and all(p.isdigit() for p in partes):
        anio, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
    return anio, mes, dia


def _responder(calcular):
    try:
        respuesta = jsonify(calcular())
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Retos: no se pudieron calcular")
        respuesta = jsonify({"ok": False, "motivo": "error"})
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta


@retos_bp.get("/api/retos/red")
def api_red():
    _usuario()
    from app.services import retos_service
    return _responder(lambda: retos_service.red(*_corte()))


@retos_bp.get("/api/retos/tienda")
def api_tienda():
    usuario, rol = _usuario()
    store_id = usuario.store_id if rol == "TIENDA" else request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"ok": False, "motivo": "sin_tienda"})
    from app.services import retos_service
    return _responder(lambda: retos_service.tienda(store_id, *_corte()))


@retos_bp.get("/retos")
def pagina():
    """Retos de la semana de la tienda (la administración puede ver una tienda con ?store_id=)."""
    usuario, rol = _usuario()
    store_id = usuario.store_id if rol == "TIENDA" else request.args.get("store_id", type=int)
    return render_template("retos/semana.html", store_id=store_id, es_tienda_usuario=rol == "TIENDA")
