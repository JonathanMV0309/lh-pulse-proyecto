import os
from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify, session, abort
from app.extensions import db
from app.models.user import User
from app.models.store import Store
from app.models.cuadrante import CuadrantePersona, CuadranteAsignacion

cuadrante_bp = Blueprint("cuadrante", __name__, url_prefix="/cuadrante")

EMAIL_PERMITIDO = os.getenv("CUADRANTE_EMAIL_PERMITIDO", "")

PERSONAS_MANUALES = [
    {"nombre": "Asesora Ejemplo 1", "tipo": "ASESORA"},
    {"nombre": "Asesora Ejemplo 2", "tipo": "ASESORA"},
    {"nombre": "Asesor Ejemplo 3", "tipo": "ASESOR"},
    {"nombre": "Asesora Ejemplo 4", "tipo": "ASESORA"},
    {"nombre": "Administradora Ejemplo", "tipo": "ADMINISTRADORA"},
]

# Las demás tiendas: la administradora (nombre genérico) y sus asesoras fijas de «Metas y vendedores»
NOMBRE_ADMINISTRADORA = "Administradora"


def _es_tienda_34(usuario):
    return (usuario.correo or "").lower() == EMAIL_PERMITIDO.lower()


def _obtener_usuario_autorizado():
    if "user_id" not in session:
        abort(401)
    usuario = User.query.get(session["user_id"])
    if not usuario:
        abort(403)
    if _es_tienda_34(usuario):
        return usuario
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    if rol != "TIENDA" or not usuario.store_id:
        abort(403)
    return usuario

def _obtener_store_id(usuario):
    if not usuario.store_id:
        abort(403)
    return usuario.store_id

def _asegurar_personas(store_id):
    """
    Crea y devuelve únicamente las personas manuales autorizadas.
    No se crean asesoras automáticas.
    """
    personas_creadas = []

    for persona_info in PERSONAS_MANUALES:
        nombre = persona_info["nombre"]
        tipo = persona_info["tipo"]

        persona = CuadrantePersona.query.filter_by(
            store_id=store_id,
            nombre=nombre,
            tipo=tipo
        ).first()

        if not persona:
            persona = CuadrantePersona(
                store_id=store_id,
                advisor_id=None,
                nombre=nombre,
                tipo=tipo
            )
            db.session.add(persona)

        personas_creadas.append(persona)

    db.session.commit()
    return personas_creadas

def _nombre_corto(nombre):
    """«LAURA BETANCUR MONTOYA» -> «Laura Betancur»."""
    partes = str(nombre or "").strip().title().split()
    return " ".join(partes[:2]) if partes else "Asesora"


def _asesoras_fijas(store_id):
    """Asesoras fijas del último mes con ventas de la tienda (las mismas de «Metas y vendedores»)."""
    from app.models import AdvisorPerformance
    from app.services.advisor_goal_service import TIPO_FIJA, obtener_asesoras_validas_para_meta
    ultimo = (
        db.session.query(AdvisorPerformance.anio, AdvisorPerformance.mes)
        .filter(AdvisorPerformance.store_id == store_id)
        .order_by(AdvisorPerformance.anio.desc(), AdvisorPerformance.mes.desc())
        .first()
    )
    if not ultimo:
        return []
    return [a for a in obtener_asesoras_validas_para_meta(store_id, ultimo[0], ultimo[1]) if a["tipo_asesora"] == TIPO_FIJA]


def _personas_tienda(store_id):
    """La administradora y las asesoras fijas; se crean la primera vez y se reutilizan después."""
    administradora = CuadrantePersona.query.filter_by(store_id=store_id, tipo="ADMINISTRADORA").order_by(CuadrantePersona.id).first()
    if not administradora:
        administradora = CuadrantePersona(store_id=store_id, advisor_id=None, nombre=NOMBRE_ADMINISTRADORA, tipo="ADMINISTRADORA")
        db.session.add(administradora)
    administradora.activo = True
    asesoras = []
    for a in _asesoras_fijas(store_id):
        persona = CuadrantePersona.query.filter_by(store_id=store_id, advisor_id=a["advisor_id"]).order_by(CuadrantePersona.id).first()
        if not persona:
            persona = CuadrantePersona(store_id=store_id, advisor_id=a["advisor_id"], nombre=_nombre_corto(a["nombre"]), tipo="ASESORA")
            db.session.add(persona)
        persona.activo = True
        asesoras.append(persona)
    # Personas que creó Talento Humano en «Novedades» (sin código de asesora todavía)
    asesoras += CuadrantePersona.query.filter(
        CuadrantePersona.store_id == store_id, CuadrantePersona.advisor_id.is_(None),
        CuadrantePersona.tipo != "ADMINISTRADORA", CuadrantePersona.activo == True,  # noqa: E712
    ).all()
    db.session.commit()
    asesoras.sort(key=lambda p: p.nombre)
    return [administradora] + asesoras


