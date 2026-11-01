"""Novedades del personal (incapacidades, vacaciones, licencias, traslados, ingresos y retiros…).

Quién ve qué:
- Talento Humano (Yorely) y el administrador principal (NOVEDADES_EDITORES): crean, editan y ven
  todo, incluidas las observaciones.
- Analista de mercadeo (Victor, NOVEDADES_LECTORES): solo las ausencias, con persona, tienda, de qué
  día a qué día y cuántas horas. No ve el tipo ni las observaciones.
- Cada tienda: las novedades de su propia gente (tipo y fechas), sin observaciones.
Los correos se configuran en el .env (NOVEDADES_EDITORES y NOVEDADES_LECTORES, separados por comas).
SIN_ADMINISTRACION: administradores que no ven cargas de datos, metas y vendedores ni registro de accesos.
"""
import os
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, session, url_for

from app.extensions import db
from app.models.advisor import Advisor
from app.models.store import Store
from app.models.user import User

novedades_bp = Blueprint("novedades", __name__, url_prefix="/novedades")

TIPOS = [
    # clave, nombre, es ausencia (cuenta días y horas), necesita persona
    ("INCAPACIDAD", "Incapacidad", True, True),
    ("VACACIONES", "Vacaciones", True, True),
    ("PERMISO_ESPECIAL", "Permiso especial", True, True),
    ("LICENCIA_NO_REMUNERADA", "Licencia no remunerada", True, True),
    ("LICENCIA_LUTO", "Licencia de luto", True, True),
    ("LICENCIA_MATERNIDAD", "Licencia de maternidad", True, True),
    ("CALAMIDAD", "Calamidad familiar", True, True),
    ("CIERRE_TIENDA", "Cierre de tienda", True, False),
    ("TRASLADO", "Traslado de tienda", False, True),
    ("VOLANTE", "Asesora volante", False, True),
    ("INGRESO", "Ingreso a la empresa", False, True),
    ("RETIRO", "Retiro de la empresa", False, True),
]
NOMBRE_TIPO = {t[0]: t[1] for t in TIPOS}
AUSENCIA = {t[0] for t in TIPOS if t[2]}
HORAS_DIA = 7   # jornada diaria del formato de Talento Humano (8 h con 1 h de almuerzo)
_tabla_lista = False


def _correos(variable, defecto):
    return {c.strip().lower() for c in (os.environ.get(variable) or defecto).split(",") if c.strip()}


def _rol(usuario):
    """'editor', 'lector', 'tienda' o None."""
    if not usuario:
        return None
    correo = (usuario.correo or "").strip().lower()
    if correo in _correos("NOVEDADES_EDITORES", ""):
        return "editor"
    if correo in _correos("NOVEDADES_LECTORES", ""):
        return "lector"
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    if rol == "TIENDA" and usuario.store_id:
        return "tienda"
    return None


def _usuario():
    global _tabla_lista
    if "user_id" not in session:
        abort(401)
    usuario = db.session.get(User, session["user_id"])
    rol = _rol(usuario)
    if not rol:
        abort(403)
    if not _tabla_lista:
        from app.models.novedad_personal import crear_tabla_si_falta
        crear_tabla_si_falta()
        _tabla_lista = True
    return usuario, rol


def _sin_administracion(usuario):
    """Talento Humano, mercadeo y horarios: administradores sin cargas de datos, metas ni registro de accesos."""
    correo = ((usuario.correo if usuario else "") or "").strip().lower()
    return correo in _correos("SIN_ADMINISTRACION", "")


BLOQUEADAS = {"accesos", "import_excel", "admin_goals", "admin_goals_distribution"}


@novedades_bp.before_app_request
def _bloquear_administracion():
    """Aunque escriban la dirección a mano, esos usuarios no entran a esas páginas."""
    endpoint = request.endpoint or ""
    if endpoint.split(".")[0] not in BLOQUEADAS and endpoint != "app_pages.historial_importaciones":
        return None
    if not session.get("user_id") or not _sin_administracion(db.session.get(User, session["user_id"])):
        return None
    if request.method == "GET":
        return redirect(url_for("dashboard.dashboard"))
    abort(403)


