"""Retos de la red: batallas de la semana, récords, remontadas, hora dorada, turnos,
batalla de asesoras, batalla de ciudades y salón de la fama. Solo lectura.

- Batalla de la semana: parejas de tiendas con meta parecida (de otra ciudad cuando se puede).
  Gana la que va más adelante en su meta de la semana (venta de lunes a hoy frente a la meta
  de esos mismos días). Todo en porcentaje: sin puntos.
  · La meta de cada día respeta cómo vende cada tienda según el día de la semana
    (una tienda fuerte el sábado no queda «perdiendo» el martes).
  · Las parejas rotan cada semana dentro de grupos de 4 tiendas de meta parecida.
  · Si el número de tiendas es impar, descansa una distinta cada semana.
  · La tienda virtual compite como una tienda más (su región es «Canal virtual»).
- Racha: batallas ganadas seguidas en las semanas ya terminadas.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
import math
import unicodedata

from sqlalchemy import func

from app.extensions import db
from app.models import AdvisorPerformance, Compliance, DailyStoreSales, Store
from app.services.hilo_inteligente_service import (
    MESES, _asesoras_al_corte, _compliance_corte, _con_cache, _excluir_tienda, _f, resolver_corte,
)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
SEMANAS_HISTORIA = 8
REGION_CIUDAD = {
    "bogota": "Centro", "chia": "Centro", "soacha": "Centro", "ibague": "Centro", "villavicencio": "Centro", "tunja": "Centro", "neiva": "Centro",
    "medellin": "Antioquia y Eje Cafetero", "envigado": "Antioquia y Eje Cafetero", "rionegro": "Antioquia y Eje Cafetero", "bello": "Antioquia y Eje Cafetero",
    "itagui": "Antioquia y Eje Cafetero", "pereira": "Antioquia y Eje Cafetero", "manizales": "Antioquia y Eje Cafetero", "armenia": "Antioquia y Eje Cafetero",
    "cali": "Pacífico", "palmira": "Pacífico", "pasto": "Pacífico", "popayan": "Pacífico",
    "barranquilla": "Caribe y Oriente", "cartagena": "Caribe y Oriente", "santa marta": "Caribe y Oriente", "valledupar": "Caribe y Oriente",
    "monteria": "Caribe y Oriente", "sincelejo": "Caribe y Oriente", "bucaramanga": "Caribe y Oriente", "cucuta": "Caribe y Oriente",
}


def _norm(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn").strip()


def _es_virtual(tienda):
    """Misma regla de «Mapa y resultados»: código S-03 o ciudad GLOBAL."""
    return _norm(tienda.codigo).replace(" ", "") == "s-03" or _norm(tienda.ciudad) == "global"


def _region(tienda):
    if _es_virtual(tienda):
        return "Canal virtual"
    region = getattr(tienda, "region", None)
    if region is not None and getattr(region, "nombre", None):
        return region.nombre
    return REGION_CIUDAD.get(_norm(tienda.ciudad), "Otras regiones")


def _meses_atras(anio, mes, n):
    lista = []
    for _ in range(n):
        lista.append((anio, mes))
        anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    return lista


# ==========================================================
# Datos base (una sola vez por corte, en caché)
# ==========================================================

def _base(anio, mes, dia_corte):
    fecha_corte = date(anio, mes, min(dia_corte or monthrange(anio, mes)[1], monthrange(anio, mes)[1]))
    actuales = _compliance_corte(anio, mes, dia_corte)
    tiendas = {sid: t for sid, (_, t) in actuales.items()}
    if not tiendas:
        return None
    # Cuota del mes por tienda: este mes al corte y los anteriores con su último registro activo
    meses = _meses_atras(anio, mes, 14)
    cuotas, tickets = {}, {}
    for (a, m) in meses[:4]:
        filas = actuales if (a, m) == (anio, mes) else _compliance_corte(a, m, None)
        for sid, (registro, tienda) in filas.items():
            if sid in tiendas:
                cuotas[(sid, a, m)] = _f(registro.cuota_total)
                if (a, m) == (anio, mes):
                    tickets[sid] = _f(registro.ticket_promedio)
    # Venta de cada día: la versión más reciente de cada día (hasta el corte en el mes actual)
    consulta = db.session.query(
        DailyStoreSales.store_id, DailyStoreSales.anio, DailyStoreSales.mes, DailyStoreSales.dia,
        DailyStoreSales.dia_corte, DailyStoreSales.venta,
    ).filter(DailyStoreSales.store_id.in_(list(tiendas)), DailyStoreSales.anio >= meses[-1][0])
    mejor = {}
    for sid, a, m, d, corte, venta in consulta.all():
        if (a, m) not in meses:
            continue
        try:
            fecha = date(int(a), int(m), int(d))
        except ValueError:
            continue
        if fecha > fecha_corte or ((a, m) == (anio, mes) and (corte or 0) > fecha_corte.day):
            continue
        clave = (sid, fecha)
        if clave not in mejor or (corte or 0) >= mejor[clave][0]:
            mejor[clave] = (corte or 0, _f(venta))
    ventas = defaultdict(dict)
    for (sid, fecha), (_, venta) in mejor.items():
        ventas[sid][fecha] = venta
    return {"anio": anio, "mes": mes, "fecha": fecha_corte, "tiendas": tiendas, "cuotas": cuotas,
            "tickets": tickets, "ventas": ventas, "actuales": actuales, "pesos": _pesos(ventas, fecha_corte)}


def _pesos(ventas, fecha_corte):
    """Cuánto vende cada tienda cada día de la semana frente a su promedio (8 semanas antes de esta)."""
    lunes = fecha_corte - timedelta(days=fecha_corte.weekday())
    desde = lunes - timedelta(days=56)
    pesos = {}
    for sid, dias in ventas.items():
        suma, cuenta = defaultdict(float), defaultdict(int)
        for f, v in dias.items():
            if desde <= f < lunes and v > 0:
                suma[f.weekday()] += v
                cuenta[f.weekday()] += 1
        if sum(cuenta.values()) < 28 or len(cuenta) < 7:
            continue  # poca historia: días iguales
        prom = {d: suma[d] / cuenta[d] for d in cuenta}
        general = sum(prom.values()) / 7
        pesos[sid] = {d: max(0.3, min(3.0, prom[d] / general)) for d in prom} if general > 0 else None
    return pesos


def _meta_dia(base, sid, fecha):
    """La meta del mes repartida según cómo vende la tienda cada día de la semana (si no hay historia, en partes iguales)."""
    cuota = base["cuotas"].get((sid, fecha.year, fecha.month))
    if not cuota:
        return None
    dias_mes = monthrange(fecha.year, fecha.month)[1]
    p = base["pesos"].get(sid)
    if not p:
        return cuota / dias_mes
    total = sum(p[date(fecha.year, fecha.month, d).weekday()] for d in range(1, dias_mes + 1))
    return cuota * p[fecha.weekday()] / total


def _avance(base, sid, desde, hasta):
    venta = meta = 0.0
    d = desde
    while d <= hasta:
        md = _meta_dia(base, sid, d)
        if md is None:
            return None
        meta += md
        venta += base["ventas"].get(sid, {}).get(d, 0.0)
        d += timedelta(days=1)
    if meta <= 0:
        return None
    return {"venta": round(venta), "meta": round(meta), "avance": venta / meta}


ROTACIONES = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
DIFERENCIA_MAXIMA = 1.6  # la meta de una no puede ser más de 1,6 veces la de la otra


def _emparejar(base, cuota_mes, lunes):
    """Parejas de meta parecida que cambian cada semana.

    Las tiendas se ordenan por meta y se agrupan de a 4; dentro de cada grupo las parejas rotan
    con el número de la semana. Se prefiere que no sean de la misma ciudad y que la meta de una
    no pase de 1,6 veces la de la otra. Si son impares, descansa una distinta cada semana.
    """
    cuota = lambda s: base["cuotas"][(s,) + cuota_mes]
    libres = sorted((sid for sid in base["tiendas"] if base["cuotas"].get((sid,) + cuota_mes)), key=lambda s: (-cuota(s), s))
    semana = lunes.isocalendar()[1] + lunes.isocalendar()[0] * 53
    descansa = None
    if len(libres) % 2:
        descansa = libres.pop(semana % len(libres))
    misma = lambda a, b: _norm(base["tiendas"][a].ciudad) == _norm(base["tiendas"][b].ciudad)
    parejo = lambda a, b: max(cuota(a), cuota(b)) / min(cuota(a), cuota(b)) <= DIFERENCIA_MAXIMA
    parejas = []
    for i in range(0, len(libres), 4):
        grupo = libres[i:i + 4]
        if len(grupo) == 2:
            parejas.append(tuple(grupo))
            continue
        opciones = [ROTACIONES[(semana + k) % 3] for k in range(3)]
        def nota(rot):
            pares = [(grupo[x], grupo[y]) for x, y in rot]
            return (sum(not parejo(a, b) for a, b in pares), sum(misma(a, b) for a, b in pares))
        elegida = min(opciones, key=nota)  # min conserva el orden: la rotación de la semana gana los empates
        parejas.extend((grupo[x], grupo[y]) for x, y in elegida)
    return parejas, descansa


def _semana(base, lunes, hasta):
    """Batallas de una semana (de lunes a «hasta»)."""
    mes_ref = (hasta.year, hasta.month)
    parejas, descansa = _emparejar(base, mes_ref, lunes)
    resultado = []
    for a, b in parejas:
        ra, rb = _avance(base, a, lunes, hasta), _avance(base, b, lunes, hasta)
        if not ra or not rb:
            continue
        diferencia = ra["avance"] - rb["avance"]
        gana = None if abs(diferencia) < 0.0005 else (a if diferencia > 0 else b)
        resultado.append({"a": a, "b": b, "ra": ra, "rb": rb, "gana": gana})
    return {"desde": lunes, "hasta": hasta, "parejas": resultado, "descansa": descansa}


def _historia(base):
    """Semanas terminadas (de la más reciente a la más antigua) con su ganadora por pareja."""
    lunes_actual = base["fecha"] - timedelta(days=base["fecha"].weekday())
    semanas = []
    for k in range(1, SEMANAS_HISTORIA + 1):
        lunes = lunes_actual - timedelta(days=7 * k)
        domingo = lunes + timedelta(days=6)
        hay = any(base["ventas"].get(sid, {}).get(domingo) is not None for sid in base["tiendas"])
        if not hay:
            break
        semanas.append(_semana(base, lunes, domingo))
    return semanas


def _rachas(semanas):
    rachas, victorias_mes, cortada = defaultdict(int), defaultdict(int), set()
    for i, s in enumerate(semanas):
        for p in s["parejas"]:
            for sid in (p["a"], p["b"]):
                if sid in cortada:
                    continue
                if p["gana"] == sid:
                    rachas[sid] += 1
                else:
                    cortada.add(sid)
    return rachas


def _resumen(base, sid, r):
    t = base["tiendas"][sid]
    return {"id": sid, "nombre": t.nombre, "codigo": t.codigo, "ciudad": t.ciudad, "venta": r["venta"], "meta": r["meta"], "avance": round(r["avance"], 4)}


# ==========================================================
# Batallas de la red
# ==========================================================

def _batallas(base):
    hoy = base["fecha"]
    lunes = hoy - timedelta(days=hoy.weekday())
    actual = _semana(base, lunes, hoy)
    historia = _historia(base)
    rachas = _rachas(historia)
    victorias_mes = defaultdict(int)
    for s in historia:
        if (s["hasta"].year, s["hasta"].month) == (base["anio"], base["mes"]):
            for p in s["parejas"]:
                if p["gana"]:
                    victorias_mes[p["gana"]] += 1
    ultima = historia[0] if historia else None
    ganadoras_ultima = {p["gana"] for p in ultima["parejas"] if p["gana"]} if ultima else set()
    parejas = []
    for p in actual["parejas"]:
        parejas.append({
            "a": _resumen(base, p["a"], p["ra"]), "b": _resumen(base, p["b"], p["rb"]),
            "gana": p["gana"],
        })
    # Batalla de ciudades y regiones: todas sus tiendas suman venta y meta de la semana
    grupos = {"region": defaultdict(lambda: [0.0, 0.0, 0]), "ciudad": defaultdict(lambda: [0.0, 0.0, 0])}
    for sid, t in base["tiendas"].items():
        r = _avance(base, sid, lunes, hoy)
        if not r:
            continue
        for clave, nombre in (("region", _region(t)), ("ciudad", "Tienda virtual" if _es_virtual(t) else t.ciudad or "Sin ciudad")):
            g = grupos[clave][nombre]
            g[0] += r["venta"]; g[1] += r["meta"]; g[2] += 1
    equipos = {
        clave: sorted(({"nombre": n, "avance": round(v[0] / v[1], 4) if v[1] else None, "tiendas": v[2], "venta": round(v[0])}
                       for n, v in g.items()), key=lambda x: -(x["avance"] or 0))
        for clave, g in grupos.items()
    }
    return {
        "semana": {"desde": lunes.isoformat(), "hasta": hoy.isoformat(), "dia": DIAS[hoy.weekday()], "dias": (hoy - lunes).days + 1},
        "parejas": parejas,
        "descansa": base["tiendas"][actual["descansa"]].nombre if actual["descansa"] else None,
        "rachas": {sid: n for sid, n in rachas.items() if n},
        "victorias_mes": dict(victorias_mes),
        "ganadoras_semana_pasada": sorted(ganadoras_ultima),
        "semana_pasada": {"desde": ultima["desde"].isoformat(), "hasta": ultima["hasta"].isoformat()} if ultima else None,
        "equipos": equipos,
        "historia": [
            {"desde": s["desde"].isoformat(), "hasta": s["hasta"].isoformat(),
             "parejas": [{"a": base["tiendas"][p["a"]].nombre, "b": base["tiendas"][p["b"]].nombre,
                          "aa": round(p["ra"]["avance"], 4), "ab": round(p["rb"]["avance"], 4),
                          "gana": base["tiendas"][p["gana"]].nombre if p["gana"] else None} for p in s["parejas"]]}
            for s in historia[:4]
        ],
    }


# ==========================================================
# Récords y remontadas
# ==========================================================

def _records(base, sid):
    dias = base["ventas"].get(sid, {})
    if not dias:
        return None
    hoy = base["fecha"]
    pasado = {f: v for f, v in dias.items() if f < hoy}
    mejor_dia = max(pasado.items(), key=lambda x: x[1]) if pasado else None
    # Semanas completas (lunes a domingo) anteriores a la actual
    semanas = defaultdict(float)
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    for f, v in dias.items():
        lunes = f - timedelta(days=f.weekday())
        semanas[lunes] += v
    actual_semana = semanas.pop(lunes_actual, 0.0)
    completas = {l: v for l, v in semanas.items() if all((l + timedelta(days=i)) in dias for i in range(7))}
    mejor_semana = max(completas.items(), key=lambda x: x[1]) if completas else None
    # Meses completos anteriores
    meses = defaultdict(float)
    for f, v in dias.items():
        meses[(f.year, f.month)] += v
    actual_mes = meses.pop((hoy.year, hoy.month), 0.0)
    completos = {k: v for k, v in meses.items() if sum(1 for f in dias if (f.year, f.month) == k) >= monthrange(*k)[1] - 1}
    mejor_mes = max(completos.items(), key=lambda x: x[1]) if completos else None
    ritmo_mes = actual_mes / hoy.day * monthrange(hoy.year, hoy.month)[1] if hoy.day else 0
    hoy_venta = dias.get(hoy, 0.0)

    def estado(actual, record):
        if not record:
            return None
        return "roto" if actual > record else "cerca" if actual >= record * 0.9 else None

    return {
        "dia": {"valor": round(mejor_dia[1]), "fecha": mejor_dia[0].isoformat(), "hoy": round(hoy_venta), "estado": estado(hoy_venta, mejor_dia[1])} if mejor_dia else None,
        "semana": {"valor": round(mejor_semana[1]), "desde": mejor_semana[0].isoformat(), "actual": round(actual_semana), "estado": estado(actual_semana, mejor_semana[1])} if mejor_semana else None,
        "mes": {"valor": round(mejor_mes[1]), "mes": MESES[mejor_mes[0][1] - 1], "anio": mejor_mes[0][0], "ritmo": round(ritmo_mes), "estado": "camino" if ritmo_mes > mejor_mes[1] else "cerca" if ritmo_mes >= mejor_mes[1] * 0.95 else None} if mejor_mes else None,
    }


def _series_mes(anio, mes, dia_corte, store_ids=None):
    sub = db.session.query(
        Compliance.store_id.label("store_id"), Compliance.dia_corte.label("dia_corte"), func.max(Compliance.id).label("max_id"),
    ).filter(Compliance.anio == anio, Compliance.mes == mes, Compliance.dia_corte.isnot(None))
    if dia_corte is not None:
        sub = sub.filter(Compliance.dia_corte <= dia_corte)
    if store_ids:
        sub = sub.filter(Compliance.store_id.in_(list(store_ids)))
    sub = sub.group_by(Compliance.store_id, Compliance.dia_corte).subquery()
    filas = db.session.query(Compliance.store_id, Compliance.dia_corte, Compliance.cumplimiento_pct).join(sub, Compliance.id == sub.c.max_id).all()
    series = defaultdict(list)
    for sid, corte, cump in filas:
        series[sid].append((int(corte), _f(cump)))
    for s in series.values():
        s.sort()
    return series


def _remontada(serie):
    """Pasó de menos de 90 % en un corte anterior a más de su meta en el último."""
    if len(serie) < 2 or serie[-1][1] < 1:
        return None
    previos = [x for x in serie[:-1] if x[1] < 0.9]
    if not previos:
        return None
    bajo = min(previos, key=lambda x: x[1])
    return {"desde": round(bajo[1], 4), "dia_desde": bajo[0], "hasta": round(serie[-1][1], 4), "dia": serie[-1][0]}


# ==========================================================
# Hora dorada, turnos, asesoras y visitas (por tienda)
# ==========================================================

def _hora_dorada(sid, fecha):
    try:
        from app.models.trafico_horario import TraficoHorario
        filas = db.session.query(TraficoHorario.hora, func.sum(TraficoHorario.trafico), func.sum(TraficoHorario.facturas)).filter(
            TraficoHorario.store_id == sid, TraficoHorario.fecha > fecha - timedelta(days=28), TraficoHorario.fecha <= fecha,
            TraficoHorario.sensor_error.is_(False),
        ).group_by(TraficoHorario.hora).all()
    except Exception:
        db.session.rollback()
        return None
    horas = {int(h): (_f(t), _f(f)) for h, t, f in filas if h is not None}
    if sum(t for t, _ in horas.values()) <= 0:
        return None
    lista = [{"h": h, "trafico": round(horas[h][0]), "facturas": round(horas[h][1])} for h in sorted(horas)]
    ventanas = [(h, horas[h][0] + horas.get(h + 1, (0, 0))[0], horas[h][1] + horas.get(h + 1, (0, 0))[1]) for h in sorted(horas)]
    pico = max(ventanas, key=lambda x: x[1])
    dorada = max(ventanas, key=lambda x: x[2])
    total_t = sum(t for t, _ in horas.values())
    con_gente = [h for h in horas if horas[h][0] >= total_t * 0.06]
    conv = {h: horas[h][1] / horas[h][0] for h in con_gente if horas[h][0] > 0}
    floja = min(conv, key=conv.get) if conv else None
    mejor = max(conv, key=conv.get) if conv else None
    return {
        "horas": lista, "dorada": dorada[0], "pico": pico[0],
        "mejor_conversion": {"h": mejor, "valor": round(conv[mejor], 4)} if mejor is not None else None,
        "floja": {"h": floja, "valor": round(conv[floja], 4), "trafico": round(horas[floja][0])} if floja is not None else None,
        "conversion": round(sum(f for _, f in horas.values()) / total_t, 4),
        "dias": 28,
    }


def _turnos(sid, fecha, dorada):
    try:
        from app.models.cuadrante import CuadranteAsignacion
        filas = db.session.query(CuadranteAsignacion.fecha, CuadranteAsignacion.turno, func.count(CuadranteAsignacion.id)).filter(
            CuadranteAsignacion.store_id == sid, CuadranteAsignacion.fecha > fecha, CuadranteAsignacion.fecha <= fecha + timedelta(days=7),
        ).group_by(CuadranteAsignacion.fecha, CuadranteAsignacion.turno).all()
    except Exception:
        db.session.rollback()
        return None
    if not filas:
        return {"hay": False}
    por_dia = defaultdict(lambda: {"APERTURA": 0, "CIERRE": 0})
    for f, turno, n in filas:
        t = (turno or "").upper()
        if t in ("APERTURA", "CIERRE"):
            por_dia[f][t] += int(n)
    clave = "CIERRE" if dorada is None or dorada >= 14 else "APERTURA"
    otro = "APERTURA" if clave == "CIERRE" else "CIERRE"
    dias = []
    for f in sorted(por_dia):
        c = por_dia[f]
        dias.append({"fecha": f.isoformat(), "dia": DIAS[f.weekday()], "apertura": c["APERTURA"], "cierre": c["CIERRE"],
                     "corto": c[clave] < c[otro] or c[clave] <= 1})
    return {"hay": True, "turno_clave": clave.lower(), "dias": dias}


def _asesoras_semana(sid, anio, mes, corte):
    try:
        cortes = sorted({int(c) for (c,) in db.session.query(AdvisorPerformance.dia_corte).filter(
            AdvisorPerformance.store_id == sid, AdvisorPerformance.anio == anio, AdvisorPerformance.mes == mes,
            AdvisorPerformance.dia_corte.isnot(None), AdvisorPerformance.dia_corte <= corte).distinct()})
        if not cortes:
            return None
        actual = cortes[-1]
        previo = cortes[-2] if len(cortes) > 1 else 0
        hoy, _ = _asesoras_al_corte(sid, anio, mes, actual)
        antes = {a["id"]: a["venta"] for a in _asesoras_al_corte(sid, anio, mes, previo)[0]} if previo else {}
    except Exception:
        db.session.rollback()
        return None
    dias_mes = monthrange(anio, mes)[1]
    dias = actual - previo
    lista = []
    for a in hoy:
        if a["generico"] or not a["meta"] or dias <= 0:
            continue
        venta = a["venta"] - antes.get(a["id"], 0)
        meta = a["meta"] * dias / dias_mes
        lista.append({"nombre": a["nombre"].title(), "venta": round(venta), "avance": round(venta / meta, 4) if meta else None})
    lista.sort(key=lambda x: -(x["avance"] or 0))
    return {"desde": previo + 1, "hasta": actual, "asesoras": lista}


def _pendientes_visita(sid):
    try:
        from app.models import ChecklistVisita
        v = ChecklistVisita.query.filter(ChecklistVisita.store_id == sid).order_by(ChecklistVisita.fecha_visita.desc(), ChecklistVisita.id.desc()).first()
    except Exception:
        db.session.rollback()
        return None
    if not v or not isinstance(v.respuestas, dict):
        return None
    items = []
    for categoria, valores in v.respuestas.items():
        if categoria.startswith("__") or not isinstance(valores, dict):
            continue
        for item, datos in valores.items():
            if isinstance(datos, dict) and str(datos.get("cumple", "")).lower() == "no":
                items.append({"categoria": categoria, "item": item, "obs": datos.get("obs") or ""})
    return {"fecha": v.fecha_visita.isoformat() if v.fecha_visita else None, "items": items}


# ==========================================================
# Salón de la fama (último mes cerrado)
# ==========================================================

def _salon(anio, mes):
    from app.routes.ranking import _ranking_asesoras
    a, m = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    cierre = _compliance_corte(a, m, None)
    if not cierre:
        return None
    dia_cierre = max(int(r.dia_corte or 0) for r, _ in cierre.values())
    campeona = max(cierre.values(), key=lambda x: _f(x[0].cumplimiento_pct))
    series = _series_mes(a, m, None, cierre.keys())
    subidas = []
    for sid, s in series.items():
        if len(s) >= 2 and sid in cierre:
            subidas.append((s[-1][1] - s[0][1], sid, s[0][1], s[-1][1]))
    subida = max(subidas) if subidas else None
    asesora = None
    try:
        pa, pm = (a - 1, 12) if m == 1 else (a, m - 1)
        previo = _compliance_corte(pa, pm, None)
        dia_previo = max(int(r.dia_corte or 0) for r, _ in previo.values()) if previo else None
        ahora = {(x["advisor_id"], x["store_id"]): x for x in _ranking_asesoras(a, m, dia_cierre, None, None) if not x["sin_meta"]}
        antes = {(x["advisor_id"], x["store_id"]): x for x in _ranking_asesoras(pa, pm, dia_previo, None, None) if not x["sin_meta"]} if dia_previo else {}
        mejoras = [(ahora[k]["cumplimiento"] - antes[k]["cumplimiento"], ahora[k]) for k in ahora if k in antes and "VENDEDOR UNICO" not in (ahora[k]["asesora"] or "").upper()]
        if mejoras:
            d, x = max(mejoras, key=lambda y: y[0])
            asesora = {"nombre": (x["asesora"] or "").title(), "tienda": x["tienda"], "cump": round(x["cumplimiento"], 4), "subio": round(d, 4)}
    except Exception:
        db.session.rollback()
    en_meta = sum(1 for r, _ in cierre.values() if _f(r.cumplimiento_pct) >= 1)
    return {
        "mes": MESES[m - 1], "anio": a, "dia": dia_cierre, "en_meta": en_meta, "total": len(cierre),
        "campeona": {"nombre": campeona[1].nombre, "ciudad": campeona[1].ciudad, "cump": round(_f(campeona[0].cumplimiento_pct), 4)},
        "remontada": {"nombre": cierre[subida[1]][1].nombre, "desde": round(subida[2], 4), "hasta": round(subida[3], 4)} if subida and subida[0] > 0 else None,
        "asesora": asesora,
    }


# ==========================================================
# API
# ==========================================================

def red(anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte)
    if not anio or not mes:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("retos_red", anio, mes, dia_corte), lambda: _red(anio, mes, dia_corte))


def _red(anio, mes, dia_corte):
    base = _base(anio, mes, dia_corte)
    if not base:
        return {"ok": False, "motivo": "sin_datos"}
    batallas = _batallas(base)
    series = _series_mes(anio, mes, dia_corte, base["tiendas"].keys())
    remontadas = []
    for sid, s in series.items():
        r = _remontada(s)
        if r and sid in base["tiendas"]:
            remontadas.append(dict(r, nombre=base["tiendas"][sid].nombre, id=sid))
    records = []
    for sid, t in base["tiendas"].items():
        r = _records(base, sid)
        if not r:
            continue
        for tipo in ("dia", "semana", "mes"):
            if r.get(tipo) and r[tipo]["estado"]:
                records.append({"id": sid, "nombre": t.nombre, "tipo": tipo, "estado": r[tipo]["estado"]})
    try:
        salon = _salon(anio, mes)
    except Exception:
        db.session.rollback()
        salon = None
    return {"ok": True, "corte": {"anio": anio, "mes": mes, "dia": base["fecha"].day, "nombre_mes": MESES[mes - 1]},
            "batallas": batallas, "remontadas": remontadas, "records": records, "salon": salon}


def tienda(store_id, anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte, store_id)
    if not anio or not mes or not store_id:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("retos_tienda", store_id, anio, mes, dia_corte), lambda: _tienda(store_id, anio, mes, dia_corte))


def _tienda(store_id, anio, mes, dia_corte):
    general = red(anio, mes, dia_corte)
    base = _base(anio, mes, dia_corte)
    if not general.get("ok") or not base or store_id not in base["tiendas"]:
        return {"ok": False, "motivo": "sin_datos"}
    b = general["batallas"]
    mia = None
    for p in b["parejas"]:
        if store_id in (p["a"]["id"], p["b"]["id"]):
            yo, rival = (p["a"], p["b"]) if p["a"]["id"] == store_id else (p["b"], p["a"])
            falta = max(rival["avance"] * yo["meta"] - yo["venta"], 0) if rival["avance"] > yo["avance"] else 0
            ticket = base["tickets"].get(store_id) or 0
            mia = {"yo": yo, "rival": rival, "gana": p["gana"], "falta": round(falta),
                   "facturas": int(-(-falta // ticket)) if falta and ticket else 0,
                   "racha": b["rachas"].get(store_id, 0), "racha_rival": b["rachas"].get(rival["id"], 0),
                   "victorias_mes": b["victorias_mes"].get(store_id, 0),
                   "gano_semana_pasada": store_id in b["ganadoras_semana_pasada"]}
    # Sus batallas de las semanas anteriores (para «Mis trofeos»)
    nombre = base["tiendas"][store_id].nombre
    semanas = []
    for s in b["historia"]:
        for p in s["parejas"]:
            if nombre in (p["a"], p["b"]):
                yo_a = p["a"] == nombre
                semanas.append({"desde": s["desde"], "hasta": s["hasta"], "rival": p["b"] if yo_a else p["a"],
                                "yo": p["aa"] if yo_a else p["ab"], "otra": p["ab"] if yo_a else p["aa"],
                                "resultado": "gano" if p["gana"] == nombre else "empate" if not p["gana"] else "perdio"})
    serie = _series_mes(anio, mes, dia_corte, [store_id]).get(store_id, [])
    hora = _hora_dorada(store_id, base["fecha"])
    return {
        "ok": True, "corte": general["corte"], "semana": b["semana"], "batalla": mia, "descansa": b["descansa"] == base["tiendas"][store_id].nombre,
        "records": _records(base, store_id), "remontada": _remontada(serie),
        "hora_dorada": hora, "turnos": _turnos(store_id, base["fecha"], hora["dorada"] if hora else None),
        "asesoras": _asesoras_semana(store_id, anio, mes, base["fecha"].day),
        "visita": _pendientes_visita(store_id),
        "tienda": {"id": store_id, "nombre": base["tiendas"][store_id].nombre, "ciudad": base["tiendas"][store_id].ciudad},
        "semanas": semanas,
        "venta_semana": _avance(base, store_id, base["fecha"] - timedelta(days=base["fecha"].weekday()), base["fecha"]),
    }
