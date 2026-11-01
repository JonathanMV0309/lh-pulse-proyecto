from collections import defaultdict
from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import func, false

from app.extensions import db
from app.models.conversion_diaria import ConversionDiaria
from app.models.daily_sales import DailySales
from app.models.store import Store
from app.models.trafico_horario import TraficoCarga, TraficoHorario as H

ROLES = {'ADMIN', 'ADMINISTRADOR', 'TIENDA', 'SUPERVISOR', 'SUPERVISORA'}


def tiendas_permitidas(usuario):
    rol = usuario.role.nombre.strip().upper() if usuario.role else ''
    q = Store.query
    if rol in {'ADMIN', 'ADMINISTRADOR'}:
        return q
    if rol == 'TIENDA' and usuario.store_id:
        return q.filter(Store.id == usuario.store_id)
    if rol in {'SUPERVISOR', 'SUPERVISORA'} and usuario.supervisor_id:
        return q.filter(Store.supervisor_id == usuario.supervisor_id)
    return q.filter(false())


def _fecha_corte_historico():
    for identificador in (2, 1):
        carga = db.session.get(TraficoCarga, identificador)
        raw = (carga.resumen or {}).get('trafico_hasta') if carga else None
        if raw:
            try:
                return date.fromisoformat(raw)
            except (TypeError, ValueError):
                pass
    return db.session.query(func.max(H.fecha)).scalar()


def _limites(tienda_ids):
    minimo, maximo = db.session.query(func.min(H.fecha), func.max(H.fecha)).filter(
        H.store_id.in_(tienda_ids)).one()
    diarios = db.session.query(
        ConversionDiaria.anio, ConversionDiaria.mes, ConversionDiaria.dia
    ).filter(ConversionDiaria.store_id.in_(tienda_ids), ConversionDiaria.activo.is_(True)).all()
    for anio, mes, dia in diarios:
        try:
            valor = date(anio, mes, dia)
        except (TypeError, ValueError):
            continue
        minimo = valor if minimo is None or valor < minimo else minimo
        maximo = valor if maximo is None or valor > maximo else maximo
    return minimo, maximo


def filtros(args, tienda_ids):
    _, ultimo = _limites(tienda_ids)
    ultimo = ultimo or date.today()
    try:
        desde = date.fromisoformat(args.get('desde') or (ultimo - timedelta(days=29)).isoformat())
        hasta = date.fromisoformat(args.get('hasta') or ultimo.isoformat())
        h0, h1 = int(args.get('hora_desde', 0)), int(args.get('hora_hasta', 23))
        dia = int(args['dia']) if args.get('dia') else None
        tienda = int(args['tienda']) if args.get('tienda') else None
        calidad = args.get('calidad', 'validos')
    except (ValueError, TypeError):
        raise ValueError('Revisa las fechas, horas y tienda seleccionadas')
    if desde > hasta or (hasta - desde).days > 1460:
        raise ValueError('El rango debe estar ordenado y no superar cuatro años')
    if not 0 <= h0 <= h1 <= 23 or dia is not None and not 0 <= dia <= 6:
        raise ValueError('Franja horaria o día de semana inválido')
    if calidad not in {'validos', 'todos'}:
        raise ValueError('Filtro de calidad inválido')
    if tienda is not None and tienda not in tienda_ids:
        raise PermissionError('Tienda no autorizada')
    return dict(desde=desde.isoformat(), hasta=hasta.isoformat(), hora_desde=h0,
                hora_hasta=h1, dia=dia, tienda=tienda, calidad=calidad)


def acumulador():
    return dict(trafico=None, facturas=None, trafico_comparable=0,
                facturas_comparables=0, horas_coincidentes=0, horas_trafico=0,
                horas_facturas=0, horas_error=0, dias_coincidentes=0,
                dias_trafico=0, dias_facturas=0)


