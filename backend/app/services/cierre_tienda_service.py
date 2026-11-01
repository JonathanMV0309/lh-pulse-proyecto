"""Tiendas cerradas parte del mes (remodelación, apertura): la cuota cuenta solo los días que vendieron.

Se registra en «Novedades del personal» como «Cierre de tienda» (tienda, desde, hasta). Con eso:
  Cuota total    = cuota del mes × días abierta en el mes / días del mes
  Cuota al corte = cuota del mes × días abierta hasta el corte / días del mes   (0 antes de reabrir)
  Cumplimiento al corte = venta / cuota al corte · Falta = cuota total − venta
Se aplica al guardar o borrar la novedad y en cada carga del Excel, sin importar lo que traiga la
hoja CUMPL. Los valores originales del Excel se guardan aparte (ajustes_cuota_cierre) para poder
recalcular siempre desde ellos y devolverlos si se borra la novedad.
"""
from calendar import monthrange
from datetime import date, timedelta

from app.extensions import db

TIPO = "CIERRE_TIENDA"
COLUMNAS = ["cuota_total", "cuota_proporcional", "cumplimiento_pct", "venta_promedio_dia", "falta_para_cuota"]


def dias_cerrados(store_id, anio, mes):
    """Días del mes (1..31) en que la tienda estuvo cerrada según las novedades «Cierre de tienda»."""
    try:
        from app.models.novedad_personal import NovedadPersonal
        if not db.inspect(db.engine).has_table(NovedadPersonal.__tablename__):
            return set()
        inicio = date(anio, mes, 1)
        fin = date(anio, mes, monthrange(anio, mes)[1])
        dias = set()
        for n in NovedadPersonal.query.filter(NovedadPersonal.store_id == store_id, NovedadPersonal.tipo == TIPO,
                                              NovedadPersonal.desde <= fin).all():
            d, hasta = max(n.desde, inicio), min(n.hasta or n.desde, fin)
            while d <= hasta:
                dias.add(d.day)
                d += timedelta(days=1)
        return dias
    except Exception:
        return set()


def _ajustar(c, cerrados, dias_mes):
    from app.models.ajuste_cuota import AjusteCuota
    original = db.session.get(AjusteCuota, c.id)
    if not cerrados:
        if original:   # se borró el cierre: vuelven los valores del Excel
            for col in COLUMNAS:
                setattr(c, col, getattr(original, col))
            db.session.delete(original)
        return
    if not original:
        original = AjusteCuota(compliance_id=c.id, **{col: getattr(c, col) for col in COLUMNAS})
        db.session.add(original)
    total_mes = float(original.cuota_total or 0)
    if total_mes <= 0:
        return
    corte = dias_mes if c.es_cierre else max(1, min(int(c.dia_corte or dias_mes), dias_mes))
    abierta_mes = dias_mes - len(cerrados)
    abierta_corte = corte - sum(1 for d in cerrados if d <= corte)
    venta = float(c.venta_actual or 0)
    total = total_mes * abierta_mes / dias_mes
    cuota = total_mes * abierta_corte / dias_mes
    c.cuota_total = total
    c.cuota_proporcional = cuota
    c.cumplimiento_pct = venta / cuota if cuota > 0 else 0.0
    c.venta_promedio_dia = venta / abierta_corte if abierta_corte > 0 else 0.0
    c.falta_para_cuota = total - venta
    original.dias_cerrada = len(cerrados)


def guardar_original(registro, valores, dias_cerrada):
    """Guarda la cuota del mes completo de un corte que la carga ajustó por lo que trae el Excel."""
    from app.models.ajuste_cuota import AjusteCuota, crear_tabla_si_falta
    crear_tabla_si_falta()
    db.session.flush()
    if registro.id and not db.session.get(AjusteCuota, registro.id):
        db.session.add(AjusteCuota(compliance_id=registro.id, dias_cerrada=dias_cerrada,
                                   **{col: valores.get(col) for col in COLUMNAS}))


def reajustar(store_id, anio, mes, commit=True):
    """Aplica (o quita) el cierre a todos los cortes cargados de esa tienda en ese mes."""
    from app.models.ajuste_cuota import crear_tabla_si_falta
    from app.models.compliance import Compliance
    crear_tabla_si_falta()
    cerrados = dias_cerrados(store_id, anio, mes)
    dias_mes = monthrange(anio, mes)[1]
    registros = Compliance.query.filter(Compliance.store_id == store_id, Compliance.anio == anio, Compliance.mes == mes).all()
    for c in registros:
        _ajustar(c, cerrados, dias_mes)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return len(registros)


def meses(desde, hasta):
    """(año, mes) que toca un rango de fechas."""
    resultado, d = [], date(desde.year, desde.month, 1)
    while d <= (hasta or desde):
        resultado.append((d.year, d.month))
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return resultado
