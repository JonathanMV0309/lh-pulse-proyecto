"""
Hilo inteligente · API de solo lectura, Modo TV e informe semanal.

- GET  /api/hilo/tienda                  datos de la tienda para Hilo (tienda o admin con ?store_id=)
- GET  /api/hilo/admin                   resumen de la red para Hilo (solo administradores)
- POST /api/hilo/admin/mensaje           enviar un mensaje con Hilo desde el panel (solo administradores)
- GET  /api/hilo/admin/mensajes/vistos   quién vio cada mensaje (solo administradores)
- GET  /hilo/tv                          Modo TV de la tienda (pantalla grande)
- GET  /hilo/reporte-semanal             informe semanal para gerencia (imprimible / PDF)
- GET  /hilo/reporte-semanal.xlsx        el mismo informe en Excel
"""
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file, session

from app.extensions import db
from app.models.store import Store
from app.models.user import User
from app.services import hilo_inteligente_service as servicio


hilo_inteligente_bp = Blueprint("hilo_inteligente", __name__)

ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}
ROLES_TIENDA = {"TIENDA"}


def _usuario():
    usuario = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not usuario or usuario.activo is False:
        abort(401)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    return usuario, rol


def _solo_admin():
    usuario, rol = _usuario()
    if rol not in ROLES_ADMIN:
        abort(403)
    return usuario


def _corte():
    return (
        request.args.get("anio", type=int),
        request.args.get("mes", type=int),
        request.args.get("dia_corte", type=int),
    )


def _tienda_permitida(usuario, rol):
    if rol in ROLES_TIENDA:
        return usuario.store_id
    if rol in ROLES_ADMIN:
        return request.args.get("store_id", type=int)
    return None


# ==========================================================
# API
# ==========================================================

@hilo_inteligente_bp.get("/api/hilo/tienda")
def api_tienda():
    usuario, rol = _usuario()
    store_id = _tienda_permitida(usuario, rol)
    if not store_id:
        return jsonify({"ok": False, "motivo": "sin_tienda"})
    anio, mes, dia_corte = _corte()
    try:
        return jsonify(servicio.datos_tienda(store_id, anio, mes, dia_corte))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Hilo: no se pudieron calcular los datos de la tienda %s", store_id)
        return jsonify({"ok": False, "motivo": "error"})


@hilo_inteligente_bp.get("/api/hilo/admin")
def api_admin():
    _solo_admin()
    anio, mes, dia_corte = _corte()
    try:
        return jsonify(servicio.datos_admin(anio, mes, dia_corte))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Hilo: no se pudo calcular el resumen de la red")
        return jsonify({"ok": False, "motivo": "error"})


@hilo_inteligente_bp.get("/api/hilo/admin/red")
def api_red():
    """El hilo que une la red: día en que cada tienda pasó su meta (modo del mapa)."""
    _solo_admin()
    anio, mes, dia_corte = _corte()
    periodo = request.args.get("periodo") or ""
    partes = periodo.split("-")
    if len(partes) == 3 and partes[0].isdigit() and partes[1].isdigit():
        anio, mes = int(partes[0]), int(partes[1])
        dia_corte = int(partes[2]) if partes[2].isdigit() else None
    try:
        return jsonify(servicio.red_tejida(anio, mes, dia_corte))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Hilo: no se pudo armar el hilo de la red")
        return jsonify({"ok": False, "motivo": "error"})


@hilo_inteligente_bp.post("/api/hilo/admin/mensaje")
def api_enviar_mensaje():
    from app.models.mensaje_hilo import MensajeHilo
    from app.routes.mensajes_hilo import LARGO_MAXIMO, TONOS

    admin = _solo_admin()
    datos = request.get_json(silent=True) or {}
    texto = " ".join(str(datos.get("texto") or "").split())[:LARGO_MAXIMO]
    tono = datos.get("tono") if datos.get("tono") in TONOS else "anima"
    ids = sorted({int(t) for t in (datos.get("tiendas") or []) if str(t).isdigit()})
    validas = {t.id for t in Store.query.filter(Store.id.in_(ids)).all()} if ids else set()
    ids = [i for i in ids if i in validas]
    try:
        dias = max(1, min(int(datos.get("dias") or 3), 30))
    except (TypeError, ValueError):
        dias = 3
    if not texto:
        return jsonify({"ok": False, "error": "Escribe el mensaje."}), 400
    hoy = date.today()
    mensaje = MensajeHilo(
        texto=texto, tono=tono,
        destino="seleccion" if ids else "todas",
        tiendas=",".join(str(i) for i in ids) if ids else None,
        desde=hoy, hasta=hoy + timedelta(days=dias - 1), creado_por=admin.id,
    )
    db.session.add(mensaje)
    db.session.commit()
    return jsonify({"ok": True, "id": mensaje.id})


