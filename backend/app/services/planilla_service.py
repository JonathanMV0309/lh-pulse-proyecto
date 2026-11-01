"""Planilla de horas del equipo (formato GTH-ODSCTD-003 «Calendario de descansos y turnos de trabajo»).

- Horas trabajadas del día = salida − entrada − 1 hora de almuerzo (igual que el Excel). Si la persona
  no almorzó (casilla «Almorzó» sin marcar) se cuentan todas las horas.
- Semana de domingo a sábado, como el formato.
- Alertas: más de 42 horas en la semana (necesita autorización de Talento Humano), sin día de
  descanso, administradora que no está de apertura a cierre en quincena o cierre de mes, y días
  en que nadie abre o nadie cierra la tienda.
- Si un día no tiene horas guardadas se sugieren con el turno arrastrado (apertura / cierre /
  descanso) y el horario de la tienda.
- La planilla es la principal: al guardarla se llenan solos los «Turnos de la semana» de esos días
  (quien abre, quien cierra y quien descansa), para no hacer doble trabajo.
"""
import io
import json
import os
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models.cuadrante import CuadranteAsignacion
from app.models.cuadrante_horas import CuadranteHoras, CuadrantePersonaDato, CuadranteSemanaObs, CuadranteSinAlmuerzo, HorarioTienda

HORAS_SEMANA = 42
NOVEDADES = ["TRABAJA", "DESCANSO", "VACACIONES", "PERMISO", "INCAPACIDAD", "CALAMIDAD", "LICENCIA"]
CARGOS = ["Administradora", "Subadministradora", "Segunda", "Asesora", "Auxiliar", "Asesora volante"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
LETRAS = ["L", "M", "W", "J", "V", "S", "D"]   # W = miércoles (en el formato también aparece «X»)
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DATOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "horarios_tiendas.json")


# ==========================================================
# Festivos de Colombia (Ley Emiliani)
# ==========================================================

def _pascua(anio):
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _lunes_siguiente(f):
    return f + timedelta(days=(7 - f.weekday()) % 7)


def festivos(anio):
    p = _pascua(anio)
    fijos = [date(anio, 1, 1), date(anio, 5, 1), date(anio, 7, 20), date(anio, 8, 7), date(anio, 12, 8), date(anio, 12, 25)]
    trasladables = [date(anio, 1, 6), date(anio, 3, 19), date(anio, 6, 29), date(anio, 8, 15), date(anio, 10, 12), date(anio, 11, 1), date(anio, 11, 11)]
    pascua = [p - timedelta(days=3), p - timedelta(days=2)]   # jueves y viernes santo
    moviles = [p + timedelta(days=43), p + timedelta(days=64), p + timedelta(days=71)]  # Ascensión, Corpus, Sagrado Corazón (ya en lunes)
    return set(fijos + pascua + moviles + [_lunes_siguiente(f) for f in trasladables])


# ==========================================================
# Horario de la tienda
# ==========================================================

def _defecto(store):
    try:
        datos = json.load(open(DATOS, encoding="utf-8"))["tiendas"]
    except Exception:
        return []
    codigo = (store.codigo or "").replace(" ", "").upper()
    return (datos.get(codigo) or {}).get("horarios", [])


def horario(store):
    filas = HorarioTienda.query.filter_by(store_id=store.id).order_by(HorarioTienda.orden, HorarioTienda.id).all()
    if filas:
        return [{"dias": f.dias, "apertura": f.apertura, "cierre": f.cierre} for f in filas], "tienda"
    return _defecto(store), "formato"


def guardar_horario(store, filas):
    HorarioTienda.query.filter_by(store_id=store.id).delete()
    for i, f in enumerate(filas):
        if _hora(f.get("apertura")) and _hora(f.get("cierre")) and f.get("dias"):
            db.session.add(HorarioTienda(store_id=store.id, dias=str(f["dias"]).upper().replace(" ", "")[:10],
                                         apertura=_hora(f["apertura"]), cierre=_hora(f["cierre"]), orden=i))
    db.session.commit()


