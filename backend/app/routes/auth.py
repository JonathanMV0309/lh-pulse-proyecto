from app.utils.logs import log_debug
from flask import Blueprint, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.routes.accesos import registrar_acceso
from app.utils.permissions import es_administrador


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth"
)


@auth_bp.route("/register", methods=["POST"])
def register():

    # Solo un administrador con sesión iniciada puede crear usuarios por esta vía
    # (antes cualquiera podía crear un Administrador sin iniciar sesión).
    actual = User.query.get(session.get("user_id")) if session.get("user_id") else None
    if not (actual and actual.role and es_administrador(actual.role.nombre)):
        return jsonify({
            "error": "No autorizado"
        }), 403

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No se recibió JSON",
            "content_type": request.content_type,
            "raw_data": request.data.decode("utf-8", errors="replace")
        }), 400

    nombre = data.get("nombre")
    correo = data.get("correo")
    password = data.get("password")
    rol = data.get("rol", "Administrador")

    if not nombre or not correo or not password:
        return jsonify({
            "error": "Faltan datos"
        }), 400

    if User.query.filter_by(correo=correo).first():
        return jsonify({
            "error": "El correo ya existe"
        }), 400

    role = Role.query.filter_by(nombre=rol).first()

    if role is None:
        return jsonify({
            "error": "El rol no existe"
        }), 404

    nuevo = User(
        nombre=nombre,
        correo=correo,
        password=generate_password_hash(password),
        role_id=role.id
    )

    db.session.add(nuevo)
    db.session.commit()

    return jsonify({
        "mensaje": "Usuario creado correctamente"
    }), 201


# ==========================================
# LOGIN
# ==========================================
def _iniciar_sesion(user):
    """Reemplaza la sesión actual por la del usuario autenticado."""
    session.clear()
    session["user_id"] = user.id
    session["nombre"] = user.nombre
    session["rol"] = user.role.nombre
    session.permanent = True


def _usuario_publico(user):
    """Datos del usuario que el login devuelve al navegador (nunca la contraseña)."""
    return {
        "id": user.id,
        "nombre": user.nombre,
        "correo": user.correo,
        "rol": user.role.nombre,
    }


@auth_bp.route("/login", methods=["POST"])
def login():
    # silent=True: un cuerpo vacío, mal formado o sin Content-Type JSON devuelve None
    # en lugar de lanzar una excepción; una lista o un texto tampoco sirven.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Correo y contraseña son obligatorios"}), 400

    correo = data.get("correo")
    password = data.get("password")

    if not correo or not password:
        return jsonify({"error": "Correo y contraseña son obligatorios"}), 400

    user = User.query.filter_by(correo=correo).first()

    if user is None:
        registrar_acceso("usuario_no_existe", correo=correo)
        return jsonify({"error": "Usuario no encontrado"}), 404

    if not check_password_hash(user.password, password):
        registrar_acceso("clave_incorrecta", usuario=user, correo=correo)
        return jsonify({"error": "Contraseña incorrecta"}), 401

    _iniciar_sesion(user)
    registrar_acceso("ok", usuario=user, correo=correo)
    log_debug("SESION:", dict(session))

    return jsonify({"mensaje": "Login exitoso", "usuario": _usuario_publico(user)}), 200


@auth_bp.route("/logout", methods=["GET"])
def logout():

    if session.get("user_id"):
        registrar_acceso("salida", usuario=User.query.get(session["user_id"]))

    session.clear()

    return redirect("/")