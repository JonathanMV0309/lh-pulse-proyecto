"""Planilla de horas del equipo (formato de Talento Humano) dentro de «Horarios del equipo».

- La tienda ve y llena solo la suya (la 34 con sus mismas personas de siempre).
- La administración y quien maneja los horarios (Ismael, PLANILLA_HORARIOS en el .env) abren la de
  cualquier tienda (?store_id=), la corrigen y descargan el Excel del mes.
"""
import os
from datetime import date

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file, session

from app.extensions import db
from app.models.store import Store
from app.models.user import User

planilla_bp = Blueprint("planilla", __name__, url_prefix="/planilla")
ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}
_tablas_listas = False


def _ve_todas(usuario, rol):
    """Administración o el encargado de horarios de Talento Humano.

    El analista que solo lee ausencias en «Novedades» no entra a las planillas: ahí se ve el tipo de novedad."""
    from app.routes.novedades import _rol as rol_novedades
    if rol_novedades(usuario) == "lector":
        return False
    correos = {c.strip().lower() for c in (os.environ.get("PLANILLA_HORARIOS") or "").split(",") if c.strip()}
    return rol in ROLES_ADMIN or (usuario.correo or "").strip().lower() in correos


@planilla_bp.app_context_processor
def _menu():
    """Para el menú: «Horarios de las tiendas»."""
    try:
        usuario = db.session.get(User, session["user_id"]) if session.get("user_id") else None
        rol = usuario.role.nombre.strip().upper() if usuario and usuario.role and usuario.role.nombre else ""
        return {"ve_planillas": bool(usuario) and rol != "TIENDA" and _ve_todas(usuario, rol)}
    except Exception:
        return {"ve_planillas": False}


def _preparar():
    global _tablas_listas
    if not _tablas_listas:
        from app.models.cuadrante_horas import crear_tablas_si_faltan
        crear_tablas_si_faltan()
        _tablas_listas = True


def _contexto():
    """(usuario, tienda, personas) según quién entra."""
    from app.routes import cuadrante as c
    if "user_id" not in session:
        abort(401)
    usuario = db.session.get(User, session["user_id"])
    if not usuario:
        abort(403)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    if c._es_tienda_34(usuario) or rol == "TIENDA":
        store_id = usuario.store_id
    elif _ve_todas(usuario, rol):
        store_id = request.args.get("store_id", type=int) or (request.get_json(silent=True) or {}).get("store_id")
    else:
        abort(403)
    tienda = db.session.get(Store, int(store_id)) if store_id else None
    if not tienda:
        abort(404)
    _preparar()
    es_34 = c._es_tienda_34(usuario) or (tienda.codigo or "").replace(" ", "").upper() == "S-34"
    if es_34:
        c._asegurar_personas(tienda.id)
        from app.models.cuadrante import CuadrantePersona
        nombres = [p["nombre"] for p in c.PERSONAS_MANUALES]
        personas = CuadrantePersona.query.filter(CuadrantePersona.store_id == tienda.id, CuadrantePersona.activo == True,  # noqa: E712
                                                 CuadrantePersona.nombre.in_(nombres)).order_by(CuadrantePersona.tipo, CuadrantePersona.nombre).all()
    else:
        personas = c._personas_tienda(tienda.id)
    return usuario, tienda, personas


def _domingo():
    from app.services.planilla_service import domingo_de
    texto = request.args.get("fecha") or (request.get_json(silent=True) or {}).get("domingo")
    try:
        return domingo_de(date.fromisoformat(texto)) if texto else domingo_de(date.today())
    except ValueError:
        abort(400)


@planilla_bp.get("/")
def pagina():
    """Para la administración: elegir la tienda y ver su planilla."""
    if "user_id" not in session:
        abort(401)
    usuario = db.session.get(User, session["user_id"])
    rol = usuario.role.nombre.strip().upper() if usuario and usuario.role and usuario.role.nombre else ""
    if not usuario or not _ve_todas(usuario, rol):
        abort(403)
    tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").order_by(Store.codigo).all()
    return render_template("planilla/admin.html", tiendas=tiendas, store_id=request.args.get("store_id", type=int))


@planilla_bp.get("/api/semana")
def api_semana():
    from app.services import planilla_service as s
    _, tienda, personas = _contexto()
    datos = s.planilla(tienda, personas, _domingo())
    datos["tienda"] = {"id": tienda.id, "codigo": tienda.codigo, "nombre": tienda.nombre}
    datos["agregar"] = not _es_34(tienda)
    return jsonify(datos)