def _incluye(rango, fecha, es_festivo):
    """«L-S», «D-F», «V-S», «L-J», «S», «F»… ¿aplica a este día?"""
    rango = rango.upper().replace("X", "W").replace(" ", "")
    if es_festivo:
        return "F" in rango
    letra = LETRAS[fecha.weekday()]
    partes = rango.split("-")
    if len(partes) == 2 and partes[0] in LETRAS and partes[1] in LETRAS:
        a, b = LETRAS.index(partes[0]), LETRAS.index(partes[1])
        return a <= LETRAS.index(letra) <= b
    return letra in partes


def horario_del_dia(filas, fecha, es_festivo):
    if es_festivo:
        for f in filas:
            if "F" in f["dias"].upper():
                return f
        fecha = fecha + timedelta(days=6 - fecha.weekday())   # sin fila de festivos: el horario del domingo
    for f in filas:
        if _incluye(f["dias"], fecha, False):
            return f
    return None


# ==========================================================
# Horas
# ==========================================================

def _hora(valor):
    if valor is None:
        return None
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    texto = str(valor).strip().replace(".", ":")
    if not texto:
        return None
    try:
        partes = texto.split(":")
        h, m = int(partes[0]), int(partes[1]) if len(partes) > 1 and partes[1] else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None


def _min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def horas_trabajadas(entrada, salida, almuerzo=True):
    """Igual que el formato: (salida − entrada) − 1 hora de almuerzo; sin almuerzo, todas las horas."""
    if not entrada or not salida:
        return 0.0
    duracion = (_min(salida) - _min(entrada)) / 60
    return max(round(duracion - (1 if almuerzo else 0), 2), 0.0) if duracion > 0 else 0.0


def _sumar(hhmm, minutos):
    t = max(0, min(_min(hhmm) + minutos, 23 * 60 + 59))
    return f"{t // 60:02d}:{t % 60:02d}"


def _hora_en_punto(hhmm, arriba):
    h, m = _min(hhmm) // 60, _min(hhmm) % 60
    if m and arriba:
        h = min(h + 1, 23)
    return f"{h:02d}:00"


def _sugerencia(turno, h):
    """Horas sugeridas a partir del turno arrastrado y el horario de la tienda: jornada de 7 h + 1 h de
    almuerzo (como 10:00 a 18:00 o 12:00 a 20:00 en el formato), así 6 días suman las 42 h de la semana."""
    if turno == "DESCANSO":
        return {"entrada": None, "salida": None, "novedad": "DESCANSO"}
    if not h:
        return None
    # En horas en punto, como las anotan las tiendas (abre 10:30 -> entra a las 10:00)
    apertura, cierre = _hora_en_punto(h["apertura"], arriba=False), _hora_en_punto(h["cierre"], arriba=True)
    if turno == "APERTURA":
        salida = min(_sumar(apertura, 8 * 60), cierre, key=_min)
        return {"entrada": apertura, "salida": salida, "novedad": "TRABAJA"}
    if turno == "CIERRE":
        entrada = max(_sumar(cierre, -8 * 60), apertura, key=_min)
        return {"entrada": entrada, "salida": cierre, "novedad": "TRABAJA"}
    return None


# ==========================================================
# Planilla de una semana
# ==========================================================

def domingo_de(fecha):
    return fecha - timedelta(days=(fecha.weekday() + 1) % 7)


def _cargo(persona, datos):
    if datos and datos.cargo:
        return datos.cargo
    tipo = (persona.tipo or "").upper()
    return "Administradora" if tipo == "ADMINISTRADORA" else "Asesora"