def acumular(total, fila, granularidad='hora'):
    prefijo = 'horas_' if granularidad == 'hora' else 'dias_'
    for campo in ('trafico', 'facturas'):
        valor = getattr(fila, campo)
        if valor is not None:
            total[campo] = (total[campo] or 0) + valor
            total[prefijo + campo] += 1
    if granularidad == 'hora':
        total['horas_error'] += int(fila.sensor_error)
    if fila.trafico is not None and fila.facturas is not None and not fila.sensor_error:
        total['trafico_comparable'] += fila.trafico
        total['facturas_comparables'] += fila.facturas
        clave = 'horas_coincidentes' if granularidad == 'hora' else 'dias_coincidentes'
        total[clave] += 1


def completar_facturas_diarias(total, facturas, trafico):
    """Completa facturas sin cobertura horaria y conserva el tráfico histórico."""
    if facturas is None:
        return
    total['facturas'] = (total['facturas'] or 0) + facturas
    total['dias_facturas'] += 1
    if trafico is not None:
        total['facturas_comparables'] += facturas
        total['trafico_comparable'] += trafico
        total['dias_coincidentes'] += 1


def finalizar(total):
    trafico = total['trafico_comparable']
    total['conversion'] = round(total['facturas_comparables'] / trafico * 100, 2) if trafico > 0 else None
    return total


def fecha_anterior(valor):
    try:
        return valor.replace(year=valor.year - 1)
    except ValueError:
        return valor.replace(year=valor.year - 1, day=28)


def variacion(actual, anterior):
    if actual is None or anterior is None or anterior == 0:
        return None
    return round((actual - anterior) / anterior * 100, 2)


def comparacion(actual, anterior):
    return {'actual': actual, 'anterior': anterior, 'variacion': variacion(actual, anterior)}


def consulta_base(tienda_ids, f, desde, hasta, corte):
    q = db.session.query(H, Store.codigo, Store.nombre).join(
        Store, H.store_id == Store.id
    ).filter(H.store_id.in_(tienda_ids), H.fecha >= desde, H.fecha <= hasta,
             H.hora.between(f['hora_desde'], f['hora_hasta']))
    if corte:
        q = q.filter(H.fecha <= corte)
    if f['tienda'] is not None:
        q = q.filter(H.store_id == f['tienda'])
    if f['calidad'] == 'validos':
        q = q.filter(H.sensor_error.is_(False))
    return q


def consulta_diaria(tienda_ids, f, desde, hasta, corte):
    """Último registro activo por tienda/fecha para complementar el día completo."""
    if (f['hora_desde'], f['hora_hasta']) != (0, 23):
        return []
    desde_num = desde.year * 10000 + desde.month * 100 + desde.day
    hasta_num = hasta.year * 10000 + hasta.month * 100 + hasta.day
    numero_fecha = ConversionDiaria.anio * 10000 + ConversionDiaria.mes * 100 + ConversionDiaria.dia
    q = db.session.query(ConversionDiaria, Store.codigo, Store.nombre).join(
        Store, ConversionDiaria.store_id == Store.id
    ).filter(ConversionDiaria.store_id.in_(tienda_ids), ConversionDiaria.activo.is_(True),
             numero_fecha.between(desde_num, hasta_num))
    if f['tienda'] is not None:
        q = q.filter(ConversionDiaria.store_id == f['tienda'])
    vistos, resultado = set(), []
    contenido = func.coalesce(ConversionDiaria.trafico, 0) + func.coalesce(ConversionDiaria.facturas, 0)
    for fila, codigo, nombre in q.order_by(
            contenido.desc(), ConversionDiaria.fecha_carga.desc(), ConversionDiaria.id.desc()).all():
        try:
            fecha = date(fila.anio, fila.mes, fila.dia)
        except (TypeError, ValueError):
            continue
        clave = (fila.store_id, fecha)
        if clave in vistos or f['dia'] is not None and fecha.weekday() != f['dia']:
            continue
        vistos.add(clave)
        resultado.append((SimpleNamespace(store_id=fila.store_id, fecha=fecha,
            trafico=fila.trafico, facturas=fila.facturas, sensor_error=False), codigo, nombre))
    return resultado


