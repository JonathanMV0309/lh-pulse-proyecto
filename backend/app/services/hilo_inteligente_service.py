"""
Hilo inteligente · cálculos de solo lectura para la mascota de L&H Pulse.

Nada de aquí escribe en la base ni cambia los cálculos del dashboard: solo lee
cumplimiento, ventas diarias, conversión, tráfico por hora, metas de asesoras,
registro de accesos y el pronóstico V3 para que Hilo pueda:

- Tienda: proyectar el cierre del mes y armar el plan por día, revisar la meta
  distribuible, entrenar la conversión, celebrar récords y rachas, y comparar la
  tienda con las de su mismo clima.
- Administración: resumen de la red, diagnóstico de causas frente al año
  anterior, tiendas que no entran, calidad de datos, a quién felicitar,
  pronóstico V3 frente a lo real, cambios bruscos y mensajes sugeridos.

Todo funciona igual en PostgreSQL y en SQLite (solo ORM; el pronóstico V3 usa
SQL simple en una conexión aparte para no afectar la sesión si sus tablas no
existen).
"""
import math
import time
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, text

from app.extensions import db
from app.models import (
    Advisor,
    AdvisorGoal,
    AdvisorPerformance,
    Compliance,
    ConversionDiaria,
    DailyStoreSales,
    Store,
    User,
)

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
CONVERSION_META = 0.20

_CACHE = {}
_CACHE_SEGUNDOS = 300


# ==========================================================
# Utilidades
# ==========================================================

def _f(valor):
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        return 0.0
    return numero if math.isfinite(numero) else 0.0


def _con_cache(clave, calcular):
    ahora = time.monotonic()
    guardado = _CACHE.get(clave)
    if guardado and ahora - guardado[0] < _CACHE_SEGUNDOS:
        return guardado[1]
    valor = calcular()
    if len(_CACHE) > 300:
        _CACHE.clear()
    _CACHE[clave] = (ahora, valor)
    return valor


def _excluir_tienda(tienda, anio, mes):
    if not tienda:
        return True
    if (tienda.nombre or "").strip().upper() == "TOTAL" or (tienda.codigo or "").strip().upper() == "TOTA":
        return True
    if (tienda.estado or "ACTIVA").upper() != "ACTIVA":
        return True
    return (anio, mes) >= (2026, 8) and (tienda.codigo or "").strip().upper() == "S-24"


def resolver_corte(anio=None, mes=None, dia_corte=None, store_id=None):
    """Mismo corte que usa el dashboard (si no se pide uno, el último cargado)."""
    from app.services.dashboard_service import _obtener_corte_actual
    return _obtener_corte_actual(anio=anio, mes=mes, dia_corte=dia_corte, store_id=store_id)


def _compliance_corte(anio, mes, dia_corte, store_id=None):
    """{store_id: (Compliance, Store)} con la última versión de cada tienda en ese corte."""
    def consulta(filtro_corte):
        sub = db.session.query(
            Compliance.store_id.label("store_id"),
            func.max(Compliance.id).label("max_id"),
        ).filter(Compliance.anio == anio, Compliance.mes == mes, filtro_corte)
        if store_id:
            sub = sub.filter(Compliance.store_id == store_id)
        sub = sub.group_by(Compliance.store_id).subquery()
        return (
            db.session.query(Compliance, Store)
            .join(sub, Compliance.id == sub.c.max_id)
            .join(Store, Store.id == Compliance.store_id)
            .all()
        )

    filas = consulta(Compliance.dia_corte == dia_corte) if dia_corte is not None else []
    if not filas:
        filas = consulta(Compliance.activo.is_(True))
    return {
        registro.store_id: (registro, tienda)
        for registro, tienda in filas
        if not _excluir_tienda(tienda, anio, mes)
    }


def _ventas_por_dia(anio, mes, hasta_dia, store_ids=None):
    """{store_id: {dia: venta}} tomando, para cada día, la versión más reciente hasta el corte."""
    if not anio or not mes:
        return {}
    consulta = db.session.query(
        DailyStoreSales.store_id, DailyStoreSales.dia, DailyStoreSales.dia_corte, DailyStoreSales.venta,
    ).filter(DailyStoreSales.anio == anio, DailyStoreSales.mes == mes)
    if hasta_dia:
        consulta = consulta.filter(DailyStoreSales.dia <= hasta_dia, DailyStoreSales.dia_corte <= hasta_dia)
    if store_ids:
        consulta = consulta.filter(DailyStoreSales.store_id.in_(list(store_ids)))
    mejor = {}
    for store_id, dia, corte, venta in consulta.all():
        clave = (store_id, int(dia))
        if clave not in mejor or (corte or 0) >= mejor[clave][0]:
            mejor[clave] = (corte or 0, _f(venta))
    resultado = defaultdict(dict)
    for (store_id, dia), (_, venta) in mejor.items():
        resultado[store_id][dia] = venta
    return resultado


def _conversion_por_dia(anio, mes, hasta_dia, store_ids=None):
    """{store_id: {dia: (trafico, facturas)}} con la versión más reciente de cada día."""
    if not anio or not mes:
        return {}
    consulta = db.session.query(
        ConversionDiaria.store_id, ConversionDiaria.dia, ConversionDiaria.dia_corte, ConversionDiaria.id,
        ConversionDiaria.trafico, ConversionDiaria.facturas,
    ).filter(ConversionDiaria.anio == anio, ConversionDiaria.mes == mes)
    if hasta_dia:
        consulta = consulta.filter(ConversionDiaria.dia <= hasta_dia)
    if store_ids:
        consulta = consulta.filter(ConversionDiaria.store_id.in_(list(store_ids)))
    mejor = {}
    for store_id, dia, corte, ident, trafico, facturas in consulta.all():
        clave = (store_id, int(dia))
        orden = (corte or 0, ident or 0)
        if clave not in mejor or orden >= mejor[clave][0]:
            mejor[clave] = (orden, (int(trafico or 0), int(facturas or 0)))
    resultado = defaultdict(dict)
    for (store_id, dia), (_, valores) in mejor.items():
        resultado[store_id][dia] = valores
    return resultado


def _pesos_semana(ventas_dia, anio, mes):
    """Peso de cada día de la semana según cómo vende la tienda (1 = día promedio)."""
    por_dia = defaultdict(list)
    for dia, venta in ventas_dia.items():
        if venta > 0:
            por_dia[date(anio, mes, dia).weekday()].append(venta)
    todas = [v for lista in por_dia.values() for v in lista]
    if len(todas) < 5:
        return {d: 1.0 for d in range(7)}
    promedio = sum(todas) / len(todas)
    pesos = {}
    for d in range(7):
        lista = por_dia.get(d)
        pesos[d] = (sum(lista) / len(lista)) / promedio if lista and promedio > 0 else 1.0
    return pesos