def planilla(store, personas, domingo):
    dias = [domingo + timedelta(days=i) for i in range(7)]
    fest = festivos(domingo.year) | festivos((domingo + timedelta(days=6)).year)
    filas_horario, origen = horario(store)
    horario_dia = {d: horario_del_dia(filas_horario, d, d in fest) for d in dias}
    ids = [p.id for p in personas]
    guardadas = {(h.persona_id, h.fecha): h for h in CuadranteHoras.query.filter(
        CuadranteHoras.persona_id.in_(ids or [0]), CuadranteHoras.fecha >= dias[0], CuadranteHoras.fecha <= dias[-1])}
    turnos = {(a.persona_id, a.fecha): a.turno for a in CuadranteAsignacion.query.filter(
        CuadranteAsignacion.store_id == store.id, CuadranteAsignacion.fecha >= dias[0], CuadranteAsignacion.fecha <= dias[-1])}
    obs = {o.persona_id: o.texto for o in CuadranteSemanaObs.query.filter(
        CuadranteSemanaObs.persona_id.in_(ids or [0]), CuadranteSemanaObs.semana == domingo)}
    datos = {d.persona_id: d for d in CuadrantePersonaDato.query.filter(CuadrantePersonaDato.persona_id.in_(ids or [0]))}
    sin_almuerzo = {(s.persona_id, s.fecha) for s in CuadranteSinAlmuerzo.query.filter(
        CuadranteSinAlmuerzo.persona_id.in_(ids or [0]), CuadranteSinAlmuerzo.fecha >= dias[0], CuadranteSinAlmuerzo.fecha <= dias[-1])}
    from app.routes.novedades import NOMBRE_TIPO, novedades_semana
    novedades = novedades_semana(store.id, dias[0], dias[-1])

    filas = []
    for p in personas:
        celdas, total, descansa = [], 0.0, False
        for d in dias:
            g = guardadas.get((p.id, d))
            th = _novedad_de(p, d, novedades)
            if g:
                celda = {"entrada": g.entrada, "salida": g.salida, "novedad": g.novedad or "TRABAJA", "observacion": g.observacion or "", "sugerido": False}
            elif th and not _parcial(th):   # Talento Humano registró una ausencia: el día sale marcado
                celda = {"entrada": None, "salida": None, "novedad": NOVEDAD_PLANILLA.get(th.tipo, "LICENCIA"), "observacion": "", "sugerido": True}
            else:
                s = _sugerencia((turnos.get((p.id, d)) or "").upper(), horario_dia[d])
                celda = dict(s, observacion="", sugerido=True) if s else {"entrada": None, "salida": None, "novedad": "TRABAJA", "observacion": "", "sugerido": False}
            celda["th"] = (NOMBRE_TIPO.get(th.tipo, th.tipo) + (f" ({th.horas:g} h)".replace(".", ",") if _parcial(th) else "")) if th else None
            celda["th_completo"] = bool(th) and not _parcial(th)
            celda["fecha"] = d.isoformat()
            celda["almuerzo"] = (p.id, d) not in sin_almuerzo
            celda["horas"] = horas_trabajadas(celda["entrada"], celda["salida"], celda["almuerzo"]) if celda["novedad"] == "TRABAJA" else 0.0
            total += celda["horas"]
            descansa = descansa or celda["novedad"] != "TRABAJA" or not celda["entrada"]
            celdas.append(celda)
        dato = datos.get(p.id)
        filas.append({"persona_id": p.id, "nombre": p.nombre, "cargo": _cargo(p, dato), "cedula": dato.cedula if dato and dato.cedula else "",
                      "manual": not p.advisor_id and (p.tipo or "").upper() != "ADMINISTRADORA",
                      "celdas": celdas, "total": round(total, 2), "observacion": obs.get(p.id) or "", "descansa": descansa})
    return {
        "domingo": domingo.isoformat(),
        "dias": [{"fecha": d.isoformat(), "nombre": DIAS[d.weekday()], "festivo": d in fest,
                  "quincena": d.day == 15 or d.day == monthrange(d.year, d.month)[1],
                  "horario": horario_dia[d]} for d in dias],
        "horario": filas_horario, "horario_origen": origen,
        "filas": filas, "alertas": alertas(filas, [horario_dia[d] for d in dias], dias),
        "cargos": CARGOS, "novedades": NOVEDADES, "limite": HORAS_SEMANA,
    }


# Novedades de Talento Humano -> novedad de la planilla
NOVEDAD_PLANILLA = {"VACACIONES": "VACACIONES", "INCAPACIDAD": "INCAPACIDAD", "LICENCIA_MATERNIDAD": "LICENCIA",
                    "LICENCIA_LUTO": "LICENCIA", "LICENCIA_NO_REMUNERADA": "LICENCIA", "PERMISO_ESPECIAL": "PERMISO",
                    "CALAMIDAD": "CALAMIDAD", "CIERRE_TIENDA": "DESCANSO"}