@hilo_inteligente_bp.get("/api/hilo/admin/mensajes/vistos")
def api_vistos():
    _solo_admin()
    try:
        return jsonify({"ok": True, "mensajes": servicio.vistos_mensajes()})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Hilo: no se pudo leer quién vio los mensajes")
        return jsonify({"ok": False, "mensajes": []})


# ==========================================================
# MODO TV
# ==========================================================

@hilo_inteligente_bp.get("/hilo/tv")
def modo_tv():
    usuario, rol = _usuario()
    store_id = _tienda_permitida(usuario, rol)
    if rol not in ROLES_TIENDA | ROLES_ADMIN:
        abort(403)
    tiendas = []
    if rol in ROLES_ADMIN:
        tiendas = Store.query.filter_by(estado="ACTIVA").order_by(Store.codigo).all()
    tienda = db.session.get(Store, store_id) if store_id else None
    return render_template("hilo/modo_tv.html", tienda=tienda, tiendas=tiendas, es_admin=rol in ROLES_ADMIN)


# ==========================================================
# INFORME SEMANAL
# ==========================================================

def _pct(valor, decimales=1):
    return "—" if valor is None else f"{valor * 100:.{decimales}f} %".replace(".", ",")


def _signo(valor):
    return "—" if valor is None else ("+" if valor >= 0 else "") + _pct(valor)