def ventas_diarias_disponibles(tienda_ids, f, desde, hasta):
    """Ventas por tienda/fecha usando la versión diaria más reciente disponible."""
    anios = set(range(desde.year, hasta.year + 1))
    anios_fuente = anios | {anio + 1 for anio in anios}
    query = DailySales.query.filter(
        DailySales.store_id.in_(tienda_ids),
        DailySales.anio.in_(anios_fuente),
    )
    if f['tienda'] is not None:
        query = query.filter(DailySales.store_id == f['tienda'])

    elegidos = {}
    for fila in query.all():
        candidatos = (
            (fila.anio, fila.venta_2026),
            (fila.anio - 1, fila.venta_2025),
        )
        for anio_objetivo, venta in candidatos:
            try:
                fecha = date(anio_objetivo, fila.mes, fila.dia)
            except (TypeError, ValueError):
                continue
            if not desde <= fecha <= hasta:
                continue
            if f['dia'] is not None and fecha.weekday() != f['dia']:
                continue
            clave = (fila.store_id, fecha)
            prioridad = (fila.dia_corte or -1, fila.id)
            if clave not in elegidos or prioridad > elegidos[clave][0]:
                elegidos[clave] = (prioridad, float(venta or 0))
    return {clave: valor for clave, (_, valor) in elegidos.items()}


def _periodo(tienda_ids, f, desde, hasta, corte, nombres, con_detalle=False):
    total, stores = acumulador(), defaultdict(acumulador)
    daily, week, hours = defaultdict(acumulador), defaultdict(acumulador), defaultdict(acumulador)
    historico_diario = defaultdict(acumulador)
    for fila, codigo, nombre in consulta_base(tienda_ids, f, desde, hasta, corte).yield_per(2000):
        if f['dia'] is not None and fila.fecha.weekday() != f['dia']:
            continue
        nombres[fila.store_id] = dict(codigo=codigo, nombre=nombre)
        acumular(total, fila)
        acumular(stores[fila.store_id], fila)
        acumular(historico_diario[(fila.store_id, fila.fecha)], fila)
        if con_detalle:
            acumular(daily[fila.fecha.isoformat()], fila)
            acumular(week[(fila.fecha.weekday(), fila.hora)], fila)
            acumular(hours[(fila.store_id, fila.hora)], fila)
    for fila, codigo, nombre in consulta_diaria(tienda_ids, f, desde, hasta, corte):
        nombres[fila.store_id] = dict(codigo=codigo, nombre=nombre)
        if not corte or fila.fecha > corte:
            acumular(total, fila, 'dia')
            acumular(stores[fila.store_id], fila, 'dia')
            acumular(historico_diario[(fila.store_id, fila.fecha)], fila, 'dia')
            if con_detalle:
                acumular(daily[fila.fecha.isoformat()], fila, 'dia')
            continue
        historico = historico_diario.get((fila.store_id, fila.fecha))
        if historico and historico['facturas'] is None:
            for destino in (total, stores[fila.store_id]):
                completar_facturas_diarias(destino, fila.facturas, historico['trafico'])
            completar_facturas_diarias(historico, fila.facturas, historico['trafico'])
            if con_detalle:
                completar_facturas_diarias(
                    daily[fila.fecha.isoformat()], fila.facturas, historico['trafico'])
    return total, stores, daily, week, hours, historico_diario