def _parcial(n):
    """Una novedad de pocas horas (como un permiso de 3 h) no ocupa el día completo."""
    from app.routes.novedades import HORAS_DIA
    return n.horas is not None and n.horas < ((n.hasta - n.desde).days + 1) * HORAS_DIA


def _novedad_de(persona, dia, novedades):
    for n in novedades:
        if not (n.desde <= dia <= n.hasta):
            continue
        if n.tipo == "CIERRE_TIENDA" and not n.nombre:
            return n
        if n.advisor_id and n.advisor_id == persona.advisor_id:
            return n
        if not n.advisor_id and (n.cargo or "").lower() == "administradora" and (persona.tipo or "").upper() == "ADMINISTRADORA":
            return n
        if not n.advisor_id and not persona.advisor_id and n.nombre and n.nombre.strip().lower() == (persona.nombre or "").strip().lower():
            return n   # persona creada por Talento Humano en «Novedades»
    return None


def alertas(filas, horarios, dias):
    lista = []
    for f in filas:
        choques = {}
        for c in f["celdas"]:
            if c.get("th_completo") and c["novedad"] == "TRABAJA" and c["entrada"]:
                dd = date.fromisoformat(c["fecha"])
                choques.setdefault(c["th"], []).append(f"{DIAS[dd.weekday()].lower()} {dd.day}")
        for th, dias_txt in choques.items():
            cuando = dias_txt[0] if len(dias_txt) == 1 else ", ".join(dias_txt[:-1]) + " y " + dias_txt[-1]
            lista.append({"nivel": "media", "texto": f"Talento Humano registró «{th.lower()}» para {f['nombre']} el {cuando}, pero en la planilla aparece trabajando."})
        if f["total"] > HORAS_SEMANA:
            lista.append({"nivel": "alta", "texto": f"{f['nombre']}: {_txt(f['total'])} h en la semana. Más de {HORAS_SEMANA} h necesita autorización previa de la Directora de Talento Humano."})
        trabaja = [c for c in f["celdas"] if c["novedad"] == "TRABAJA" and c["entrada"]]
        if len(trabaja) == 7:
            lista.append({"nivel": "media", "texto": f"{f['nombre']} no tiene día de descanso esta semana."})
    for i, d in enumerate(dias):
        h = horarios[i]
        trabajan = [(f, f["celdas"][i]) for f in filas if f["celdas"][i]["novedad"] == "TRABAJA" and f["celdas"][i]["entrada"] and f["celdas"][i]["salida"]]
        nombre = f"el {DIAS[d.weekday()].lower()} {d.day}"
        if h and trabajan:
            if not any(_min(c["entrada"]) <= _min(h["apertura"]) for _, c in trabajan):
                lista.append({"nivel": "media", "texto": f"Nadie abre la tienda {nombre} (abre a las {h['apertura']})."})
            if not any(_min(c["salida"]) >= _min(h["cierre"]) for _, c in trabajan):
                lista.append({"nivel": "media", "texto": f"Nadie cierra la tienda {nombre} (cierra a las {h['cierre']})."})
        if h and (d.day == 15 or d.day == monthrange(d.year, d.month)[1]):
            admin = [f for f in filas if f["cargo"] == "Administradora"]
            for f in admin:
                c = f["celdas"][i]
                if not (c["novedad"] == "TRABAJA" and c["entrada"] and c["salida"] and _min(c["entrada"]) <= _min(h["apertura"]) and _min(c["salida"]) >= _min(h["cierre"])):
                    motivo = "quincena" if d.day == 15 else "cierre de mes"
                    quien = "la administradora" if f["nombre"].strip().lower() == "administradora" else f"la administradora ({f['nombre']})"
                    lista.append({"nivel": "media", "texto": f"{nombre.capitalize()} es {motivo}: {quien} debe estar de apertura a cierre ({h['apertura']} a {h['cierre']})."})
    return lista


def _txt(horas):
    return f"{horas:g}".replace(".", ",")