def proyectar(venta, cuota_total, ventas_dia, anio, mes, dia_corte):
    """Cierre esperado si la tienda sigue a su ritmo, respetando cómo vende cada día de la semana."""
    dias_mes = monthrange(anio, mes)[1]
    dia_corte = min(int(dia_corte or 0), dias_mes)
    cerrado = dia_corte >= dias_mes
    if dia_corte <= 0:
        return None
    pesos = _pesos_semana(ventas_dia, anio, mes)
    peso_corrido = sum(pesos[date(anio, mes, d).weekday()] for d in range(1, dia_corte + 1)) or dia_corte
    venta_dia_base = venta / peso_corrido if peso_corrido else 0
    restantes = list(range(dia_corte + 1, dias_mes + 1))
    peso_restante = sum(pesos[date(anio, mes, d).weekday()] for d in restantes)
    valor = venta + venta_dia_base * peso_restante
    falta = max(cuota_total - venta, 0)
    plan = []
    for d in restantes[:7]:
        peso = pesos[date(anio, mes, d).weekday()]
        plan.append({
            "dia": d,
            "nombre": DIAS_SEMANA[date(anio, mes, d).weekday()],
            "valor": round(falta * peso / peso_restante) if peso_restante else 0,
            "ritmo": round(venta_dia_base * peso),
        })
    escenarios = []
    for objetivo in (0.9, 1.0, 1.1):
        necesita = max(cuota_total * objetivo - venta, 0)
        escenarios.append({
            "pct": objetivo,
            "por_dia": round(necesita / len(restantes)) if restantes else 0,
            "logrado": necesita <= 0,
        })
    return {
        "valor": round(valor),
        "pct": (valor / cuota_total) if cuota_total > 0 else None,
        "cerrado": cerrado,
        "dias_mes": dias_mes,
        "dias_restantes": len(restantes),
        "ritmo_dia": round(venta / dia_corte),
        "necesita_dia": round(falta / len(restantes)) if restantes else 0,
        "falta": round(falta),
        "plan": plan,
        "escenarios": escenarios,
        "metodo": "semana" if any(abs(p - 1) > 0.01 for p in pesos.values()) else "promedio",
    }


# ==========================================================
# TIENDA
# ==========================================================

def _asesoras_al_corte(store_id, anio, mes, dia_corte):
    """Venta de cada asesora al corte y su meta del mes (la misma distribución de Metas y vendedores)."""
    from app.services.advisor_goal_service import calcular_metas_asesoras, obtener_meta_tienda

    sub = db.session.query(
        AdvisorPerformance.advisor_id.label("advisor_id"),
        func.max(AdvisorPerformance.id).label("max_id"),
    ).filter(
        AdvisorPerformance.store_id == store_id,
        AdvisorPerformance.anio == anio,
        AdvisorPerformance.mes == mes,
    )
    sub = sub.filter(AdvisorPerformance.dia_corte == dia_corte) if dia_corte is not None else sub.filter(AdvisorPerformance.activo.is_(True))
    sub = sub.group_by(AdvisorPerformance.advisor_id).subquery()
    filas = (
        db.session.query(AdvisorPerformance, Advisor)
        .join(sub, AdvisorPerformance.id == sub.c.max_id)
        .join(Advisor, Advisor.id == AdvisorPerformance.advisor_id)
        .all()
    )
    try:
        distribucion = calcular_metas_asesoras(store_id, anio, mes, obtener_meta_tienda(store_id, anio, mes)) or {}
    except Exception:
        db.session.rollback()
        distribucion = {}
    metas = {int(a["advisor_id"]): a for a in distribucion.get("asesoras", []) if a.get("advisor_id")}
    dias_mes = monthrange(anio, mes)[1]
    proporcion = min(int(dia_corte or dias_mes), dias_mes) / dias_mes
    resultado = []
    for registro, asesora in filas:
        nombre = (asesora.nombre or "").strip()
        generico = bool(asesora.es_generico) or "VENDEDOR UNICO" in nombre.upper()
        info = metas.get(asesora.id, {})
        meta = _f(info.get("meta"))
        venta = _f(registro.venta)
        facturas = _f(registro.facturas)
        resultado.append({
            "id": asesora.id,
            "nombre": nombre,
            "venta": round(venta),
            "facturas": facturas,
            "unidades": _f(registro.unidades),
            "upt": (_f(registro.unidades) / facturas) if facturas > 0 else 0,
            "ticket": (venta / facturas) if facturas > 0 else 0,
            "meta": round(meta),
            "cump": (venta / meta) if meta > 0 else None,
            "cump_corte": (venta / (meta * proporcion)) if meta > 0 and proporcion > 0 else None,
            "tipo": info.get("tipo_asesora") or ("AUXILIAR" if "ASESOR AUX" in nombre.upper() else "FIJA"),
            "generico": generico,
        })
    resultado.sort(key=lambda a: (a["cump"] is not None, a["cump"] or 0, a["venta"]), reverse=True)
    return resultado, distribucion


