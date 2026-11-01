from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, session, abort, redirect, url_for, jsonify, flash
from sqlalchemy import func

from app.extensions import db
from app.models.mensaje_hilo import MensajeHilo, MensajeHiloVisto
from app.models.store import Store
from app.models.user import User


# ==========================================================
# BLUEPRINT · Mensajes que Hilo dice al entrar
# ==========================================================

mensajes_hilo_bp = Blueprint(
    "mensajes_hilo",
    __name__
)

ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}
TONOS = {
    "celebra": "Celebrando (salta de alegría)",
    "anima": "Animando (brazos arriba)",
    "aviso": "Aviso importante (señala el mensaje)",
}
DESTINOS = {
    "todas": "Todas las tiendas",
    "seleccion": "Tiendas seleccionadas",
    "todos": "Todos (tiendas, administradores y supervisores)",
}
LARGO_MAXIMO = 400


def crear_tablas_si_faltan(app):
    """Crea las tablas de mensajes la primera vez (no toca las demás)."""
    with app.app_context():
        for tabla in (MensajeHilo.__table__, MensajeHiloVisto.__table__):
            try:
                tabla.create(bind=db.engine, checkfirst=True)
            except Exception as error:
                app.logger.warning("No se pudo crear %s: %s", tabla.name, error)


def _usuario():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def _rol(usuario):
    return str(usuario.role.nombre).upper().strip() if usuario and usuario.role and usuario.role.nombre else ""


def _solo_admin():
    usuario = _usuario()
    if not usuario:
        abort(401)
    if _rol(usuario) not in ROLES_ADMIN:
        abort(403)
    return usuario


def _le_toca(mensaje, usuario):
    """¿Este mensaje es para este usuario?"""
    if mensaje.destino == "todos":
        return True
    if not usuario.store_id or _rol(usuario) != "TIENDA":
        return False
    if mensaje.destino == "todas":
        return True
    return usuario.store_id in mensaje.ids_tiendas()


def _destinatarios(mensaje):
    """Usuarios activos a los que les llega (para el conteo de vistos)."""
    consulta = User.query.filter(db.or_(User.activo.is_(True), User.activo.is_(None)))
    usuarios = consulta.all()
    return [u for u in usuarios if _le_toca(mensaje, u)]


# ==========================================================
# PÁGINA DEL ADMINISTRADOR
# ==========================================================

@mensajes_hilo_bp.route("/admin/mensajes-hilo", methods=["GET", "POST"])
def mensajes():

    admin = _solo_admin()

    if request.method == "POST":
        texto = " ".join((request.form.get("texto") or "").split())[:LARGO_MAXIMO]
        tono = request.form.get("tono") if request.form.get("tono") in TONOS else "anima"
        destino = request.form.get("destino") if request.form.get("destino") in DESTINOS else "todas"
        tiendas = ",".join(sorted({t for t in request.form.getlist("tiendas") if t.isdigit()}, key=int))
        try:
            desde = datetime.strptime(request.form.get("desde") or "", "%Y-%m-%d").date()
            hasta = datetime.strptime(request.form.get("hasta") or "", "%Y-%m-%d").date()
        except ValueError:
            desde, hasta = date.today(), date.today() + timedelta(days=6)

        if not texto:
            flash("Escribe el mensaje que va a decir Hilo.", "warning")
        elif destino == "seleccion" and not tiendas:
            flash("Selecciona al menos una tienda.", "warning")
        elif hasta < desde:
            flash("La fecha final no puede ser antes de la inicial.", "warning")
        else:
            db.session.add(MensajeHilo(
                texto=texto, tono=tono, destino=destino,
                tiendas=tiendas if destino == "seleccion" else None,
                desde=desde, hasta=hasta, creado_por=admin.id,
            ))
            db.session.commit()
            flash("Listo: Hilo lo dirá cuando entren.", "success")
            return redirect(url_for("mensajes_hilo.mensajes"))

    lista = MensajeHilo.query.order_by(MensajeHilo.creado.desc()).limit(60).all()
    vistos = dict(db.session.query(MensajeHiloVisto.mensaje_id, func.count(MensajeHiloVisto.id))
                  .group_by(MensajeHiloVisto.mensaje_id).all())
    tiendas = Store.query.order_by(Store.codigo).all()
    nombres_tiendas = {t.id: t.codigo for t in tiendas}
    hoy = date.today()

    filas = []
    for m in lista:
        if not m.activo:
            estado = "retirado"
        elif m.hasta < hoy:
            estado = "vencido"
        elif m.desde > hoy:
            estado = "programado"
        else:
            estado = "activo"
        filas.append({
            "m": m,
            "estado": estado,
            "vistos": vistos.get(m.id, 0),
            "total": len(_destinatarios(m)),
            "para": DESTINOS.get(m.destino, m.destino) if m.destino != "seleccion"
            else ", ".join(nombres_tiendas.get(i, str(i)) for i in sorted(m.ids_tiendas())),
        })

    return render_template(
        "admin/mensajes_hilo.html",
        filas=filas,
        tiendas=[t for t in tiendas if (t.estado or "ACTIVA").upper() == "ACTIVA"],
        tonos=TONOS,
        destinos=DESTINOS,
        hoy=hoy,
        en_una_semana=hoy + timedelta(days=6),
        largo_maximo=LARGO_MAXIMO,
        form=request.form if request.method == "POST" else {},
    )


@mensajes_hilo_bp.route("/admin/mensajes-hilo/<int:mensaje_id>/retirar", methods=["POST"])
def retirar(mensaje_id):
    _solo_admin()
    mensaje = MensajeHilo.query.get_or_404(mensaje_id)
    mensaje.activo = False
    db.session.commit()
    flash("Mensaje retirado: Hilo ya no lo dirá.", "success")
    return redirect(url_for("mensajes_hilo.mensajes"))


# ==========================================================
# API PARA HILO
# ==========================================================

@mensajes_hilo_bp.route("/api/hilo/mensajes")
def pendientes():
    usuario = _usuario()
    if not usuario:
        return jsonify([])
    hoy = date.today()
    vistos = {v for (v,) in db.session.query(MensajeHiloVisto.mensaje_id).filter_by(user_id=usuario.id).all()}
    activos = MensajeHilo.query.filter(
        MensajeHilo.activo.is_(True), MensajeHilo.desde <= hoy, MensajeHilo.hasta >= hoy
    ).order_by(MensajeHilo.creado).all()
    return jsonify([
        {
            "id": m.id,
            "texto": m.texto,
            "tono": m.tono,
            "autor": (m.autor.nombre if m.autor else "Administración"),
            "fecha": m.creado.strftime("%d/%m/%Y"),
        }
        for m in activos if m.id not in vistos and _le_toca(m, usuario)
    ][:5])


@mensajes_hilo_bp.route("/api/hilo/mensajes/<int:mensaje_id>/visto", methods=["POST"])
def marcar_visto(mensaje_id):
    usuario = _usuario()
    if not usuario:
        return jsonify({"ok": False}), 401
    if not MensajeHiloVisto.query.filter_by(mensaje_id=mensaje_id, user_id=usuario.id).first():
        try:
            db.session.add(MensajeHiloVisto(mensaje_id=mensaje_id, user_id=usuario.id))
            db.session.commit()
        except Exception:
            db.session.rollback()
    return jsonify({"ok": True})