def guardar(store, personas, domingo, datos):
    validas = {p.id for p in personas}
    dias = {(domingo + timedelta(days=i)).isoformat() for i in range(7)}
    for fila in datos.get("filas", []):
        pid = int(fila.get("persona_id") or 0)
        if pid not in validas:
            raise ValueError("Hay personas que no son de esta tienda")
        for c in fila.get("celdas", []):
            if c.get("fecha") not in dias:
                continue
            f = date.fromisoformat(c["fecha"])
            novedad = str(c.get("novedad") or "TRABAJA").upper()
            novedad = novedad if novedad in NOVEDADES else "TRABAJA"
            entrada, salida = _hora(c.get("entrada")), _hora(c.get("salida"))
            if novedad != "TRABAJA":
                entrada = salida = None
            if entrada and salida and _min(salida) <= _min(entrada):
                raise ValueError(f"La salida debe ser después de la entrada ({fila.get('nombre', '')}, {f.day}/{f.month})")
            sin = CuadranteSinAlmuerzo.query.filter_by(persona_id=pid, fecha=f).first()
            if novedad == "TRABAJA" and c.get("almuerzo") is False:
                if not sin:
                    db.session.add(CuadranteSinAlmuerzo(store_id=store.id, persona_id=pid, fecha=f))
            elif sin:
                db.session.delete(sin)
            fila_bd = CuadranteHoras.query.filter_by(persona_id=pid, fecha=f).first()
            vacia = novedad == "TRABAJA" and not entrada and not salida and not (c.get("observacion") or "").strip()
            if vacia:
                if fila_bd:
                    db.session.delete(fila_bd)
                continue
            if not fila_bd:
                fila_bd = CuadranteHoras(store_id=store.id, persona_id=pid, fecha=f)
                db.session.add(fila_bd)
            fila_bd.entrada, fila_bd.salida, fila_bd.novedad = entrada, salida, novedad
            fila_bd.observacion = (c.get("observacion") or "").strip()[:200] or None
        texto = (fila.get("observacion") or "").strip()[:300]
        o = CuadranteSemanaObs.query.filter_by(persona_id=pid, semana=domingo).first()
        if texto:
            if not o:
                o = CuadranteSemanaObs(store_id=store.id, persona_id=pid, semana=domingo)
                db.session.add(o)
            o.texto = texto
        elif o:
            db.session.delete(o)
        cargo, cedula = (fila.get("cargo") or "").strip(), "".join(ch for ch in str(fila.get("cedula") or "") if ch.isdigit())[:20]
        dato = db.session.get(CuadrantePersonaDato, pid) or CuadrantePersonaDato(persona_id=pid)
        dato.cargo = cargo if cargo in CARGOS else None
        dato.cedula = cedula or None
        db.session.add(dato)
    _llenar_turnos(store, domingo, datos.get("filas", []), validas)
    db.session.commit()


def turnos_de(entrada, salida, h):
    """Turnos del tablero de arrastrar según las horas: APERTURA, CIERRE o los dos (apertura a cierre)."""
    if not h:
        return ["APERTURA"] if _min(entrada) < 13 * 60 else ["CIERRE"]
    abre, cierra = _min(entrada) <= _min(h["apertura"]), _min(salida) >= _min(h["cierre"])
    if abre or cierra:
        return (["APERTURA"] if abre else []) + (["CIERRE"] if cierra else [])
    # Turno intermedio: al que quede más cerca
    return ["APERTURA"] if _min(entrada) - _min(h["apertura"]) <= _min(h["cierre"]) - _min(salida) else ["CIERRE"]