@cuadrante_bp.route("/")
def cuadrante():
    usuario = _obtener_usuario_autorizado()
    store_id = _obtener_store_id(usuario)
    store = Store.query.get(store_id)
    return render_template("cuadrante.html", store=store)

@cuadrante_bp.route("/api/personas")
def api_personas():
    usuario = _obtener_usuario_autorizado()
    store_id = _obtener_store_id(usuario)

    if not _es_tienda_34(usuario):
        return jsonify([
            {"id": p.id, "nombre": p.nombre, "tipo": p.tipo, "advisor_id": p.advisor_id}
            for p in _personas_tienda(store_id)
        ])

    _asegurar_personas(store_id)

    # Consultar solo las personas manuales permitidas
    nombres_permitidos = [p["nombre"] for p in PERSONAS_MANUALES]
    personas = CuadrantePersona.query.filter(
        CuadrantePersona.store_id == store_id,
        CuadrantePersona.activo == True,
        CuadrantePersona.nombre.in_(nombres_permitidos)
    ).order_by(CuadrantePersona.tipo, CuadrantePersona.nombre).all()

    data = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "tipo": p.tipo,
            "advisor_id": p.advisor_id
        }
        for p in personas
    ]
    return jsonify(data)

@cuadrante_bp.route("/api/asignaciones")
def api_asignaciones():
    usuario = _obtener_usuario_autorizado()
    store_id = _obtener_store_id(usuario)

    inicio = request.args.get("inicio")
    fin = request.args.get("fin")
    if not inicio or not fin:
        hoy = date.today()
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)

    asignaciones = CuadranteAsignacion.query.filter(
        CuadranteAsignacion.store_id == store_id,
        CuadranteAsignacion.fecha >= inicio,
        CuadranteAsignacion.fecha <= fin
    ).order_by(CuadranteAsignacion.fecha, CuadranteAsignacion.turno, CuadranteAsignacion.orden).all()

    data = []
    for a in asignaciones:
        data.append({
            "id": a.id,
            "persona_id": a.persona_id,
            "nombre": a.persona.nombre,
            "tipo": a.persona.tipo,
            "fecha": a.fecha.isoformat(),
            "turno": a.turno,
            "orden": a.orden
        })
    return jsonify(data)

@cuadrante_bp.route("/api/guardar", methods=["POST"])
def api_guardar():
    usuario = _obtener_usuario_autorizado()
    store_id = _obtener_store_id(usuario)
    data = request.get_json()

    if not data or "asignaciones" not in data:
        return jsonify({"error": "Datos inválidos"}), 400

    asignaciones_nuevas = data["asignaciones"]

    # En las demás tiendas solo se aceptan personas de su propia tienda
    if not _es_tienda_34(usuario):
        propias = {p.id for p in CuadrantePersona.query.filter_by(store_id=store_id).all()}
        if any(int(a.get("persona_id") or 0) not in propias for a in asignaciones_nuevas):
            return jsonify({"error": "Hay personas que no son de esta tienda"}), 400

    # Eliminar las asignaciones existentes solo del rango de fechas enviado
    fechas = [a["fecha"] for a in asignaciones_nuevas]
    if fechas:
        fecha_min = min(fechas)
        fecha_max = max(fechas)
        CuadranteAsignacion.query.filter(
            CuadranteAsignacion.store_id == store_id,
            CuadranteAsignacion.fecha >= fecha_min,
            CuadranteAsignacion.fecha <= fecha_max
        ).delete()

    for a in asignaciones_nuevas:
        nueva = CuadranteAsignacion(
            store_id=store_id,
            persona_id=a["persona_id"],
            fecha=date.fromisoformat(a["fecha"]),
            turno=a["turno"],
            orden=a.get("orden", 0)
        )
        db.session.add(nueva)

    db.session.commit()
    return jsonify({"success": True, "message": "Cuadrante guardado correctamente."})

@cuadrante_bp.route("/api/eliminar", methods=["POST"])
def api_eliminar():
    usuario = _obtener_usuario_autorizado()
    store_id = _obtener_store_id(usuario)
    data = request.get_json()
    asignacion_id = data.get("id")
    if not asignacion_id:
        return jsonify({"error": "ID no proporcionado"}), 400

    asignacion = CuadranteAsignacion.query.get(asignacion_id)
    if not asignacion or asignacion.store_id != store_id:
        abort(404)

    db.session.delete(asignacion)
    db.session.commit()
    return jsonify({"success": True})