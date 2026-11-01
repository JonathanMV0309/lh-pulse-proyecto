from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash
)
from datetime import datetime

from app.extensions import db
from app.models.user import User
from app.models.store import Store
from app.models.notification import Notification
from app.models.notification_read import NotificationRead


notifications_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/notificaciones"
)


def _es_admin(usuario):
    if not usuario or not usuario.role:
        return False
    return usuario.role.nombre.upper() in [
        "ADMIN",
        "ADMINISTRADOR"
    ]


def _es_tienda(usuario):
    if not usuario or not usuario.role:
        return False
    return usuario.role.nombre.upper() == "TIENDA"


def _obtener_usuario():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _obtener_notificaciones_de_tienda(store_id):
    return (
        Notification.query
        .filter(
            (Notification.store_id.is_(None)) |
            (Notification.store_id == store_id)
        )
        .order_by(Notification.fecha_creacion.desc())
        .all()
    )


def _contar_no_leidas(store_id):
    notificaciones = _obtener_notificaciones_de_tienda(store_id)
    ids = [n.id for n in notificaciones]
    if not ids:
        return 0
    leidas = (
        db.session.query(NotificationRead.notification_id)
        .filter(
            NotificationRead.store_id == store_id,
            NotificationRead.notification_id.in_(ids)
        )
        .all()
    )
    ids_leidos = {row[0] for row in leidas}
    return sum(1 for n in notificaciones if n.id not in ids_leidos)


# ==========================================================
# RUTAS ADMINISTRADOR
# ==========================================================

@notifications_bp.route("/admin", methods=["GET"])
def admin_notifications():
    usuario = _obtener_usuario()
    if not _es_admin(usuario):
        return redirect("/")

    tiendas = Store.query.filter_by(estado="ACTIVA").order_by(Store.codigo).all()
    notificaciones = Notification.query.order_by(Notification.fecha_creacion.desc()).all()

    return render_template(
        "notifications/admin_notifications.html",
        tiendas=tiendas,
        notificaciones=notificaciones
    )


@notifications_bp.route("/admin/enviar", methods=["POST"])
def admin_enviar_notificacion():
    usuario = _obtener_usuario()
    if not _es_admin(usuario):
        return jsonify({"success": False, "error": "No autorizado"}), 403

    titulo = request.form.get("titulo", "").strip()
    mensaje = request.form.get("mensaje", "").strip()
    store_id = request.form.get("store_id", type=int)

    if not titulo or not mensaje:
        flash("Título y mensaje son obligatorios", "danger")
        return redirect(url_for("notifications.admin_notifications"))

    if store_id == 0:
        store_id = None
    else:
        tienda = Store.query.get(store_id)
        if not tienda:
            flash("Tienda inválida", "danger")
            return redirect(url_for("notifications.admin_notifications"))

    nueva = Notification(
        titulo=titulo,
        mensaje=mensaje,
        store_id=store_id,
        creador_id=usuario.id
    )
    db.session.add(nueva)
    db.session.commit()

    flash("Notificación enviada correctamente", "success")
    return redirect(url_for("notifications.admin_notifications"))


# ==========================================================
# RUTAS TIENDA
# ==========================================================

@notifications_bp.route("/", methods=["GET"])
def store_notifications():
    usuario = _obtener_usuario()
    if not _es_tienda(usuario) or not usuario.store_id:
        return redirect("/")

    store_id = usuario.store_id
    notificaciones = _obtener_notificaciones_de_tienda(store_id)

    leidas_db = (
        db.session.query(NotificationRead.notification_id)
        .filter(NotificationRead.store_id == store_id)
        .all()
    )
    ids_leidos = {row[0] for row in leidas_db}

    notificaciones_con_estado = []
    for n in notificaciones:
        leida = n.id in ids_leidos
        notificaciones_con_estado.append({
            "id": n.id,
            "titulo": n.titulo,
            "mensaje": n.mensaje,
            "fecha": n.fecha_creacion,
            "leida": leida,
            "global": n.store_id is None
        })

    return render_template(
        "notifications/store_notifications.html",
        notificaciones=notificaciones_con_estado,
        unread_count=sum(1 for n in notificaciones_con_estado if not n["leida"])
    )


@notifications_bp.route("/api/contador", methods=["GET"])
def api_contador():
    usuario = _obtener_usuario()
    if not _es_tienda(usuario) or not usuario.store_id:
        return jsonify({"count": 0}), 200

    count = _contar_no_leidas(usuario.store_id)
    return jsonify({"count": count})


@notifications_bp.route("/api/lista", methods=["GET"])
def api_lista():
    usuario = _obtener_usuario()
    if not _es_tienda(usuario) or not usuario.store_id:
        return jsonify([]), 200

    store_id = usuario.store_id
    notificaciones = _obtener_notificaciones_de_tienda(store_id)

    leidas_db = (
        db.session.query(NotificationRead.notification_id)
        .filter(NotificationRead.store_id == store_id)
        .all()
    )
    ids_leidos = {row[0] for row in leidas_db}

    lista = []
    for n in notificaciones:
        lista.append({
            "id": n.id,
            "titulo": n.titulo,
            "mensaje": n.mensaje,
            "fecha": n.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
            "leida": n.id in ids_leidos
        })

    return jsonify(lista)


@notifications_bp.route("/api/leer/<int:notificacion_id>", methods=["POST"])
def api_marcar_leida(notificacion_id):
    usuario = _obtener_usuario()
    if not _es_tienda(usuario) or not usuario.store_id:
        return jsonify({"success": False, "error": "No autorizado"}), 403

    store_id = usuario.store_id

    notificacion = Notification.query.get(notificacion_id)
    if not notificacion:
        return jsonify({"success": False, "error": "Notificación no encontrada"}), 404

    if not (
        notificacion.store_id is None or
        notificacion.store_id == store_id
    ):
        return jsonify({"success": False, "error": "No autorizado"}), 403

    existe = NotificationRead.query.filter_by(
        notification_id=notificacion_id,
        store_id=store_id
    ).first()

    if not existe:
        nueva_lectura = NotificationRead(
            notification_id=notificacion_id,
            store_id=store_id
        )
        db.session.add(nueva_lectura)
        db.session.commit()

    count = _contar_no_leidas(store_id)
    return jsonify({"success": True, "count": count})