@novedades_bp.app_context_processor
def _menu():
    """Para el menú: si el usuario puede ver «Novedades del personal» y la parte de administración."""
    try:
        usuario = db.session.get(User, session["user_id"]) if session.get("user_id") else None
        return {"rol_novedades": _rol(usuario), "sin_administracion": _sin_administracion(usuario)}
    except Exception:
        return {"rol_novedades": None, "sin_administracion": False}


def _dias(n):
    return (n.hasta - n.desde).days + 1


def _json(n, rol, tiendas):
    tienda = tiendas.get(n.store_id)
    base = {"id": n.id, "store_id": n.store_id, "tienda": f"{tienda.codigo} · {tienda.nombre}" if tienda else "",
            "persona": n.nombre or ("Toda la tienda" if n.tipo == "CIERRE_TIENDA" else ""), "cargo": n.cargo or "",
            "desde": n.desde.isoformat(), "hasta": n.hasta.isoformat(), "dias": _dias(n),
            "horas": n.horas if n.tipo in AUSENCIA else None}
    if rol == "lector":
        return base
    base.update({"tipo": n.tipo, "tipo_nombre": NOMBRE_TIPO.get(n.tipo, n.tipo), "ausencia": n.tipo in AUSENCIA,
                 "destino": (lambda d: f"{d.codigo} · {d.nombre}" if d else "")(tiendas.get(n.tienda_destino_id))})
    if rol == "editor":
        base.update({"observacion": n.observacion or "", "advisor_id": n.advisor_id, "tienda_destino_id": n.tienda_destino_id,
                     "creado_por": n.creado_por or ""})
    return base


@novedades_bp.get("/")
def pagina():
    usuario, rol = _usuario()
    tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").order_by(Store.codigo).all() if rol != "tienda" else []
    return render_template("novedades/index.html", rol=rol, tiendas=tiendas,
                           tipos=[{"clave": t[0], "nombre": t[1], "ausencia": t[2], "persona": t[3]} for t in TIPOS], horas_dia=HORAS_DIA)


