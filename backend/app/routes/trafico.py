from flask import Blueprint, abort, jsonify, render_template, request, session
from app.extensions import db
from app.models.user import User
from app.services.trafico_service import ROLES, tiendas_permitidas, filtros, obtener_panel

trafico_bp = Blueprint('trafico', __name__, url_prefix='/trafico')


def contexto():
    usuario = db.session.get(User, session['user_id']) if session.get('user_id') else None
    if not usuario:
        abort(401)
    rol = usuario.role.nombre.strip().upper() if usuario.role else ''
    if not usuario.activo or rol not in ROLES:
        abort(403)
    tiendas = tiendas_permitidas(usuario).order_by('codigo').all()
    return usuario, tiendas


@trafico_bp.get('/')
def index():
    usuario, tiendas = contexto()
    try:
        f = filtros(request.args, [t.id for t in tiendas])
    except ValueError as exc:
        abort(400, description=str(exc))
    except PermissionError:
        abort(403)
    return render_template('trafico.html', usuario=usuario, tiendas_trafico=tiendas, filtros_trafico=f)


@trafico_bp.get('/api/datos')
def datos():
    _, tiendas = contexto()
    ids = [t.id for t in tiendas]
    try:
        f = filtros(request.args, ids)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except PermissionError:
        abort(403)
    response = jsonify(obtener_panel(ids, f))
    response.headers['Cache-Control'] = 'private, no-store'
    return response