@hilo_inteligente_bp.get("/hilo/reporte-semanal")
def reporte_semanal():
    _solo_admin()
    anio, mes, dia_corte = _corte()
    datos = servicio.datos_admin(anio, mes, dia_corte)
    if not datos.get("ok"):
        abort(404)
    return render_template(
        "hilo/reporte_semanal.html", d=datos, pct=_pct, signo=_signo,
        generado=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


@hilo_inteligente_bp.get("/hilo/reporte-semanal.xlsx")
def reporte_semanal_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    _solo_admin()
    anio, mes, dia_corte = _corte()
    d = servicio.datos_admin(anio, mes, dia_corte)
    if not d.get("ok"):
        abort(404)
    corte, red = d["corte"], d["red"]

    libro = Workbook()
    titulo = Font(bold=True, size=14, color="2D2A26")
    cabeza = Font(bold=True, color="FFFFFF")
    fondo = PatternFill("solid", fgColor="8B7D6B")
    dinero = '"$"#,##0'
    porcentaje = "0.0%"

    def hoja(nombre, encabezados, filas, formatos=None, primera=False):
        h = libro.active if primera else libro.create_sheet()
        h.title = nombre
        h.append(encabezados)
        for celda in h[1]:
            celda.font, celda.fill = cabeza, fondo
            celda.alignment = Alignment(vertical="center")
        for fila in filas:
            h.append(fila)
        for i, ancho in enumerate(max(len(str(c.value or "")) for c in col) for col in h.columns):
            h.column_dimensions[get_column_letter(i + 1)].width = min(max(ancho + 2, 10), 60)
        for col, formato in (formatos or {}).items():
            for celda in h[col][1:]:
                celda.number_format = formato
        h.freeze_panes = "A2"
        return h

    resumen = libro.active
    resumen.title = "Resumen"
    resumen["A1"] = f"L&H Pulse · Informe semanal · {corte['nombre_mes'].capitalize()} {corte['anio']} (corte día {corte['dia']})"
    resumen["A1"].font = titulo
    filas = [
        ("Venta de la red", red["venta"], dinero),
        ("Venta año anterior", red["venta_anterior"], dinero),
        ("Crecimiento", red.get("crecimiento"), porcentaje),
        ("Cumplimiento al corte", red["cump"], porcentaje),
        ("Meta del mes", red["cuota_total"], dinero),
        ("Cierre proyectado", red["proyeccion"], dinero),
        ("Cierre proyectado (% de la meta)", red["proy_pct"], porcentaje),
        ("Tiendas al día con la meta", f"{red['al_dia']} de {red['tiendas']}", None),
        (f"Venta últimos 7 días ({d['semana'].get('desde', '')}–{d['semana'].get('hasta', '')})", d["semana"].get("actual"), dinero),
        ("Frente a los 7 días anteriores", d["semana"].get("variacion"), porcentaje),
    ]
    if d.get("red_tejida"):
        rt = d["red_tejida"]
        filas.append(("Red tejida: tiendas que pasaron su meta", f"{rt['unidas']} de {rt['total']}", None))
        if rt.get("hace_una_semana") is not None:
            filas.append(("Red tejida hace una semana", f"{rt['hace_una_semana']} de {rt['total']}", None))
    for i, (nombre, valor, formato) in enumerate(filas, start=3):
        resumen.cell(row=i, column=1, value=nombre).font = Font(bold=True)
        celda = resumen.cell(row=i, column=2, value=valor)
        if formato:
            celda.number_format = formato
    resumen.column_dimensions["A"].width = 48
    resumen.column_dimensions["B"].width = 22

    hoja("Tiendas",
         ["Código", "Tienda", "Clima", "Venta", "Año anterior", "Crecimiento", "Cumplimiento", "Meta del mes", "Cierre proyectado", "% proyectado", "Necesita por día"],
         [[t["codigo"], t["nombre"], t["clima"], t["venta"], t["venta_anterior"], t["crecimiento"], t["cump"], t["cuota_total"], t["proy_valor"], t["proy_pct"], t["necesita_dia"]] for t in d["tiendas"]],
         {"D": dinero, "E": dinero, "F": porcentaje, "G": porcentaje, "H": dinero, "I": dinero, "J": porcentaje, "K": dinero})
    hoja("Semana",
         ["Código", "Tienda", "Últimos 7 días", "7 días anteriores", "Variación"],
         [[t["codigo"], t["nombre"], t["actual"], t["previa"], t["variacion"]] for t in d["semana"].get("tiendas", [])],
         {"C": dinero, "D": dinero, "E": porcentaje})
    causas = {"trafico": "Tráfico", "conversion": "Conversión", "ticket": "Tiquete", None: "Sin dato del año anterior"}
    hoja("Diagnóstico",
         ["Código", "Tienda", "Crecimiento", "Tráfico", "Conversión", "Tiquete", "Causa principal"],
         [[x["codigo"], x["nombre"], x["crecimiento"], x.get("trafico"), x.get("conversion"), x.get("ticket"), causas.get(x.get("causa"), "")] for x in d["diagnostico"]],
         {"C": porcentaje, "D": porcentaje, "E": porcentaje, "F": porcentaje})
    hoja("Calidad de datos", ["Nivel", "Qué pasa", "Detalle", "Tiendas"],
         [[a["nivel"], a["titulo"], a["detalle"], ", ".join(a.get("tiendas") or [])] for a in d["calidad"]])
    hoja("Uso de L&H Pulse", ["Código", "Tienda", "Último ingreso", "Días sin entrar"],
         [[x["codigo"], x["nombre"], x["ultimo"] or "Sin ingresos registrados", x["dias"]] for x in d["sin_uso"].get("tiendas", [])])
    if d.get("v3"):
        hoja("Pronóstico V3",
             ["Código", "Tienda", "V3 (P50)", "Cierre al ritmo actual", "Diferencia", "Fuera del rango"],
             [[x["codigo"], x["nombre"], x["p50"], x["proyeccion"], x["diferencia"], x["fuera"] or ""] for x in d["v3"]["tiendas"]],
             {"C": dinero, "D": dinero, "E": porcentaje})
    if d["cambios"]:
        hoja("Cambios bruscos",
             ["Código", "Tienda", "Día", "Venta", "Promedio mismo día", "Variación"],
             [[x["codigo"], x["nombre"], f"{x['nombre_dia']} {x['dia']}", x["venta"], x["promedio"], x["variacion"]] for x in d["cambios"]],
             {"D": dinero, "E": dinero, "F": porcentaje})

    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    nombre = f"LH_Pulse_informe_semanal_{corte['anio']}-{corte['mes']:02d}-{corte['dia']:02d}.xlsx"
    return send_file(salida, as_attachment=True, download_name=nombre,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
