"""Metas de las asesoras ajustadas por las novedades de Talento Humano.

Los días que una asesora no estuvo en la tienda no cuentan:
- vacaciones, incapacidad, licencias, calamidad y permisos de día completo;
- retiro o traslado: desde la fecha de la novedad ya no está en la tienda de origen;
- traslado a esta tienda o ingreso: los días antes de la fecha todavía no estaba.

Meta del mes ajustada = meta × días en la tienda / días del mes.
Debería ir hoy        = meta × días en la tienda hasta el corte / días del mes.
Si no hay novedades (o la tabla todavía no existe) todo queda igual que antes.
"""
from calendar import monthrange
from datetime import date, timedelta

from app.extensions import db

MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
SALIDAS = {"RETIRO", "TRASLADO"}


def _rango(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def _fecha_corta(d):
    return f"{d.day} {MESES_CORTOS[d.month - 1]}"


def ajustes(pares, anio, mes, dia_corte):
    """{(store_id, advisor_id): {"factor_mes", "factor_corte", "etiquetas"}} solo para quien tiene novedades."""
    pares = {(int(s), int(a)) for s, a in pares if s and a}
    if not pares or not anio or not mes:
        return {}
    try:
        from app.models.novedad_personal import NovedadPersonal
        from app.routes.novedades import AUSENCIA, HORAS_DIA, NOMBRE_TIPO
        if not db.inspect(db.engine).has_table(NovedadPersonal.__tablename__):
            return {}
        anio, mes = int(anio), int(mes)
        dias_mes = monthrange(anio, mes)[1]
        inicio, fin = date(anio, mes, 1), date(anio, mes, dias_mes)
        corte = min(int(dia_corte or dias_mes), dias_mes)
        asesoras = {a for _, a in pares}
        novedades = NovedadPersonal.query.filter(
            NovedadPersonal.advisor_id.in_(sorted(asesoras)), NovedadPersonal.desde <= fin,
            db.or_(NovedadPersonal.hasta.is_(None), NovedadPersonal.hasta >= inicio, NovedadPersonal.tipo.in_(sorted(SALIDAS))),
        ).order_by(NovedadPersonal.desde).all()
    except Exception:
        db.session.rollback()
        return {}

    from app.models.store import Store
    codigos = {}
    fuera, etiquetas = {}, {}
    for n in novedades:
        hasta = n.hasta or n.desde
        for store_id in {n.store_id, n.tienda_destino_id}:
            par = (store_id, n.advisor_id)
            if par not in pares:
                continue
            dias = set()
            if n.tipo in AUSENCIA and n.tipo != "CIERRE_TIENDA":
                if store_id != n.store_id or (n.horas is not None and n.horas < ((hasta - n.desde).days + 1) * HORAS_DIA):
                    continue   # un permiso de pocas horas no quita el día
                dias = set(_rango(max(n.desde, inicio), min(hasta, fin)))
                texto = f"{NOMBRE_TIPO.get(n.tipo, n.tipo)} " + (f"{_fecha_corta(n.desde)}" if n.desde == hasta else f"{_fecha_corta(n.desde)} – {_fecha_corta(hasta)}")
            elif n.tipo in SALIDAS and store_id == n.store_id:
                dias = set(_rango(max(n.desde, inicio), fin))
                if n.tipo == "RETIRO":
                    texto = f"Retirada desde el {_fecha_corta(n.desde)}"
                else:
                    if n.tienda_destino_id and n.tienda_destino_id not in codigos:
                        destino = db.session.get(Store, n.tienda_destino_id)
                        codigos[n.tienda_destino_id] = destino.codigo if destino else ""
                    texto = f"Trasladada a {codigos.get(n.tienda_destino_id) or 'otra tienda'} desde el {_fecha_corta(n.desde)}"
            elif (n.tipo == "TRASLADO" and store_id == n.tienda_destino_id) or (n.tipo == "INGRESO" and store_id == n.store_id):
                dias = set(_rango(inicio, min(n.desde - timedelta(days=1), fin)))
                texto = ("Llegó a la tienda" if n.tipo == "TRASLADO" else "Ingresó") + f" el {_fecha_corta(n.desde)}"
            else:
                continue
            if not dias and not (n.tipo in SALIDAS and n.desde <= fin):
                continue
            fuera.setdefault(par, set()).update(dias)
            etiquetas.setdefault(par, []).append(texto)

    resultado = {}
    for par, dias in fuera.items():
        en_tienda_mes = dias_mes - len(dias)
        en_tienda_corte = corte - sum(1 for d in dias if d.day <= corte)
        resultado[par] = {
            "factor_mes": max(en_tienda_mes, 0) / dias_mes,
            "factor_corte": max(en_tienda_corte, 0) / dias_mes,
            "dias_fuera": len(dias),
            "etiquetas": etiquetas.get(par, []),
        }
    return resultado


def aplicar(meta_valor, ajuste, dia_corte, dias_mes):
    """(meta del mes ajustada, debería ir hoy). Sin ajuste, el cálculo de siempre."""
    meta_valor = float(meta_valor or 0)
    if meta_valor <= 0:
        return meta_valor, 0
    if not ajuste:
        return meta_valor, meta_valor * (min(dia_corte, dias_mes) / dias_mes) if dia_corte else 0
    return meta_valor * ajuste["factor_mes"], meta_valor * ajuste["factor_corte"]
