"""Histórico de cumplimientos e incrementos por tienda (hoja «ACUM» del Excel de ventas).

- Administración: todas las tiendas y el total de la red.
- Tienda: su propia fila y el total de la red.
Solo lectura: los datos salen del último Excel cargado (ver historico_service).
"""
from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from app.extensions import db
from app.models.user import User

historico_bp = Blueprint("historico", __name__, url_prefix="/historico")


@historico_bp.get("/")
def pagina():
    from app.services import historico_service
    if "user_id" not in session:
        abort(401)
    usuario = db.session.get(User, session["user_id"])
    if not usuario:
        abort(403)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    es_tienda = rol == "TIENDA"
    try:
        datos = historico_service.datos()
    except Exception:
        current_app.logger.exception("Histórico: no se pudo leer la hoja ACUM")
        datos = None
    if datos and es_tienda:
        datos = dict(datos, tiendas=[t for t in datos["tiendas"] if t.get("store_id") == usuario.store_id])
    return render_template("historico/index.html", datos=datos, es_tienda=es_tienda,
                           mi_store_id=usuario.store_id if es_tienda else None)


@historico_bp.get("/api/tienda")
def api_tienda():
    """Para el recuadro «Histórico» del dashboard de tienda: la fila de una tienda y el total de la red.

    La tienda solo ve la suya; la administración, la de la tienda que está mirando (?store_id=)."""
    from app.services import historico_service
    if "user_id" not in session:
        abort(401)
    usuario = db.session.get(User, session["user_id"])
    if not usuario:
        abort(403)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    store_id = usuario.store_id if rol == "TIENDA" else request.args.get("store_id", type=int)
    try:
        datos = historico_service.datos()
    except Exception:
        current_app.logger.exception("Histórico: no se pudo leer la hoja ACUM")
        datos = None
    if not datos or not store_id:
        return jsonify({"ok": False})
    fila = next((t for t in datos["tiendas"] if t.get("store_id") == store_id), None)
    return jsonify({"ok": bool(fila), "fila": fila, "total": datos["total"], "anios": datos["anios"], "archivo": datos["archivo"]})