def _asesoras_para_revisar(store_id, anio, mes, asesoras):
    """Meta distribuible: asesoras que parecen no ser de planta y siguen como «Fija»."""
    con_meta_guardada = {
        g.advisor_id for g in AdvisorGoal.query.filter_by(store_id=store_id, anio=anio, mes=mes).all()
    }
    mes_ant, anio_ant = (mes - 1, anio) if mes > 1 else (12, anio - 1)
    del_mes_pasado = {
        a for (a,) in db.session.query(AdvisorPerformance.advisor_id).filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio_ant,
            AdvisorPerformance.mes == mes_ant,
        ).distinct().all()
    }
    fijas = [a for a in asesoras if not a["generico"] and a["tipo"] == "FIJA" and a["venta"] > 0]
    if len(fijas) < 2:
        return []
    ventas = sorted(a["venta"] for a in fijas)
    mediana = ventas[len(ventas) // 2]
    revisar = []
    for a in fijas:
        motivos = []
        if a["id"] not in del_mes_pasado:
            motivos.append("es nueva este mes")
        if mediana > 0 and a["venta"] < mediana * 0.35:
            motivos.append(f"vende {round(a['venta'] / mediana * 100)} % de lo que vende una asesora típica de la tienda")
        if motivos and a["id"] not in con_meta_guardada:
            revisar.append({"nombre": a["nombre"], "venta": a["venta"], "meta": a["meta"], "motivo": " y ".join(motivos)})
    return revisar[:5]


def _coach_conversion(store_id, anio, mes, dia_corte, venta, conv_dias):
    trafico = sum(t for t, _ in conv_dias.values())
    facturas = sum(f for _, f in conv_dias.values())
    resultado = {
        "trafico": trafico,
        "facturas": facturas,
        "conversion": (facturas / trafico) if trafico > 0 else None,
        "meta": CONVERSION_META,
        "vpt": (venta / facturas) if facturas > 0 else 0,
        "horas": [],
        "semana": [],
    }
    if trafico > 0:
        objetivo = math.ceil(trafico * CONVERSION_META)
        faltan = max(objetivo - facturas, 0)
        resultado["facturas_faltan"] = faltan
        resultado["venta_perdida"] = round(faltan * resultado["vpt"])
        dias = len([1 for t, _ in conv_dias.values() if t > 0]) or 1
        resultado["faltan_por_dia"] = round(faltan / dias, 1)
        resultado["trafico_dia"] = round(trafico / dias)

    # Tráfico por hora del mes (si la tienda tiene contador por hora)
    try:
        from app.models.trafico_horario import TraficoHorario
        desde = date(anio, mes, 1)
        hasta = date(anio, mes, min(int(dia_corte or monthrange(anio, mes)[1]), monthrange(anio, mes)[1]))
        filas = db.session.query(
            TraficoHorario.hora,
            func.sum(TraficoHorario.trafico),
            func.sum(TraficoHorario.facturas),
            func.count(func.distinct(TraficoHorario.fecha)),
        ).filter(
            TraficoHorario.store_id == store_id,
            TraficoHorario.fecha >= desde,
            TraficoHorario.fecha <= hasta,
            TraficoHorario.sensor_error.is_(False),
        ).group_by(TraficoHorario.hora).all()
        horas = []
        for hora, t, f, n in filas:
            t, f = int(t or 0), (int(f) if f is not None else None)
            if t <= 0:
                continue
            horas.append({
                "hora": int(hora),
                "trafico": t,
                "por_dia": round(t / (n or 1), 1),
                "facturas": f,
                "conversion": (f / t) if f is not None and t > 0 else None,
            })
        horas.sort(key=lambda h: h["hora"])
        resultado["horas"] = horas
        filas_dia = db.session.query(TraficoHorario.fecha, func.sum(TraficoHorario.trafico)).filter(
            TraficoHorario.store_id == store_id,
            TraficoHorario.fecha >= desde,
            TraficoHorario.fecha <= hasta,
            TraficoHorario.sensor_error.is_(False),
        ).group_by(TraficoHorario.fecha).all()
        semana = defaultdict(list)
        for fecha, t in filas_dia:
            if isinstance(fecha, str):
                fecha = date.fromisoformat(fecha[:10])
            semana[fecha.weekday()].append(int(t or 0))
        resultado["semana"] = [
            {"dia": DIAS_SEMANA[d], "trafico": round(sum(v) / len(v))}
            for d, v in sorted(semana.items()) if v
        ]
    except Exception:
        db.session.rollback()
    return resultado


def _celebraciones(ventas_dia, cuota_total, anio, mes, dia_corte):
    dias_mes = monthrange(anio, mes)[1]
    resultado = {"racha": 0, "record": None, "mejor_dia": None}
    if not ventas_dia:
        return resultado
    ultimo = max(ventas_dia)
    meta_dia = cuota_total / dias_mes if cuota_total > 0 else 0
    if meta_dia > 0:
        racha = 0
        for d in range(ultimo, 0, -1):
            if ventas_dia.get(d, 0) >= meta_dia:
                racha += 1
            else:
                break
        resultado["racha"] = racha
        resultado["meta_dia"] = round(meta_dia)
    mejor = max(ventas_dia.items(), key=lambda par: par[1])
    resultado["mejor_dia"] = {"dia": mejor[0], "venta": round(mejor[1]), "nombre": DIAS_SEMANA[date(anio, mes, mejor[0]).weekday()]}
    con_venta = [d for d, v in ventas_dia.items() if v > 0]
    if len(con_venta) >= 5 and mejor[0] == ultimo and ventas_dia[ultimo] > 0:
        resultado["record"] = {"dia": ultimo, "venta": round(ventas_dia[ultimo])}
    return resultado


def _comparacion_clima(store_id, filas_corte):
    tienda = filas_corte.get(store_id)
    if not tienda:
        return None
    clima = (tienda[1].clima or "").strip()
    if not clima:
        return None
    grupo = [
        {"id": sid, "codigo": t.codigo, "nombre": t.nombre, "cump": _f(r.cumplimiento_pct), "mia": sid == store_id}
        for sid, (r, t) in filas_corte.items()
        if (t.clima or "").strip().lower() == clima.lower() and _f(r.cumplimiento_pct) > 0
    ]
    grupo.sort(key=lambda x: x["cump"], reverse=True)
    puesto = next((i for i, x in enumerate(grupo, start=1) if x["mia"]), None)
    general = sorted((_f(r.cumplimiento_pct) for r, _ in filas_corte.values() if _f(r.cumplimiento_pct) > 0), reverse=True)
    mio = _f(tienda[0].cumplimiento_pct)
    return {
        "clima": clima,
        "puesto": puesto,
        "total": len(grupo),
        "puesto_general": (general.index(mio) + 1) if mio in general else None,
        "total_general": len(general),
        "promedio": (sum(x["cump"] for x in grupo) / len(grupo)) if grupo else None,
        "tiendas": [{k: v for k, v in x.items() if k != "id"} for x in grupo],
    }


def datos_tienda(store_id, anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte, store_id=store_id)
    if not anio or not mes:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("tienda", store_id, anio, mes, dia_corte), lambda: _datos_tienda(store_id, anio, mes, dia_corte))