def _consulta(usuario, rol):
    """Las novedades que ve este usuario con los filtros de la pantalla (mes, tienda, tipo)."""
    from app.models.novedad_personal import NovedadPersonal
    q = NovedadPersonal.query
    if rol == "tienda":
        q = q.filter(NovedadPersonal.store_id == usuario.store_id)
    elif request.args.get("store_id", type=int):
        q = q.filter(NovedadPersonal.store_id == request.args.get("store_id", type=int))
    if rol == "lector":
        q = q.filter(NovedadPersonal.tipo.in_(sorted(AUSENCIA)))
    mes = request.args.get("mes") or ""
    if len(mes) == 7:
        anio, m = int(mes[:4]), int(mes[5:])
        inicio = date(anio, m, 1)
        fin = (date(anio + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
        q = q.filter(NovedadPersonal.desde <= fin, NovedadPersonal.hasta >= inicio)
    tipo = request.args.get("tipo")
    if tipo and rol != "lector":
        q = q.filter(NovedadPersonal.tipo == tipo)
    return q.order_by(NovedadPersonal.desde.desc(), NovedadPersonal.id.desc()).limit(5000).all()


@novedades_bp.get("/api/lista")
def api_lista():
    usuario, rol = _usuario()
    filas = _consulta(usuario, rol)
    tiendas = {t.id: t for t in Store.query.all()}
    return jsonify({"rol": rol, "novedades": [_json(n, rol, tiendas) for n in filas]})


@novedades_bp.get("/exportar")
def exportar():
    """Excel con lo mismo que se ve en pantalla (cada rol con sus columnas)."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    usuario, rol = _usuario()
    tiendas = {t.id: t for t in Store.query.all()}
    filas = [_json(n, rol, tiendas) for n in _consulta(usuario, rol)]
    columnas = [("Tienda", "tienda", 34), ("Persona", "persona", 30), ("Cargo", "cargo", 16)]
    if rol != "lector":
        columnas.append(("Tipo", "tipo_nombre", 24))
    columnas += [("Desde", "desde", 12), ("Hasta", "hasta", 12), ("Días", "dias", 8), ("Horas", "horas", 9)]
    if rol != "lector":
        columnas.append(("Se traslada a", "destino", 30))
    if rol == "editor":
        columnas += [("Observaciones", "observacion", 50), ("Registró", "creado_por", 30)]

    wb = Workbook()
    ws = wb.active
    ws.title = "Novedades"
    mes = request.args.get("mes") or ""
    titulo = "Ausencias del personal" if rol == "lector" else "Novedades del personal"
    tienda_f = tiendas.get(request.args.get("store_id", type=int)) if rol != "tienda" else tiendas.get(usuario.store_id)
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = " · ".join(x for x in [f"Mes {mes[5:]}/{mes[:4]}" if len(mes) == 7 else "Todos los meses",
                                      f"{tienda_f.codigo} {tienda_f.nombre}" if tienda_f else "Todas las tiendas",
                                      f"Descargado el {date.today():%d/%m/%Y}"] if x)
    ws["A2"].font = Font(color="6B6259")
    fondo, borde = PatternFill("solid", fgColor="F2E6D3"), Border(bottom=Side(style="thin", color="B8AC9A"))
    for j, (nombre, _, ancho) in enumerate(columnas, start=1):
        c = ws.cell(row=4, column=j, value=nombre)
        c.font, c.fill, c.border = Font(bold=True), fondo, borde
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = ancho
    for i, f in enumerate(filas, start=5):
        for j, (_, clave, _) in enumerate(columnas, start=1):
            v = f.get(clave)
            if clave in ("desde", "hasta") and v:
                v = date.fromisoformat(v)
            c = ws.cell(row=i, column=j, value=v if v not in ("", None) else None)
            if clave in ("desde", "hasta"):
                c.number_format = "DD/MM/YYYY"
            if clave == "observacion":
                c.alignment = Alignment(wrap_text=True, vertical="top")
    if filas:   # totales de días y horas
        fin = 4 + len(filas)
        ws.cell(row=fin + 1, column=1, value="Total").font = Font(bold=True)
        for j, (_, clave, _) in enumerate(columnas, start=1):
            if clave in ("dias", "horas"):
                letra = get_column_letter(j)
                ws.cell(row=fin + 1, column=j, value=f"=SUM({letra}5:{letra}{fin})").font = Font(bold=True)
    else:
        ws.cell(row=5, column=1, value="No hay novedades con esos filtros.")
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(columnas))}{max(4 + len(filas), 5)}"
    salida = io.BytesIO()
    wb.save(salida)
    salida.seek(0)
    nombre = f"{titulo} {mes or 'todos'}{' ' + tienda_f.codigo if tienda_f else ''}.xlsx"
    return send_file(salida, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@novedades_bp.get("/api/personas")
def api_personas():
    """La gente actual de la tienda (para el formulario de Talento Humano).

    Las asesoras son las del último mes con ventas de esa tienda, las mismas de «Metas y vendedores»;
    la tabla de asesoras guarda también a las que ya no están. ?incluir=<advisor_id> conserva a la
    persona de una novedad vieja al editarla."""
    _, rol = _usuario()
    if rol != "editor":
        abort(403)
    store_id = request.args.get("store_id", type=int)
    lista = [{"advisor_id": None, "nombre": "Administradora", "cargo": "Administradora"}]
    for a in sorted(_asesoras_actuales(store_id), key=lambda a: (a["tipo_asesora"] != "FIJA", a["nombre"] or "")):
        lista.append({"advisor_id": a["advisor_id"], "nombre": (a["nombre"] or "").strip().title(),
                      "cargo": "Asesora" if a["tipo_asesora"] == "FIJA" else "Auxiliar"})
    incluir = request.args.get("incluir", type=int)
    if incluir and not any(p["advisor_id"] == incluir for p in lista):
        vieja = db.session.get(Advisor, incluir)
        if vieja:
            lista.append({"advisor_id": vieja.id, "nombre": (vieja.nombre or "").strip().title(), "cargo": "Asesora"})
    # Personas creadas aquí por Talento Humano (todavía sin código de asesora)
    for p, cargo in _personas_creadas(store_id):
        lista.append({"advisor_id": None, "persona_id": p.id, "nombre": p.nombre, "cargo": cargo, "creada": True})
    return jsonify(lista)


def _asesoras_actuales(store_id):
    if not store_id:
        return []
    from app.models import AdvisorPerformance
    from app.services.advisor_goal_service import obtener_asesoras_validas_para_meta
    ultimo = (db.session.query(AdvisorPerformance.anio, AdvisorPerformance.mes)
              .filter(AdvisorPerformance.store_id == store_id)
              .order_by(AdvisorPerformance.anio.desc(), AdvisorPerformance.mes.desc()).first())
    return obtener_asesoras_validas_para_meta(store_id, ultimo[0], ultimo[1]) if ultimo else []


CARGOS_NUEVOS = ["Asesora", "Auxiliar", "Subadministradora", "Segunda", "Asesora volante"]


def _personas_creadas(store_id):
    if not store_id:
        return []
    from app.models.cuadrante import CuadrantePersona
    from app.models.cuadrante_horas import CuadrantePersonaDato, crear_tablas_si_faltan
    crear_tablas_si_faltan()
    filas = CuadrantePersona.query.filter(CuadrantePersona.store_id == store_id, CuadrantePersona.advisor_id.is_(None),
                                          CuadrantePersona.tipo != "ADMINISTRADORA", CuadrantePersona.activo == True).order_by(CuadrantePersona.nombre).all()  # noqa: E712
    datos = {d.persona_id: d for d in CuadrantePersonaDato.query.filter(CuadrantePersonaDato.persona_id.in_([p.id for p in filas] or [0]))}
    return [(p, (datos.get(p.id).cargo if datos.get(p.id) and datos.get(p.id).cargo else "Asesora")) for p in filas]


@novedades_bp.post("/api/persona")
def api_crear_persona():
    """Crea una persona en la tienda (aparece en «Horarios del equipo» de esa tienda)."""
    from app.models.cuadrante import CuadrantePersona
    from app.models.cuadrante_horas import CuadrantePersonaDato, crear_tablas_si_faltan
    _, rol = _usuario()
    if rol != "editor":
        abort(403)
    d = request.get_json(silent=True) or {}
    tienda = db.session.get(Store, int(d.get("store_id") or 0))
    nombre = " ".join(str(d.get("nombre") or "").split()).title()[:120]
    cargo = d.get("cargo") if d.get("cargo") in CARGOS_NUEVOS else "Asesora"
    cedula = "".join(ch for ch in str(d.get("cedula") or "") if ch.isdigit())[:20]
    if not tienda:
        return jsonify({"ok": False, "error": "Elige la tienda"}), 400
    if len(nombre) < 3:
        return jsonify({"ok": False, "error": "Escribe el nombre completo de la persona"}), 400
    crear_tablas_si_faltan()
    existente = next((p for p, _ in _personas_creadas(tienda.id) if p.nombre.lower() == nombre.lower()), None)
    persona = existente or CuadrantePersona(store_id=tienda.id, advisor_id=None, nombre=nombre, tipo="ASESORA", activo=True)
    if not existente:
        db.session.add(persona)
        db.session.flush()
    dato = db.session.get(CuadrantePersonaDato, persona.id) or CuadrantePersonaDato(persona_id=persona.id)
    dato.cargo = cargo
    dato.cedula = cedula or dato.cedula
    db.session.add(dato)
    db.session.commit()
    return jsonify({"ok": True, "persona": {"advisor_id": None, "persona_id": persona.id, "nombre": persona.nombre, "cargo": cargo, "creada": True}})


@novedades_bp.post("/api")
def api_guardar():
    from app.models.novedad_personal import NovedadPersonal
    usuario, rol = _usuario()
    if rol != "editor":
        abort(403)
    d = request.get_json(silent=True) or {}
    tipo = d.get("tipo")
    if tipo not in NOMBRE_TIPO:
        return jsonify({"ok": False, "error": "Elige el tipo de novedad"}), 400
    tienda = db.session.get(Store, int(d.get("store_id") or 0))
    if not tienda:
        return jsonify({"ok": False, "error": "Elige la tienda"}), 400
    try:
        desde = date.fromisoformat(d.get("desde"))
        hasta = date.fromisoformat(d.get("hasta") or d.get("desde"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Revisa las fechas"}), 400
    if hasta < desde:
        return jsonify({"ok": False, "error": "La fecha final no puede ser antes de la inicial"}), 400
    persona = (d.get("nombre") or "").strip()[:150]
    necesita_persona = next(t[3] for t in TIPOS if t[0] == tipo)
    if necesita_persona and not persona:
        return jsonify({"ok": False, "error": "Elige la persona"}), 400
    destino = None
    if tipo == "TRASLADO":
        destino = db.session.get(Store, int(d.get("tienda_destino_id") or 0))
        if not destino or destino.id == tienda.id:
            return jsonify({"ok": False, "error": "Elige la tienda a la que se traslada"}), 400
    n = db.session.get(NovedadPersonal, int(d["id"])) if d.get("id") else None
    if d.get("id") and not n:
        abort(404)
    antes = (n.store_id, n.tipo, n.desde, n.hasta) if n else None
    if not n:
        n = NovedadPersonal(creado_por=usuario.correo)
        db.session.add(n)
    advisor_id = d.get("advisor_id")
    n.store_id, n.tipo, n.desde, n.hasta = tienda.id, tipo, desde, hasta
    n.advisor_id = int(advisor_id) if advisor_id not in (None, "", "null") else None
    n.nombre = persona or None
    n.cargo = (d.get("cargo") or "").strip()[:30] or None
    n.tienda_destino_id = destino.id if destino else None
    if tipo in AUSENCIA:
        try:
            horas = float(d.get("horas")) if d.get("horas") not in (None, "") else None
        except ValueError:
            horas = None
        n.horas = horas if horas is not None and horas >= 0 else ((hasta - desde).days + 1) * HORAS_DIA
    else:
        n.horas = None
    n.observacion = (d.get("observacion") or "").strip()[:500] or None
    db.session.commit()
    _cuota_por_cierre(antes, (n.store_id, n.tipo, n.desde, n.hasta))
    return jsonify({"ok": True, "id": n.id})


@novedades_bp.delete("/api/<int:novedad_id>")
def api_borrar(novedad_id):
    from app.models.novedad_personal import NovedadPersonal
    _, rol = _usuario()
    if rol != "editor":
        abort(403)
    n = db.session.get(NovedadPersonal, novedad_id)
    if not n:
        abort(404)
    antes = (n.store_id, n.tipo, n.desde, n.hasta)
    db.session.delete(n)
    db.session.commit()
    _cuota_por_cierre(antes, None)
    return jsonify({"ok": True})


def _admin_cierres():
    """Configuración › Cierres de tienda: solo el administrador principal (CIERRES_TIENDA_ADMIN en el .env)."""
    usuario = db.session.get(User, session["user_id"]) if session.get("user_id") else None
    correo = ((usuario.correo if usuario else "") or "").strip().lower()
    if not usuario or correo not in _correos("CIERRES_TIENDA_ADMIN", ""):
        abort(403)
    from app.models.novedad_personal import crear_tabla_si_falta
    crear_tabla_si_falta()
    return usuario


@novedades_bp.get("/api/cierres")
def api_cierres():
    from app.models.novedad_personal import NovedadPersonal
    _admin_cierres()
    tiendas = Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").order_by(Store.codigo).all()
    nombres = {s.id: s for s in tiendas}
    filas = NovedadPersonal.query.filter_by(tipo="CIERRE_TIENDA").order_by(NovedadPersonal.desde.desc()).limit(100).all()
    return jsonify({"ok": True,
                    "tiendas": [{"id": s.id, "codigo": s.codigo, "nombre": s.nombre} for s in tiendas],
                    "cierres": [{"id": n.id, "store_id": n.store_id,
                                 "tienda": (f"{nombres[n.store_id].codigo} · {nombres[n.store_id].nombre}" if n.store_id in nombres else str(n.store_id)),
                                 "desde": n.desde.isoformat(), "hasta": (n.hasta or n.desde).isoformat(),
                                 "dias": ((n.hasta or n.desde) - n.desde).days + 1, "observacion": n.observacion or "",
                                 "creado_por": n.creado_por or ""} for n in filas]})


@novedades_bp.post("/api/cierres")
def api_cierres_guardar():
    from app.models.novedad_personal import NovedadPersonal
    usuario = _admin_cierres()
    d = request.get_json(silent=True) or {}
    tienda = db.session.get(Store, int(d.get("store_id") or 0))
    if not tienda:
        return jsonify({"ok": False, "error": "Elige la tienda"}), 400
    try:
        desde = date.fromisoformat(d.get("desde"))
        hasta = date.fromisoformat(d.get("hasta") or d.get("desde"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Revisa las fechas"}), 400
    if hasta < desde:
        return jsonify({"ok": False, "error": "El último día cerrada no puede ser antes del primero"}), 400
    n = db.session.get(NovedadPersonal, int(d["id"])) if d.get("id") else None
    if d.get("id") and (not n or n.tipo != "CIERRE_TIENDA"):
        abort(404)
    antes = (n.store_id, n.tipo, n.desde, n.hasta) if n else None
    if not n:
        n = NovedadPersonal(creado_por=usuario.correo, tipo="CIERRE_TIENDA")
        db.session.add(n)
    n.store_id, n.desde, n.hasta = tienda.id, desde, hasta
    n.horas = ((hasta - desde).days + 1) * HORAS_DIA
    n.observacion = (d.get("observacion") or "").strip()[:500] or None
    db.session.commit()
    _cuota_por_cierre(antes, (n.store_id, n.tipo, n.desde, n.hasta))
    return jsonify({"ok": True, "id": n.id})


@novedades_bp.delete("/api/cierres/<int:novedad_id>")
def api_cierres_borrar(novedad_id):
    from app.models.novedad_personal import NovedadPersonal
    _admin_cierres()
    n = db.session.get(NovedadPersonal, novedad_id)
    if not n or n.tipo != "CIERRE_TIENDA":
        abort(404)
    antes = (n.store_id, n.tipo, n.desde, n.hasta)
    db.session.delete(n)
    db.session.commit()
    _cuota_por_cierre(antes, None)
    return jsonify({"ok": True})


def _cuota_por_cierre(*estados):
    """«Cierre de tienda»: la cuota de esa tienda cuenta solo los días que vendió (se recalcula o se devuelve)."""
    from app.services import cierre_tienda_service
    tocar = set()
    for e in estados:
        if e and e[1] == cierre_tienda_service.TIPO:
            tocar.update((e[0], a, m) for a, m in cierre_tienda_service.meses(e[2], e[3]))
    for store_id, anio, mes in tocar:
        try:
            cierre_tienda_service.reajustar(store_id, anio, mes)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Novedades: no se pudo ajustar la cuota por el cierre de tienda")


# Presentaciones de Hilo «Horarios y novedades»: cada usuario la ve una sola vez
# (las tiendas una versión y la administración otra)
PRESENTACIONES = {
    "horarios-novedades": ("tiendas", "Horarios y novedades · versión para tiendas"),
    "horarios-novedades-admin": ("administracion", "Horarios y novedades · versión para administración"),
}


def _es_tienda(usuario):
    rol = usuario.role.nombre.strip().upper() if usuario and usuario.role and usuario.role.nombre else ""
    return rol == "TIENDA"


@novedades_bp.route("/api/presentacion/<clave>", methods=["GET", "POST"])
def api_presentacion(clave):
    from app.models.presentacion_vista import PresentacionVista, crear_tabla_si_falta
    if clave not in PRESENTACIONES or not session.get("user_id"):
        abort(404)
    usuario = db.session.get(User, session["user_id"])
    if not usuario or _es_tienda(usuario) != (PRESENTACIONES[clave][0] == "tiendas"):
        return jsonify({"ver": False})
    try:
        crear_tabla_si_falta()
        vista = PresentacionVista.query.filter_by(user_id=usuario.id, clave=clave).first()
        if request.method == "POST" and not vista:
            db.session.add(PresentacionVista(user_id=usuario.id, clave=clave))
            db.session.commit()
            return jsonify({"ok": True})
        return jsonify({"ver": vista is None, "ok": True})
    except Exception:
        db.session.rollback()
        return jsonify({"ver": False, "ok": False})


@novedades_bp.get("/api/presentaciones/vistos")
def api_presentaciones_vistos():
    """Para «Mensajes con Hilo»: quién ya vio cada presentación y a quién le falta (solo administradores)."""
    from app.models.presentacion_vista import PresentacionVista, crear_tabla_si_falta
    usuario = db.session.get(User, session["user_id"]) if session.get("user_id") else None
    rol = usuario.role.nombre.strip().upper() if usuario and usuario.role and usuario.role.nombre else ""
    if rol not in {"ADMIN", "ADMINISTRADOR"}:
        abort(403)
    try:
        crear_tabla_si_falta()
        vistas = {(v.user_id, v.clave): v.visto for v in PresentacionVista.query.all()}
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False})
    usuarios = User.query.filter(db.or_(User.activo.is_(True), User.activo.is_(None))).all()
    resultado = []
    for clave, (publico, titulo) in PRESENTACIONES.items():
        vieron, faltan = [], []
        for u in usuarios:
            if _es_tienda(u) != (publico == "tiendas"):
                continue
            fecha = vistas.get((u.id, clave))
            fila = {"usuario": u.nombre, "tienda": u.store.codigo if u.store else None,
                    "fecha": fecha.strftime("%d/%m %H:%M") if fecha else None}
            (vieron if (u.id, clave) in vistas else faltan).append(fila)
        orden = lambda x: (x["tienda"] or "zz", x["usuario"] or "")
        resultado.append({"clave": clave, "titulo": titulo, "publico": publico,
                          "vieron": sorted(vieron, key=orden), "faltan": sorted(faltan, key=orden)})
    return jsonify({"ok": True, "presentaciones": resultado})


def novedades_semana(store_id, desde, hasta):
    """Para la planilla de horas: las ausencias de la tienda que tocan esos días."""
    try:
        from app.models.novedad_personal import NovedadPersonal
        NovedadPersonal.__table__.create(bind=db.engine, checkfirst=True)
        return NovedadPersonal.query.filter(NovedadPersonal.store_id == store_id, NovedadPersonal.tipo.in_(sorted(AUSENCIA)),
                                            NovedadPersonal.desde <= hasta, NovedadPersonal.hasta >= desde).all()
    except Exception:
        db.session.rollback()
        return []