def _llenar_turnos(store, domingo, filas, validas):
    """Pasa la planilla guardada a «Turnos de la semana»: solo las personas y los días de esta planilla."""
    dias = [domingo + timedelta(days=i) for i in range(7)]
    fest = festivos(domingo.year) | festivos(dias[-1].year)
    filas_horario, _ = horario(store)
    ids = [int(f.get("persona_id") or 0) for f in filas if int(f.get("persona_id") or 0) in validas]
    if not ids:
        return
    CuadranteAsignacion.query.filter(CuadranteAsignacion.store_id == store.id, CuadranteAsignacion.persona_id.in_(ids),
                                     CuadranteAsignacion.fecha >= dias[0], CuadranteAsignacion.fecha <= dias[-1]).delete(synchronize_session=False)
    orden = {}
    for fila in filas:
        pid = int(fila.get("persona_id") or 0)
        if pid not in validas:
            continue
        for c in fila.get("celdas", []):
            try:
                f = date.fromisoformat(c.get("fecha") or "")
            except ValueError:
                continue
            if not dias[0] <= f <= dias[-1]:
                continue
            novedad = str(c.get("novedad") or "TRABAJA").upper()
            entrada, salida = _hora(c.get("entrada")), _hora(c.get("salida"))
            if novedad != "TRABAJA":
                turnos = ["DESCANSO"]
            elif entrada and salida and _min(salida) > _min(entrada):
                turnos = turnos_de(entrada, salida, horario_del_dia(filas_horario, f, f in fest))
            else:
                continue   # sin horas: ese día no se pone en ningún turno
            for t in turnos:
                orden[(f, t)] = orden.get((f, t), -1) + 1
                db.session.add(CuadranteAsignacion(store_id=store.id, persona_id=pid, fecha=f, turno=t, orden=orden[(f, t)]))


# ==========================================================
# Excel del mes con el formato de Talento Humano
# ==========================================================