def _datos_tienda(store_id, anio, mes, dia_corte):
    filas = _compliance_corte(anio, mes, dia_corte)
    propia = filas.get(store_id) or _compliance_corte(anio, mes, dia_corte, store_id=store_id).get(store_id)
    tienda = propia[1] if propia else db.session.get(Store, store_id)
    if not tienda:
        return {"ok": False, "motivo": "sin_tienda"}
    registro = propia[0] if propia else None
    venta = _f(registro.venta_actual) if registro else 0
    cuota = _f(registro.cuota_total) if registro else 0
    dias_mes = monthrange(anio, mes)[1]
    corte = min(int(dia_corte or dias_mes), dias_mes)

    ventas_dia = _ventas_por_dia(anio, mes, corte, [store_id]).get(store_id, {})
    conv_dias = _conversion_por_dia(anio, mes, corte, [store_id]).get(store_id, {})
    asesoras, distribucion = _asesoras_al_corte(store_id, anio, mes, dia_corte)

    from flask import url_for
    try:
        url_metas = url_for("admin_goals.admin_metas", store_id=store_id, anio=anio, mes=mes) + "#distribucion"
    except Exception:
        url_metas = None

    return {
        "ok": True,
        "tienda": {"id": tienda.id, "codigo": tienda.codigo, "nombre": tienda.nombre, "clima": tienda.clima},
        "corte": {"anio": anio, "mes": mes, "dia": corte, "dias_mes": dias_mes, "nombre_mes": MESES[mes - 1]},
        "venta": round(venta),
        "venta_anterior": round(_f(registro.venta_anterior)) if registro else 0,
        "cuota_total": round(cuota),
        "cumplimiento": _f(registro.cumplimiento_pct) if registro else 0,
        "proyeccion": proyectar(venta, cuota, ventas_dia, anio, mes, corte) if cuota > 0 and venta > 0 else None,
        "asesoras": [{k: v for k, v in a.items() if k != "id"} for a in asesoras if not a["generico"]],
        "meta_distribuible": {
            "meta_tienda": round(_f(distribucion.get("meta_tienda"))),
            "venta_auxiliares": round(_f(distribucion.get("venta_auxiliar_real"))),
            "distribuible": round(_f(distribucion.get("meta_ajustada"))),
            "de_planta": distribucion.get("cantidad_asesoras") or 0,
            "auxiliares": distribucion.get("cantidad_auxiliares") or 0,
            "revisar": _asesoras_para_revisar(store_id, anio, mes, asesoras),
            "url": url_metas,
        },
        "conversion": _coach_conversion(store_id, anio, mes, corte, venta, conv_dias),
        "celebra": _celebraciones(ventas_dia, cuota, anio, mes, corte),
        "comparacion": _comparacion_clima(store_id, filas),
        "dias": [{"dia": d, "venta": round(v)} for d, v in sorted(ventas_dia.items())],
        "diario": [{"dia": d, "trafico": t, "facturas": f} for d, (t, f) in sorted(conv_dias.items())],
    }


# ==========================================================
# ADMINISTRACIÓN
# ==========================================================

def datos_admin(anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte)
    if not anio or not mes:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("admin", anio, mes, dia_corte), lambda: _datos_admin(anio, mes, dia_corte))


def _url_tienda(store_id, anio, mes, dia_corte):
    from flask import url_for
    try:
        return url_for("dashboard.dashboard_tienda_admin", store_id=store_id, anio=anio, mes=mes, dia_corte=dia_corte)
    except Exception:
        return None


def _datos_admin(anio, mes, dia_corte):
    filas = _compliance_corte(anio, mes, dia_corte)
    dias_mes = monthrange(anio, mes)[1]
    corte = min(int(dia_corte or dias_mes), dias_mes)
    ids = list(filas)
    ventas = _ventas_por_dia(anio, mes, corte, ids)
    conv = _conversion_por_dia(anio, mes, corte, ids)

    tiendas = []
    for sid, (r, t) in filas.items():
        venta, cuota, cump = _f(r.venta_actual), _f(r.cuota_total), _f(r.cumplimiento_pct)
        proy = proyectar(venta, cuota, ventas.get(sid, {}), anio, mes, corte) if cuota > 0 and venta > 0 else None
        tiendas.append({
            "store_id": sid,
            "codigo": t.codigo,
            "nombre": t.nombre,
            "clima": t.clima,
            "venta": round(venta),
            "venta_anterior": round(_f(r.venta_anterior)),
            "cuota_total": round(cuota),
            "meta_corte": round(venta / cump) if cump > 0 else 0,
            "cump": cump,
            "crecimiento": (venta / _f(r.venta_anterior) - 1) if _f(r.venta_anterior) > 0 else None,
            "proy_valor": proy["valor"] if proy else None,
            "proy_pct": proy["pct"] if proy else None,
            "necesita_dia": proy["necesita_dia"] if proy else None,
            "ritmo_dia": proy["ritmo_dia"] if proy else None,
            "url": _url_tienda(sid, anio, mes, dia_corte),
        })
    tiendas.sort(key=lambda x: x["cump"], reverse=True)

    venta_red = sum(x["venta"] for x in tiendas)
    meta_corte_red = sum(x["meta_corte"] for x in tiendas)
    cuota_red = sum(x["cuota_total"] for x in tiendas)
    proy_red = sum((x["proy_valor"] if x["proy_valor"] is not None else x["venta"]) for x in tiendas)
    con_ventas = [x for x in tiendas if x["venta"] > 0]
    hoy = date.today()
    atraso = (hoy.day - 1 - corte) if (anio, mes) == (hoy.year, hoy.month) else 0

    red = {
        "venta": venta_red,
        "venta_anterior": sum(x["venta_anterior"] for x in tiendas),
        "meta_corte": meta_corte_red,
        "cump": (venta_red / meta_corte_red) if meta_corte_red > 0 else None,
        "cuota_total": cuota_red,
        "proyeccion": proy_red,
        "proy_pct": (proy_red / cuota_red) if cuota_red > 0 else None,
        "tiendas": len(con_ventas),
        "al_dia": len([x for x in con_ventas if x["cump"] >= 1]),
        "cerrado": corte >= dias_mes,
        "dias_restantes": max(dias_mes - corte, 0),
    }
    if red["venta_anterior"] > 0:
        red["crecimiento"] = red["venta"] / red["venta_anterior"] - 1

    riesgo = sorted(
        [x for x in con_ventas if x["proy_pct"] is not None and x["proy_pct"] < 0.95 and not red["cerrado"]],
        key=lambda x: x["proy_pct"],
    )[:8]

    resultado = {
        "ok": True,
        "corte": {"anio": anio, "mes": mes, "dia": corte, "dias_mes": dias_mes, "nombre_mes": MESES[mes - 1], "atraso": max(atraso, 0)},
        "red": red,
        "tiendas": tiendas,
        "riesgo": riesgo,
        "diagnostico": _diagnostico(filas, conv, anio, mes, corte),
        "sin_uso": _sin_uso(filas),
        "calidad": _calidad(filas, ventas, conv, anio, mes, corte, atraso),
        "felicitar": _felicitar(filas, anio, mes, dia_corte),
        "cambios": _cambios_bruscos(filas, ventas, anio, mes, corte),
        "v3": _pronostico_v3(tiendas, anio, mes),
        "semana": _semana(filas, ventas, anio, mes, corte),
        "red_tejida": _resumen_red(anio, mes, dia_corte),
    }
    resultado["sugeridos"] = _sugeridos(resultado)
    return resultado