def obtener_panel(tienda_ids, f):
    desde, hasta = date.fromisoformat(f['desde']), date.fromisoformat(f['hasta'])
    corte = _fecha_corte_historico()
    nombres = {t.id: dict(codigo=t.codigo, nombre=t.nombre)
               for t in Store.query.filter(Store.id.in_(tienda_ids)).all()}
    totals, stores, daily, week, hours, store_daily = _periodo(
        tienda_ids, f, desde, hasta, corte, nombres, True)
    anterior_desde, anterior_hasta = fecha_anterior(desde), fecha_anterior(hasta)
    anterior_total, anteriores, _, _, _, _ = _periodo(
        tienda_ids, f, anterior_desde, anterior_hasta, corte, nombres, False)
    actual_total, anterior_total = finalizar(totals), finalizar(anterior_total)

    ventas = ventas_diarias_disponibles(tienda_ids, f, desde, hasta)
    ventas_ticket = 0.0
    facturas_ticket = 0.0
    dias_tienda_ticket = 0
    ventas_por_fecha = defaultdict(float)
    facturas_por_fecha = defaultdict(float)
    ventas_por_tienda = defaultdict(float)
    facturas_por_tienda = defaultdict(float)
    dias_ticket_por_tienda = defaultdict(int)
    for clave, venta in ventas.items():
        detalle = store_daily.get(clave)
        if not detalle or detalle['facturas'] is None:
            continue
        facturas = float(detalle['facturas'] or 0)
        ventas_ticket += venta
        facturas_ticket += facturas
        dias_tienda_ticket += 1
        ventas_por_fecha[clave[1].isoformat()] += venta
        facturas_por_fecha[clave[1].isoformat()] += facturas
        ventas_por_tienda[clave[0]] += venta
        facturas_por_tienda[clave[0]] += facturas
        dias_ticket_por_tienda[clave[0]] += 1

    actual_total['ventas_ticket'] = round(ventas_ticket, 2) if dias_tienda_ticket else None
    actual_total['ticket_promedio'] = (
        round(ventas_ticket / facturas_ticket, 2)
        if facturas_ticket > 0 else None
    )
    actual_total['ticket_dias_tienda'] = dias_tienda_ticket
    for fecha, detalle in daily.items():
        venta = ventas_por_fecha.get(fecha)
        facturas = facturas_por_fecha.get(fecha)
        detalle['venta'] = round(venta, 2) if fecha in ventas_por_fecha else None
        detalle['ticket_promedio'] = (
            round(venta / facturas, 2)
            if facturas and fecha in ventas_por_fecha else None
        )
    for store_id, detalle in stores.items():
        ventas_store = ventas_por_tienda.get(store_id, 0)
        facturas_store = facturas_por_tienda.get(store_id, 0)
        detalle['ticket_promedio'] = (
            round(ventas_store / facturas_store, 2)
            if facturas_store > 0 else None
        )
        detalle['ticket_dias_tienda'] = dias_ticket_por_tienda.get(store_id, 0)

    comparacion_tiendas = []
    for store_id in sorted(set(stores) | set(anteriores)):
        actual = finalizar(stores.get(store_id, acumulador()))
        anterior = finalizar(anteriores.get(store_id, acumulador()))
        comparacion_tiendas.append(dict(id=store_id, **nombres[store_id],
            trafico=comparacion(actual['trafico'], anterior['trafico']),
            facturas=comparacion(actual['facturas'], anterior['facturas'])))
    dia_completo = (f['hora_desde'], f['hora_hasta']) == (0, 23)
    return dict(filtros=f, resumen=actual_total,
        fuentes=dict(fecha_corte_historico=corte.isoformat() if corte else None,
                     diario_posterior_incluido=dia_completo,
                     granularidad_horaria_hasta=corte.isoformat() if corte else None),
        diario=[dict(fecha=k, **finalizar(v)) for k, v in sorted(daily.items())],
        semana_hora=[dict(dia=k[0], hora=k[1], **finalizar(v)) for k, v in sorted(week.items())],
        tiendas=[dict(id=k, **nombres[k], **finalizar(v)) for k, v in sorted(stores.items())],
        tienda_hora=[dict(tienda=k[0], hora=k[1], **finalizar(v)) for k, v in sorted(hours.items())],
        comparacion=dict(
            periodo_actual={'desde': desde.isoformat(), 'hasta': hasta.isoformat()},
            periodo_anterior={'desde': anterior_desde.isoformat(), 'hasta': anterior_hasta.isoformat()},
            total={'trafico': comparacion(actual_total['trafico'], anterior_total['trafico']),
                   'facturas': comparacion(actual_total['facturas'], anterior_total['facturas'])},
            tiendas=comparacion_tiendas))
