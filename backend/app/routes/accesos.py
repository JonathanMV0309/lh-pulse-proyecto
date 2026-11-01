from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, session, abort
from sqlalchemy import func

from app.extensions import db
from app.models.registro_acceso import RegistroAcceso
from app.models.user import User


# ==========================================================
# BLUEPRINT · Registro de accesos (solo administradores)
# ==========================================================

accesos_bp = Blueprint(
    "accesos",
    __name__
)

DIAS_GUARDADOS = 180
ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}

RESULTADOS = {
    "ok": "Entró",
    "clave_incorrecta": "Contraseña incorrecta",
    "usuario_no_existe": "Usuario no existe",
    "salida": "Cerró sesión",
}


def ip_cliente():
    """IP de quien hace la petición (respeta un proxy si lo hay)."""
    reenviada = request.headers.get("X-Forwarded-For", "")
    if reenviada:
        return reenviada.split(",")[0].strip()[:45]
    return (request.remote_addr or "")[:45]


def registrar_acceso(resultado, usuario=None, correo=None):
    """
    Guarda un evento de acceso. Nunca interrumpe el login:
    si algo falla, se descarta el registro y el login sigue normal.
    """
    try:
        db.session.add(RegistroAcceso(
            user_id=usuario.id if usuario else None,
            correo=(correo or (usuario.correo if usuario else None) or "")[:150] or None,
            resultado=resultado,
            ip=ip_cliente(),
            navegador=(request.headers.get("User-Agent") or "")[:300] or None,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def crear_tabla_si_falta(app):
    """Crea la tabla registro_accesos la primera vez (no toca las demás tablas)."""
    with app.app_context():
        try:
            RegistroAcceso.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as error:
            app.logger.warning("No se pudo crear registro_accesos: %s", error)


def navegador_corto(texto):
    """'Chrome en Windows', 'Safari en iPhone', etc."""
    t = (texto or "").lower()
    if not t:
        return "—"
    nav = "Edge" if "edg/" in t else "Opera" if "opr/" in t else "Chrome" if "chrome" in t else "Firefox" if "firefox" in t else "Safari" if "safari" in t else "Otro"
    so = "Android" if "android" in t else "iPhone" if "iphone" in t else "iPad" if "ipad" in t else "Windows" if "windows" in t else "Mac" if "mac os" in t else "Linux" if "linux" in t else ""
    return f"{nav} en {so}" if so else nav


def _usuario_admin():
    user_id = session.get("user_id")
    if not user_id:
        abort(401)
    usuario = User.query.get(user_id)
    rol = str(usuario.role.nombre).upper().strip() if usuario and usuario.role and usuario.role.nombre else ""
    if rol not in ROLES_ADMIN:
        abort(403)
    return usuario


# ==========================================================
# PÁGINA
# ==========================================================

@accesos_bp.route("/admin/accesos")
def registro_accesos():

    _usuario_admin()

    # Limpieza: solo se guardan los últimos 180 días
    try:
        RegistroAcceso.query.filter(
            RegistroAcceso.fecha < datetime.now() - timedelta(days=DIAS_GUARDADOS)
        ).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()

    texto = (request.args.get("q") or "").strip()
    resultado = (request.args.get("resultado") or "").strip()
    dias = request.args.get("dias", "7")
    dias = int(dias) if dias.isdigit() and 0 < int(dias) <= DIAS_GUARDADOS else 7

    desde = datetime.now() - timedelta(days=dias)
    consulta = RegistroAcceso.query.filter(RegistroAcceso.fecha >= desde)

    if resultado in RESULTADOS:
        consulta = consulta.filter(RegistroAcceso.resultado == resultado)

    if texto:
        patron = f"%{texto}%"
        consulta = consulta.outerjoin(User, RegistroAcceso.user_id == User.id).filter(
            db.or_(RegistroAcceso.correo.ilike(patron), User.nombre.ilike(patron), RegistroAcceso.ip.ilike(patron))
        )

    filas = consulta.order_by(RegistroAcceso.fecha.desc()).limit(500).all()

    # Resumen
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    entradas_hoy = RegistroAcceso.query.filter(RegistroAcceso.fecha >= hoy, RegistroAcceso.resultado == "ok").count()
    fallidos_hoy = RegistroAcceso.query.filter(
        RegistroAcceso.fecha >= hoy,
        RegistroAcceso.resultado.in_(["clave_incorrecta", "usuario_no_existe"])
    ).count()
    usuarios_7d = db.session.query(func.count(func.distinct(RegistroAcceso.user_id))).filter(
        RegistroAcceso.fecha >= datetime.now() - timedelta(days=7),
        RegistroAcceso.resultado == "ok"
    ).scalar() or 0

    # Alertas: 5 o más intentos fallidos con el mismo usuario en la última hora
    sospechosos = db.session.query(
        RegistroAcceso.correo,
        func.count(RegistroAcceso.id).label("intentos"),
        func.max(RegistroAcceso.fecha).label("ultimo")
    ).filter(
        RegistroAcceso.fecha >= datetime.now() - timedelta(hours=1),
        RegistroAcceso.resultado.in_(["clave_incorrecta", "usuario_no_existe"])
    ).group_by(RegistroAcceso.correo).having(func.count(RegistroAcceso.id) >= 5).all()

    return render_template(
        "admin/accesos.html",
        filas=filas,
        resultados=RESULTADOS,
        navegador_corto=navegador_corto,
        texto=texto,
        resultado=resultado,
        dias=dias,
        entradas_hoy=entradas_hoy,
        fallidos_hoy=fallidos_hoy,
        usuarios_7d=usuarios_7d,
        sospechosos=sospechosos,
        dias_guardados=DIAS_GUARDADOS,
    )