def _resumen_red(anio, mes, dia_corte):
    """Resumen del hilo de la red para el panel de Hilo y el informe semanal."""
    try:
        r = _red_tejida(anio, mes, dia_corte)
    except Exception:
        db.session.rollback()
        return None
    if not r.get("ok"):
        return None
    cortes = r["cortes"]
    # Hace una semana: el corte más cercano a 7 días antes del último
    antes = None
    if len(cortes) > 1:
        objetivo = cortes[-1] - 7
        antes = min(cortes[:-1], key=lambda c: abs(c - objetivo))
    def unidas_en(corte):
        n = 0
        for t in r["tiendas"]:
            racha = None
            for c, v in t["serie"]:
                if c > corte:
                    break
                racha = (racha or c) if v >= 1 else None
            n += 1 if racha is not None else 0
        return n
    return {
        "unidas": r["unidas"], "total": r["total"], "nuevas": r["nuevas"],
        "hace_una_semana": unidas_en(antes) if antes is not None else None,
        "corte_semana": antes,
        "orden": [{"nombre": t["nombre"], "ciudad": t["ciudad"], "dia": t["dia"], "cump": t["cump"]} for t in r["tiendas"] if t["dia"] is not None],
    }


def _diagnostico(filas, conv, anio, mes, corte):
    """¿Por qué cambió la venta frente al año anterior? tráfico × conversión × tiquete."""
    previo = _conversion_por_dia(anio - 1, mes, corte, list(filas))
    resultado = []
    for sid, (r, t) in filas.items():
        v1, v0 = _f(r.venta_actual), _f(r.venta_anterior)
        actual = [conv.get(sid, {}).get(d) for d in range(1, corte + 1)]
        anterior = [previo.get(sid, {}).get(d) for d in range(1, corte + 1)]
        t1 = sum(x[0] for x in actual if x)
        f1 = sum(x[1] for x in actual if x)
        t0 = sum(x[0] for x in anterior if x)
        f0 = sum(x[1] for x in anterior if x)
        if v1 <= 0 or v0 <= 0:
            continue
        item = {
            "store_id": sid, "codigo": t.codigo, "nombre": t.nombre,
            "crecimiento": v1 / v0 - 1, "venta": round(v1), "venta_anterior": round(v0),
            "url": _url_tienda(sid, anio, mes, corte),
        }
        if t1 > 0 and t0 > 0 and f1 > 0 and f0 > 0:
            item.update({
                "trafico": t1 / t0 - 1,
                "conversion": (f1 / t1) / (f0 / t0) - 1,
                "ticket": (v1 / f1) / (v0 / f0) - 1,
                "conv_actual": f1 / t1,
                "conv_anterior": f0 / t0,
            })
            efectos = {
                "trafico": math.log(t1 / t0),
                "conversion": math.log((f1 / t1) / (f0 / t0)),
                "ticket": math.log((v1 / f1) / (v0 / f0)),
            }
            item["causa"] = min(efectos, key=efectos.get) if item["crecimiento"] < 0 else max(efectos, key=efectos.get)
        else:
            item["causa"] = None
        resultado.append(item)
    resultado.sort(key=lambda x: x["crecimiento"])
    return resultado


def _sin_uso(filas):
    """Tiendas cuyo usuario no ha entrado a L&H Pulse en los últimos días."""
    try:
        from app.models.registro_acceso import RegistroAcceso
        from app.models.role import Role
    except Exception:
        return {"activo": False, "tiendas": []}
    try:
        primero = db.session.query(func.min(RegistroAcceso.fecha)).scalar()
        if not primero:
            return {"activo": False, "tiendas": []}
        usuarios = (
            User.query.join(Role, Role.id == User.role_id)
            .filter(func.upper(func.trim(Role.nombre)) == "TIENDA", User.store_id.isnot(None))
            .all()
        )
        ultimos = dict(
            db.session.query(RegistroAcceso.user_id, func.max(RegistroAcceso.fecha))
            .filter(RegistroAcceso.resultado == "ok")
            .group_by(RegistroAcceso.user_id).all()
        )
    except Exception:
        db.session.rollback()
        return {"activo": False, "tiendas": []}
    por_tienda = {}
    for u in usuarios:
        if u.activo is False or u.store_id not in filas:
            continue
        fecha = ultimos.get(u.id)
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha[:19])
        actual = por_tienda.get(u.store_id)
        por_tienda[u.store_id] = max(f for f in (actual, fecha) if f) if (actual or fecha) else None
    ahora = datetime.now()
    tiendas = []
    for sid, fecha in por_tienda.items():
        t = filas[sid][1]
        dias = (ahora - fecha).days if fecha else None
        if dias is None or dias >= 3:
            tiendas.append({
                "store_id": sid, "codigo": t.codigo, "nombre": t.nombre,
                "ultimo": fecha.strftime("%d/%m/%Y %H:%M") if fecha else None,
                "dias": dias,
            })
    tiendas.sort(key=lambda x: (x["dias"] is not None, -(x["dias"] or 0)))
    if isinstance(primero, str):
        primero = datetime.fromisoformat(primero[:19])
    return {"activo": True, "desde": primero.strftime("%d/%m/%Y"), "tiendas": tiendas}