def exportar_mes(store, personas, anio, mes):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = MESES[mes - 1]
    negrita = Font(bold=True)
    titulo = Font(bold=True, size=14)
    fondo = PatternFill("solid", fgColor="F2E6D3")
    descanso = PatternFill("solid", fgColor="E7E0D6")
    fino = Side(style="thin", color="B8AC9A")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    centro = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws["A1"] = "CALENDARIO DE DESCANSOS Y TURNOS DE TRABAJO"; ws["A1"].font = titulo
    ws["A2"] = "CÓDIGO: GTH - ODSCTD - 003"
    ws["A4"] = "Punto de Venta"; ws["C4"] = f"{(store.codigo or '').replace('-', '')}-{store.nombre}"
    ws["A5"] = "Mes"; ws["C5"] = MESES[mes - 1]; ws["E5"] = "Año"; ws["F5"] = anio
    ws["A6"] = "Periodo"; ws["C6"] = f"Del 01/{mes:02d}/{anio} al {monthrange(anio, mes)[1]}/{mes:02d}/{anio}"
    for celda in ("A4", "A5", "A6", "E5"):
        ws[celda].font = negrita
    ws["A8"] = "Horario de apertura"; ws["A8"].font = negrita
    filas_horario, _ = horario(store)
    for i, h in enumerate(filas_horario):
        ws.cell(row=9 + i, column=1, value=h["dias"]); ws.cell(row=9 + i, column=2, value=f"{h['apertura']} a {h['cierre']}")
    notas = [
        "Cada colaborador deberá descansar en las fechas pactadas y acordadas previamente por el equipo de trabajo.",
        "42 horas semanales; en caso de exceder las horas deberá ser autorizado previamente con la Directora de TTHH.",
        "Se tiene en cuenta la jornada diaria trabajada descontando la hora de almuerzo (si no almorzó, se cuentan todas las horas).",
        "En observaciones se diligencia si la persona está en vacaciones, tuvo un permiso, una incapacidad o calamidad.",
        "Los días de quincena y cierre de mes la administradora debe estar de apertura a cierre.",
    ]
    ws["P8"] = "Importante"; ws["P8"].font = negrita
    for i, n in enumerate(notas):
        ws.cell(row=9 + i, column=16, value=n)

    fila = 16
    domingo = domingo_de(date(anio, mes, 1))
    ultimo = date(anio, mes, monthrange(anio, mes)[1])
    semana = 1
    while domingo <= ultimo:
        datos = planilla(store, personas, domingo)
        ws.cell(row=fila, column=4, value=f"SEMANA {semana}").font = negrita
        fila += 1
        ws.cell(row=fila, column=1, value="Cargo"); ws.cell(row=fila, column=2, value="Cédula"); ws.cell(row=fila, column=3, value="Nombre completo")
        for i, d in enumerate(datos["dias"]):
            col = 4 + i * 3
            f = date.fromisoformat(d["fecha"])
            ws.cell(row=fila, column=col, value=f"{d['nombre']} {f.day:02d}/{f.month:02d}" + (" (festivo)" if d["festivo"] else ""))
            ws.merge_cells(start_row=fila, start_column=col, end_row=fila, end_column=col + 2)
            for j, t in enumerate(["Apertura", "Cierre", "THT"]):
                ws.cell(row=fila + 1, column=col + j, value=t)
        ws.cell(row=fila, column=25, value="Horas trabajadas por semana"); ws.cell(row=fila, column=26, value="Observaciones")
        for r in (fila, fila + 1):
            for c in range(1, 27):
                ws.cell(row=r, column=c).font = negrita; ws.cell(row=r, column=c).fill = fondo
                ws.cell(row=r, column=c).alignment = centro; ws.cell(row=r, column=c).border = borde
        fila += 2
        for p in datos["filas"]:
            ws.cell(row=fila, column=1, value=p["cargo"]); ws.cell(row=fila, column=2, value=p["cedula"] or None); ws.cell(row=fila, column=3, value=p["nombre"])
            thts = []
            for i, c in enumerate(p["celdas"]):
                col = 4 + i * 3
                f = date.fromisoformat(c["fecha"])
                fuera = f.month != mes
                if c["novedad"] == "TRABAJA" and c["entrada"] and c["salida"] and not c.get("sugerido"):
                    ws.cell(row=fila, column=col, value=time.fromisoformat(c["entrada"])).number_format = "hh:mm"
                    ws.cell(row=fila, column=col + 1, value=time.fromisoformat(c["salida"])).number_format = "hh:mm"
                else:
                    ws.cell(row=fila, column=col, value=0); ws.cell(row=fila, column=col + 1, value=0)
                    if c["novedad"] != "TRABAJA":
                        ws.cell(row=fila, column=col, value=c["novedad"].capitalize())
                        for j in range(3):
                            ws.cell(row=fila, column=col + j).fill = descanso
                a, b = get_column_letter(col), get_column_letter(col + 1)
                almuerzo = 1 if c.get("almuerzo", True) else 0
                ws.cell(row=fila, column=col + 2, value=f'=IF(OR(NOT(ISNUMBER({a}{fila})),NOT(ISNUMBER({b}{fila}))),0,IF(({a}{fila}+{b}{fila})=0,0,(({b}{fila}-{a}{fila})*24)-{almuerzo}))')
                thts.append(f"{get_column_letter(col + 2)}{fila}")
                if fuera:
                    for j in range(3):
                        ws.cell(row=fila, column=col + j).font = Font(color="9A8F80")
            ws.cell(row=fila, column=25, value="=" + "+".join(thts)).font = negrita
            obs = [p["observacion"]] + [f"{date.fromisoformat(c['fecha']).day}/{date.fromisoformat(c['fecha']).month}: {c['observacion']}" for c in p["celdas"] if c["observacion"]]
            obs += [f"{date.fromisoformat(c['fecha']).day}/{date.fromisoformat(c['fecha']).month}: no almorzó" for c in p["celdas"]
                    if not c.get("almuerzo", True) and c["novedad"] == "TRABAJA" and c["entrada"] and not c.get("sugerido")]
            ws.cell(row=fila, column=26, value=" · ".join(o for o in obs if o) or None)
            for c in range(1, 27):
                ws.cell(row=fila, column=c).border = borde
                ws.cell(row=fila, column=c).alignment = Alignment(horizontal="center" if 3 < c < 26 else "left", vertical="center", wrap_text=c == 26)
            fila += 1
        fila += 1
        domingo += timedelta(days=7)
        semana += 1
    ws.column_dimensions["A"].width = 16; ws.column_dimensions["B"].width = 13; ws.column_dimensions["C"].width = 26
    for c in range(4, 25):
        ws.column_dimensions[get_column_letter(c)].width = 8.5
    ws.column_dimensions["Y"].width = 12; ws.column_dimensions["Z"].width = 40; ws.column_dimensions["P"].width = 9
    salida = io.BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida
