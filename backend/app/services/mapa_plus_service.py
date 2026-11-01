"""Datos extra para «Mapa y resultados» (mapa_plus.js). Solo lectura.

Por tienda, al corte elegido:
- meta del mes, meta al corte, lo que falta para el 100 % al corte y cuántas facturas son
- proyección de cierre (la misma de Hilo inteligente)
- venta de cada día del mes (para el pulso en el tiempo)
- asesoras: cuántas tienen meta y cuántas ya la pasaron (el mismo cálculo de Ranking de desempeño)
- última visita registrada en Evaluación de visitas
- región registrada de la tienda
"""
from calendar import monthrange
from datetime import date

from sqlalchemy import func

from app.extensions import db
from app.services.hilo_inteligente_service import (
    _compliance_corte, _con_cache, _f, _url_tienda, _ventas_por_dia, proyectar, resolver_corte,
)


def mapa_plus(anio=None, mes=None, dia_corte=None):
    anio, mes, dia_corte = resolver_corte(anio, mes, dia_corte)
    if not anio or not mes:
        return {"ok": False, "motivo": "sin_datos"}
    return _con_cache(("mapa_plus", anio, mes, dia_corte), lambda: _mapa_plus(anio, mes, dia_corte))


def _asesoras(anio, mes, dia_corte):
    try:
        from app.routes.ranking import _ranking_asesoras
        filas = _ranking_asesoras(anio, mes, dia_corte, None, None)
    except Exception:
        db.session.rollback()
        return {}
    resultado = {}
    for a in filas:
        if "VENDEDOR UNICO" in (a["asesora"] or "").upper():
            continue
        r = resultado.setdefault(a["store_id"], {"total": 0, "con_meta": 0, "en_meta": 0, "lista": []})
        r["total"] += 1
        if not a["sin_meta"]:
            r["con_meta"] += 1
            r["en_meta"] += 1 if a["cumplimiento"] >= 1 else 0
        r["lista"].append({
            "nombre": (a["asesora"] or "").strip().title(),
            "cump": None if a["sin_meta"] else round(a["cumplimiento"], 4),
        })
    return resultado


def _visitas(store_ids):
    if not store_ids:
        return {}
    try:
        from app.models import ChecklistVisita
        sub = db.session.query(
            ChecklistVisita.store_id.label("store_id"), func.max(ChecklistVisita.fecha_visita).label("fecha"),
        ).filter(ChecklistVisita.store_id.in_(list(store_ids))).group_by(ChecklistVisita.store_id).subquery()
        filas = (
            db.session.query(ChecklistVisita.store_id, ChecklistVisita.fecha_visita, ChecklistVisita.cumplimiento_pct, ChecklistVisita.respuestas)
            .join(sub, (ChecklistVisita.store_id == sub.c.store_id) & (ChecklistVisita.fecha_visita == sub.c.fecha))
            .all()
        )
    except Exception:
        db.session.rollback()
        return {}
    hoy = date.today()
    return {
        store_id: {"fecha": fecha.isoformat(), "dias": (hoy - fecha).days, "pct": round(_f(pct), 1), "pendientes": _pendientes(respuestas)}
        for store_id, fecha, pct, respuestas in filas if fecha
    }


def _pendientes(respuestas):
    """Puntos que salieron en «no» en la evaluación (para revisarlos en la siguiente visita)."""
    if not isinstance(respuestas, dict):
        return []
    items = []
    for categoria, valores in respuestas.items():
        if str(categoria).startswith("__") or not isinstance(valores, dict):
            continue
        for item, datos in valores.items():
            if isinstance(datos, dict) and str(datos.get("cumple", "")).lower() == "no":
                items.append({"categoria": categoria, "item": item})
    return items[:8]


def _mapa_plus(anio, mes, dia_corte):
    filas = _compliance_corte(anio, mes, dia_corte)
    if not filas:
        return {"ok": False, "motivo": "sin_datos"}
    corte = max(int(r.dia_corte or 0) for r, _ in filas.values()) or dia_corte
    dias_mes = monthrange(anio, mes)[1]
    ventas = _ventas_por_dia(anio, mes, corte, filas.keys())
    asesoras = _asesoras(anio, mes, corte)
    visitas = _visitas(filas.keys())
    tiendas = []
    for store_id, (registro, tienda) in filas.items():
        venta = _f(registro.venta_actual)
        cuota = _f(registro.cuota_total)
        meta_corte = _f(registro.cuota_proporcional) or (cuota * min(corte, dias_mes) / dias_mes if cuota else 0)
        ticket = _f(registro.ticket_promedio)
        falta = max(meta_corte - venta, 0)
        dias = ventas.get(store_id, {})
        try:
            proy = proyectar(venta, cuota, dias, anio, mes, corte) if cuota > 0 and venta > 0 else None
        except Exception:
            proy = None
        tiendas.append({
            "id": store_id,
            "region": tienda.region.nombre if getattr(tienda, "region", None) else None,
            "meta": round(cuota),
            "meta_corte": round(meta_corte),
            "falta": round(falta),
            "facturas_faltan": int(-(-falta // ticket)) if falta > 0 and ticket > 0 else 0,
            "proyeccion": {"valor": proy["valor"], "pct": proy["pct"]} if proy else None,
            "dias": [round(dias.get(d, 0)) for d in range(1, min(corte, dias_mes) + 1)],
            "asesoras": asesoras.get(store_id),
            "visita": visitas.get(store_id),
            "url": _url_tienda(store_id, anio, mes, corte),
        })
    return {"ok": True, "corte": {"anio": anio, "mes": mes, "dia": corte, "dias_mes": dias_mes}, "tiendas": tiendas}