def _calidad(filas, ventas, conv, anio, mes, corte, atraso):
    avisos = []
    if atraso >= 1:
        avisos.append({
            "nivel": "alto" if atraso >= 3 else "medio",
            "titulo": f"Los datos llegan hasta el día {corte}",
            "detalle": f"Hoy es {date.today().day}: {'falta 1 día' if atraso == 1 else f'faltan {atraso} días'} por cargar.",
            "tiendas": [],
        })
    sin_meta = [t for r, t in filas.values() if _f(r.cuota_total) <= 0]
    if sin_meta:
        avisos.append({
            "nivel": "alto",
            "titulo": f"{len(sin_meta)} {'tienda' if len(sin_meta) == 1 else 'tiendas'} sin meta del mes",
            "detalle": "Sin cuota no se puede medir el cumplimiento.",
            "tiendas": [f"{t.codigo}" for t in sin_meta[:12]],
        })

    # Metas por asesora que nadie revisó este mes (distribución automática)
    con_distribucion = {
        sid for (sid,) in db.session.query(AdvisorGoal.store_id).filter(
            AdvisorGoal.anio == anio, AdvisorGoal.mes == mes,
        ).distinct().all()
    }
    sin_revisar = [t for sid, (r, t) in filas.items() if sid not in con_distribucion and _f(r.venta_actual) > 0]
    if sin_revisar:
        avisos.append({
            "nivel": "medio",
            "titulo": f"{len(sin_revisar)} {'tienda no ha' if len(sin_revisar) == 1 else 'tiendas no han'} revisado las metas por asesora",
            "detalle": "La meta se reparte automáticamente; si hay asesoras que no son de planta, deben marcarse como Auxiliar.",
            "tiendas": [t.codigo for t in sin_revisar[:12]],
        })

    # Asesoras nuevas este mes con ventas y meta automática
    mes_ant, anio_ant = (mes - 1, anio) if mes > 1 else (12, anio - 1)
    antes = {
        (s, a) for s, a in db.session.query(AdvisorPerformance.store_id, AdvisorPerformance.advisor_id).filter(
            AdvisorPerformance.anio == anio_ant, AdvisorPerformance.mes == mes_ant,
        ).distinct().all()
    }
    con_meta = {
        (s, a) for s, a in db.session.query(AdvisorGoal.store_id, AdvisorGoal.advisor_id).filter(
            AdvisorGoal.anio == anio, AdvisorGoal.mes == mes,
        ).all()
    }
    if antes:
        nuevas = db.session.query(AdvisorPerformance.store_id, Advisor.nombre).join(
            Advisor, Advisor.id == AdvisorPerformance.advisor_id,
        ).filter(
            AdvisorPerformance.anio == anio, AdvisorPerformance.mes == mes,
            AdvisorPerformance.venta > 0, AdvisorPerformance.store_id.in_(list(filas)),
        ).with_entities(AdvisorPerformance.store_id, AdvisorPerformance.advisor_id, Advisor.nombre, Advisor.es_generico).distinct().all()
        lista = sorted({
            (filas[s][1].codigo, (n or "").strip())
            for s, a, n, g in nuevas
            if (s, a) not in antes and (s, a) not in con_meta and not g and "VENDEDOR UNICO" not in (n or "").upper()
        })
        if lista:
            avisos.append({
                "nivel": "medio",
                "titulo": f"{len(lista)} {'asesora nueva' if len(lista) == 1 else 'asesoras nuevas'} con ventas y meta automática",
                "detalle": "Si no son de planta, cámbienlas a Auxiliar para que la meta distribuible quede bien.",
                "tiendas": [f"{c} · {n.title()}" for c, n in lista[:12]],
            })

    # Días sin ventas cuando el resto de la red sí vendió
    por_dia = defaultdict(int)
    for sid in filas:
        for d, v in ventas.get(sid, {}).items():
            if v > 0:
                por_dia[d] += 1
    hay_ventas = [d for d, n in por_dia.items() if n >= max(2, len(filas) // 2)]
    ceros = []
    for sid, (r, t) in filas.items():
        dias = [d for d in hay_ventas if ventas.get(sid, {}).get(d, 0) <= 0]
        if dias and ventas.get(sid):
            ceros.append(f"{t.codigo} ({', '.join(str(d) for d in sorted(dias)[:5])}{'…' if len(dias) > 5 else ''})")
    if ceros:
        avisos.append({
            "nivel": "medio",
            "titulo": f"{len(ceros)} {'tienda' if len(ceros) == 1 else 'tiendas'} con días en cero",
            "detalle": "El resto de la red sí vendió esos días: puede faltar la carga o el día estuvo cerrado.",
            "tiendas": ceros[:12],
        })

    sin_trafico = []
    for sid, (r, t) in filas.items():
        n = len([1 for tr, fa in conv.get(sid, {}).values() if tr == 0 and fa > 0])
        if n:
            sin_trafico.append(f"{t.codigo} ({n} {'día' if n == 1 else 'días'})")
    if sin_trafico:
        avisos.append({
            "nivel": "bajo",
            "titulo": f"{len(sin_trafico)} {'tienda' if len(sin_trafico) == 1 else 'tiendas'} con ventas y sin tráfico",
            "detalle": "Puede fallar el contador de personas.",
            "tiendas": sin_trafico[:12],
        })
    return avisos


def _felicitar(filas, anio, mes, dia_corte):
    """Las que más mejoraron frente al corte anterior y las que van arriba de la meta."""
    anteriores = sorted({
        int(c) for (c,) in db.session.query(Compliance.dia_corte).filter(
            Compliance.anio == anio, Compliance.mes == mes, Compliance.dia_corte.isnot(None),
        ).distinct().all() if c is not None and dia_corte is not None and int(c) < int(dia_corte)
    })
    referencia = None
    if anteriores:
        objetivo = int(dia_corte) - 7
        referencia = min(anteriores, key=lambda c: abs(c - objetivo))
    mejoras = []
    if referencia is not None:
        antes = {sid: _f(r.cumplimiento_pct) for sid, (r, _) in _compliance_corte(anio, mes, referencia).items()}
        for sid, (r, t) in filas.items():
            ahora, previo = _f(r.cumplimiento_pct), antes.get(sid)
            if previo and ahora > 0 and ahora - previo >= 0.02:
                mejoras.append({"store_id": sid, "codigo": t.codigo, "nombre": t.nombre, "antes": previo, "ahora": ahora, "mejora": ahora - previo})
        mejoras.sort(key=lambda x: x["mejora"], reverse=True)
    ya = {x["store_id"] for x in mejoras[:5]}
    arriba = sorted(
        [{"store_id": sid, "codigo": t.codigo, "nombre": t.nombre, "ahora": _f(r.cumplimiento_pct)}
         for sid, (r, t) in filas.items() if _f(r.cumplimiento_pct) >= 1 and sid not in ya],
        key=lambda x: x["ahora"], reverse=True,
    )
    return {"referencia": referencia, "mejoras": mejoras[:5], "arriba": arriba[:5]}


def _ventas_fecha(filas, ventas, anio, mes, corte):
    """{store_id: {fecha: venta}} del mes actual y el anterior (para comparar el mismo día de la semana)."""
    mes_ant, anio_ant = (mes - 1, anio) if mes > 1 else (12, anio - 1)
    previas = _ventas_por_dia(anio_ant, mes_ant, None, list(filas))
    resultado = defaultdict(dict)
    for sid in filas:
        for d, v in previas.get(sid, {}).items():
            resultado[sid][date(anio_ant, mes_ant, d)] = v
        for d, v in ventas.get(sid, {}).items():
            resultado[sid][date(anio, mes, d)] = v
    return resultado


def _cambios_bruscos(filas, ventas, anio, mes, corte):
    if not corte:
        return []
    por_fecha = _ventas_fecha(filas, ventas, anio, mes, corte)
    ultimo = date(anio, mes, corte)
    cambios = []
    for sid, (r, t) in filas.items():
        serie = por_fecha.get(sid, {})
        for atras in (0, 1):
            dia = ultimo - timedelta(days=atras)
            valor = serie.get(dia)
            if valor is None:
                continue
            muestras = [serie.get(dia - timedelta(days=7 * k)) for k in range(1, 5)]
            muestras = [m for m in muestras if m and m > 0]
            if len(muestras) < 2:
                continue
            promedio = sum(muestras) / len(muestras)
            variacion = valor / promedio - 1 if promedio > 0 else 0
            if variacion <= -0.45 or variacion >= 0.8:
                cambios.append({
                    "store_id": sid, "codigo": t.codigo, "nombre": t.nombre,
                    "dia": dia.day, "nombre_dia": DIAS_SEMANA[dia.weekday()],
                    "venta": round(valor), "promedio": round(promedio), "variacion": variacion,
                    "url": _url_tienda(sid, anio, mes, corte),
                })
                break
    cambios.sort(key=lambda x: x["variacion"])
    return cambios[:10]


def _semana(filas, ventas, anio, mes, corte):
    """Últimos 7 días frente a los 7 anteriores, por tienda (para el informe semanal)."""
    if not corte:
        return {"tiendas": []}
    por_fecha = _ventas_fecha(filas, ventas, anio, mes, corte)
    fin = date(anio, mes, corte)
    resultado = []
    total_actual = total_previa = 0
    for sid, (r, t) in filas.items():
        serie = por_fecha.get(sid, {})
        actual = sum(serie.get(fin - timedelta(days=k), 0) for k in range(7))
        previa = sum(serie.get(fin - timedelta(days=k), 0) for k in range(7, 14))
        total_actual += actual
        total_previa += previa
        resultado.append({
            "codigo": t.codigo, "nombre": t.nombre, "actual": round(actual), "previa": round(previa),
            "variacion": (actual / previa - 1) if previa > 0 else None,
        })
    resultado.sort(key=lambda x: x["actual"], reverse=True)
    return {
        "desde": (fin - timedelta(days=6)).strftime("%d/%m"),
        "hasta": fin.strftime("%d/%m/%Y"),
        "actual": round(total_actual),
        "previa": round(total_previa),
        "variacion": (total_actual / total_previa - 1) if total_previa > 0 else None,
        "tiendas": resultado,
    }


def _pronostico_v3(tiendas, anio, mes):
    """Pronóstico V3 (P50) frente a cómo va de verdad cada tienda. Si no hay corrida, no muestra nada."""
    try:
        with db.engine.connect() as conexion:
            corrida = conexion.execute(text(
                "SELECT id, created_at FROM ai_v3_runs WHERE anio = :a AND mes = :m AND status = 'SUCCESS' ORDER BY id DESC"
            ), {"a": anio, "m": mes}).first()
            if not corrida:
                return None
            filas = conexion.execute(text(
                "SELECT store_id, SUM(venta_p10), SUM(venta_p50), SUM(venta_p90), AVG(probabilidad_cumplimiento) "
                "FROM ai_v3_forecasts WHERE run_id = :r GROUP BY store_id"
            ), {"r": corrida[0]}).all()
    except Exception:
        return None
    por_tienda = {int(f[0]): f for f in filas if f[0] is not None}
    lista = []
    for x in tiendas:
        f = por_tienda.get(x["store_id"])
        if not f or not _f(f[2]):
            continue
        esperado = x["proy_valor"] if x["proy_valor"] is not None else x["venta"]
        p10, p50, p90 = _f(f[1]), _f(f[2]), _f(f[3])
        lista.append({
            "store_id": x["store_id"], "codigo": x["codigo"], "nombre": x["nombre"],
            "p10": round(p10), "p50": round(p50), "p90": round(p90),
            "proyeccion": round(esperado),
            "diferencia": esperado / p50 - 1,
            "fuera": "abajo" if p10 and esperado < p10 else "arriba" if p90 and esperado > p90 else None,
            "probabilidad": _f(f[4]) if f[4] is not None else None,
        })
    if not lista:
        return None
    lista.sort(key=lambda x: x["diferencia"])
    total_p50 = sum(x["p50"] for x in lista)
    total_proy = sum(x["proyeccion"] for x in lista)
    fecha = corrida[1]
    if isinstance(fecha, str):
        fecha = fecha[:10]
    elif fecha:
        fecha = fecha.strftime("%d/%m/%Y")
    return {
        "corrida": fecha,
        "p50": total_p50,
        "proyeccion": total_proy,
        "diferencia": (total_proy / total_p50 - 1) if total_p50 else None,
        "tiendas": lista,
    }


def _sugeridos(datos):
    """Mensajes listos para enviar con Hilo, armados con los datos del corte."""
    sugeridos = []
    red, corte = datos["red"], datos["corte"]
    for x in datos["felicitar"]["mejoras"][:3]:
        sugeridos.append({
            "motivo": f"{x['codigo']} subió {round((x['ahora'] - x['antes']) * 100)} puntos",
            "tono": "celebra",
            "tiendas": [x["store_id"]],
            "texto": f"¡Felicitaciones, {x['nombre']}! Pasaron de {round(x['antes'] * 100)} % a {round(x['ahora'] * 100)} % de cumplimiento esta semana. ¡Sigan con ese ritmo!",
        })
    for x in datos["felicitar"]["arriba"][:2]:
        if any(x["store_id"] in s["tiendas"] for s in sugeridos):
            continue
        sugeridos.append({
            "motivo": f"{x['codigo']} va en {round(x['ahora'] * 100)} %",
            "tono": "celebra",
            "tiendas": [x["store_id"]],
            "texto": f"¡{x['nombre']}, van por encima de la meta con {round(x['ahora'] * 100)} %! Gracias por el esfuerzo de todo el equipo.",
        })
    if datos["riesgo"] and not red["cerrado"]:
        ids = [x["store_id"] for x in datos["riesgo"][:6]]
        sugeridos.append({
            "motivo": f"{len(ids)} tiendas proyectan cerrar por debajo del 95 %",
            "tono": "anima",
            "tiendas": ids,
            "texto": f"Quedan {red['dias_restantes']} días del mes y todavía se puede. Revisen en Hilo cuánto necesitan vender por día y repartan el reto entre todas. ¡Vamos con toda!",
        })
    if datos["sin_uso"].get("tiendas"):
        ids = [x["store_id"] for x in datos["sin_uso"]["tiendas"][:10]]
        sugeridos.append({
            "motivo": f"{len(ids)} tiendas llevan días sin entrar",
            "tono": "aviso",
            "tiendas": ids,
            "texto": "Las extrañamos en L&H Pulse. Entren todos los días a revisar la meta de hoy de cada asesora: ahí está el plan para cerrar el mes.",
        })
    if red.get("proy_pct") and not red["cerrado"]:
        sugeridos.append({
            "motivo": f"La red proyecta cerrar en {round(red['proy_pct'] * 100)} %",
            "tono": "anima" if red["proy_pct"] < 1 else "celebra",
            "tiendas": [],
            "texto": (f"Así vamos en {corte['nombre_mes']}: al ritmo de hoy la red cierra en {round(red['proy_pct'] * 100)} %. "
                      + ("¡Un último empujón y llegamos!" if red["proy_pct"] < 1 else "¡Vamos a cerrar por encima de la meta!")),
        })
    return sugeridos[:6]


# ==========================================================
# Mensajes con Hilo: quién lo vio
# ==========================================================

def vistos_mensajes(limite=60):
    from app.models.mensaje_hilo import MensajeHilo, MensajeHiloVisto
    from app.routes.mensajes_hilo import _destinatarios

    mensajes = MensajeHilo.query.order_by(MensajeHilo.creado.desc()).limit(limite).all()
    usuarios = {u.id: u for u in User.query.all()}
    resultado = []
    for m in mensajes:
        vistos = {v.user_id: v.visto for v in MensajeHiloVisto.query.filter_by(mensaje_id=m.id).all()}
        vieron, faltan = [], []
        for u in _destinatarios(m):
            fila = {
                "usuario": u.nombre,
                "tienda": (u.store.codigo if u.store else None),
                "fecha": vistos[u.id].strftime("%d/%m %H:%M") if u.id in vistos and vistos[u.id] else None,
            }
            (vieron if u.id in vistos else faltan).append(fila)
        for uid in vistos:
            if uid in usuarios and not any(v["usuario"] == usuarios[uid].nombre for v in vieron):
                u = usuarios[uid]
                vieron.append({"usuario": u.nombre, "tienda": u.store.codigo if u.store else None,
                               "fecha": vistos[uid].strftime("%d/%m %H:%M") if vistos[uid] else None})
        orden = lambda x: (x["tienda"] or "zz", x["usuario"] or "")
        resultado.append({"id": m.id, "vieron": sorted(vieron, key=orden), "faltan": sorted(faltan, key=orden)})
    return resultado


# ==========================================================
# El hilo que une la red (modo del mapa del administrador)
# ==========================================================

def red_tejida(anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte)
    if not anio or not mes:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("red", anio, mes, dia_corte), lambda: _red_tejida(anio, mes, dia_corte))


def _red_tejida(anio, mes, dia_corte):
    """Cumplimiento de cada tienda en cada corte del mes y el día en que se unió al hilo.

    Una tienda «se une al hilo» el primer corte de su racha actual con cumplimiento al
    corte de 100 % o más. Si después baja del 100 %, sale del hilo.
    """
    sub = db.session.query(
        Compliance.store_id.label("store_id"),
        Compliance.dia_corte.label("dia_corte"),
        func.max(Compliance.id).label("max_id"),
    ).filter(
        Compliance.anio == anio, Compliance.mes == mes, Compliance.dia_corte.isnot(None),
    )
    if dia_corte is not None:
        sub = sub.filter(Compliance.dia_corte <= dia_corte)
    sub = sub.group_by(Compliance.store_id, Compliance.dia_corte).subquery()
    filas = (
        db.session.query(Compliance.store_id, Compliance.dia_corte, Compliance.cumplimiento_pct, Store)
        .join(sub, Compliance.id == sub.c.max_id)
        .join(Store, Store.id == Compliance.store_id)
        .all()
    )
    series, tiendas = defaultdict(list), {}
    for store_id, corte, cump, tienda in filas:
        if _excluir_tienda(tienda, anio, mes):
            continue
        series[store_id].append((int(corte), _f(cump)))
        tiendas[store_id] = tienda
    cortes = sorted({c for s in series.values() for c, _ in s})
    resultado, sin_ubicacion = [], 0
    for store_id, serie in series.items():
        serie.sort()
        t = tiendas[store_id]
        dia_union = None
        for corte, cump in serie:
            if cump >= 1:
                dia_union = dia_union or corte
            else:
                dia_union = None
        if t.lat is None or t.lng is None:
            sin_ubicacion += 1
        resultado.append({
            "id": store_id, "codigo": t.codigo, "nombre": t.nombre, "ciudad": t.ciudad,
            "lat": t.lat, "lng": t.lng,
            "cump": serie[-1][1], "dia": dia_union,
            "serie": [[c, round(v, 4)] for c, v in serie],
        })
    resultado.sort(key=lambda x: (x["dia"] is None, x["dia"] or 0, -x["cump"]))
    unidas = [x for x in resultado if x["dia"] is not None]
    ultimo = cortes[-1] if cortes else None
    previo = cortes[-2] if len(cortes) > 1 else None
    return {
        "ok": True,
        "corte": {"anio": anio, "mes": mes, "dia": ultimo, "nombre_mes": MESES[mes - 1], "dias_mes": monthrange(anio, mes)[1]},
        "cortes": cortes,
        "tiendas": resultado,
        "unidas": len(unidas),
        "total": len(resultado),
        # Las que se unieron en el último corte (para que Hilo las anuncie)
        "nuevas": [x["nombre"] for x in unidas if x["dia"] == ultimo and previo is not None],
        "sin_ubicacion": sin_ubicacion,
    }