@planilla_bp.post("/api/semana")
def api_guardar():
    from app.services import planilla_service as s
    _, tienda, personas = _contexto()
    try:
        s.guardar(tienda, personas, _domingo(), request.get_json(silent=True) or {})
    except ValueError as error:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Planilla: no se pudo guardar")
        return jsonify({"ok": False, "error": "No se pudo guardar la planilla"}), 500
    datos = s.planilla(tienda, personas, _domingo())
    datos["agregar"] = not _es_34(tienda)
    datos["ok"] = True
    return jsonify(datos)


@planilla_bp.post("/api/horario")
def api_horario():
    from app.services import planilla_service as s
    _, tienda, _ = _contexto()
    filas = (request.get_json(silent=True) or {}).get("horario") or []
    s.guardar_horario(tienda, filas)
    return jsonify({"ok": True, "horario": s.horario(tienda)[0]})


def _es_34(tienda):
    return (tienda.codigo or "").replace(" ", "").upper() == "S-34"


@planilla_bp.post("/api/persona")
def api_agregar_persona():
    """Agrega a mano una persona a la planilla de la tienda (auxiliar, subadministradora…)."""
    from app.models.cuadrante import CuadrantePersona
    from app.models.cuadrante_horas import CuadrantePersonaDato
    from app.services.planilla_service import CARGOS
    _, tienda, personas = _contexto()
    if _es_34(tienda):
        return jsonify({"ok": False, "error": "En esta tienda las personas se manejan en los turnos de siempre"}), 400
    d = request.get_json(silent=True) or {}
    nombre = " ".join(str(d.get("nombre") or "").split()).title()[:120]
    cargo = d.get("cargo") if d.get("cargo") in CARGOS and d.get("cargo") != "Administradora" else "Auxiliar"
    cedula = "".join(ch for ch in str(d.get("cedula") or "") if ch.isdigit())[:20]
    if len(nombre) < 3:
        return jsonify({"ok": False, "error": "Escribe el nombre completo de la persona"}), 400
    if any((p.nombre or "").lower() == nombre.lower() for p in personas):
        return jsonify({"ok": False, "error": f"{nombre} ya está en la planilla"}), 400
    # Si la habían quitado antes, vuelve con sus horas guardadas
    persona = CuadrantePersona.query.filter(CuadrantePersona.store_id == tienda.id, CuadrantePersona.advisor_id.is_(None),
                                            CuadrantePersona.tipo != "ADMINISTRADORA", db.func.lower(CuadrantePersona.nombre) == nombre.lower()).first()
    if not persona:
        persona = CuadrantePersona(store_id=tienda.id, advisor_id=None, nombre=nombre, tipo="ASESORA")
        db.session.add(persona)
    persona.activo = True
    db.session.flush()
    dato = db.session.get(CuadrantePersonaDato, persona.id) or CuadrantePersonaDato(persona_id=persona.id)
    dato.cargo = cargo
    dato.cedula = cedula or dato.cedula
    db.session.add(dato)
    db.session.commit()
    return jsonify({"ok": True})


@planilla_bp.delete("/api/persona/<int:persona_id>")
def api_quitar_persona(persona_id):
    """Quita de la planilla a una persona agregada a mano (sus horas quedan guardadas)."""
    from app.models.cuadrante import CuadrantePersona
    _, tienda, _ = _contexto()
    persona = db.session.get(CuadrantePersona, persona_id)
    if not persona or persona.store_id != tienda.id or persona.advisor_id or (persona.tipo or "").upper() == "ADMINISTRADORA":
        return jsonify({"ok": False, "error": "Solo se pueden quitar las personas agregadas a mano"}), 400
    persona.activo = False
    db.session.commit()
    return jsonify({"ok": True})


@planilla_bp.get("/exportar")
def exportar():
    from app.services import planilla_service as s
    _, tienda, personas = _contexto()
    try:
        anio, mes = [int(x) for x in (request.args.get("mes") or date.today().strftime("%Y-%m")).split("-")[:2]]
        assert 1 <= mes <= 12
    except Exception:
        abort(400)
    archivo = s.exportar_mes(tienda, personas, anio, mes)
    nombre = f"{anio} GTH-ODSCTD-003 Calendario Trabajo de Turnos {tienda.codigo} {s.MESES[mes - 1]}.xlsx"
    return send_file(archivo, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
