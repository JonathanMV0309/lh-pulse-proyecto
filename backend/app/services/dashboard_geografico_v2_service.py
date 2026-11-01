# services/dashboard_geografico_v2_service.py

import math
import unicodedata
from app.services.dashboard_geografico_v2_periodos import resolver_periodo, registros_del_corte
from app.services.dashboard_geografico_v2_external_service import obtener_contexto_externo
from flask import current_app

from app.extensions import db
from app.models.store import Store
from app.models.compliance import Compliance

# =========================================================
# CONFIGURACIÓN DE PESOS PARA OPPORTUNITY SCORE (solo internos)
# =========================================================
PESOS_SCORE = {
    "ventas": 0.30,
    "cumplimiento": 0.30,
    "conversion": 0.25,
    "trafico": 0.15,
}

# =========================================================
# COORDENADAS DE FALLBACK POR CIUDAD
# (solo se usan si la tienda no tiene lat/lng en BD)
# =========================================================
COORDENADAS_CIUDADES = {
    "BOGOTA": (4.6097, -74.0817),
    "BOGOTÁ": (4.6097, -74.0817),
    "MEDELLIN": (6.2442, -75.5812),
    "MEDELLÍN": (6.2442, -75.5812),
    "CALI": (3.4516, -76.5320),
    "BARRANQUILLA": (10.9685, -74.7813),
    "CARTAGENA": (10.3910, -75.4794),
    "CÚCUTA": (7.8939, -72.5078),
    "BUCARAMANGA": (7.1193, -73.1227),
    "PEREIRA": (4.8133, -75.6961),
    "MANIZALES": (5.0703, -75.5138),
    "IBAGUÉ": (4.4389, -75.2322),
    "SANTA MARTA": (11.2408, -74.1990),
    "VILLAVICENCIO": (4.1420, -73.6266),
    "PASTO": (1.2136, -77.2811),
    "MONTERÍA": (8.7480, -75.8814),
    "NEIVA": (2.9273, -75.2819),
    "ARMENIA": (4.5339, -75.6811),
    "SINCELEJO": (9.3047, -75.3978),
    "VALLEDUPAR": (10.4631, -73.2532),
    "SOACHA": (4.5793, -74.2158),
    "CHIA": (4.8616, -74.0600),
    "BARRANCABERMEJA": (7.0653, -73.8547),
    "GLOBAL": (4.5709, -74.2973),
}

def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto or '').upper().strip()) if not unicodedata.combining(c))


def _ubicacion(tienda):
    virtual = _normalizar(tienda.codigo).replace(' ', '') == 'S-03' or _normalizar(tienda.ciudad) == 'GLOBAL'
    if virtual:
        return None, None, 'virtual'
    try:
        lat, lng = float(tienda.lat), float(tienda.lng)
        if math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng, 'tienda'
    except (TypeError, ValueError, AttributeError, OverflowError):
        pass
    ciudades = {_normalizar(k): v for k, v in COORDENADAS_CIUDADES.items() if k != 'GLOBAL'}
    coordenadas = ciudades.get(_normalizar(tienda.ciudad))
    return (*coordenadas, 'ciudad') if coordenadas else (None, None, 'sin_ubicacion')


def _get_coordenadas(tienda):
    return _ubicacion(tienda)[:2]


# =========================================================
# CALCULAR OPPORTUNITY SCORE (solo datos internos)
# =========================================================
def _calcular_score(tienda_data):
    """
    Calcula un Opportunity Score 0-100 basado SOLO en datos internos.
    Factores: ventas, cumplimiento, conversión, tráfico.
    """
    score = 0.0
    detalle = {}

    # Ventas normalizadas (máximo esperado: 100M)
    ventas = float(tienda_data.get("venta_actual", 0))
    ventas_norm = max(0, min(ventas / 100000000 * 100, 100))
    detalle["ventas"] = round(ventas_norm, 1)

    # Cumplimiento (0-100)
    cumplimiento = float(tienda_data.get("cumplimiento_pct", 0)) * 100
    detalle["cumplimiento"] = round(max(0, min(cumplimiento, 100)), 1)

    # Conversión (40% = excelente)
    conversion = float(tienda_data.get("conversion", 0))
    conversion_norm = max(0, min(conversion / 40 * 100, 100))
    detalle["conversion"] = round(conversion_norm, 1)

    # Tráfico (10,000 visitas = 100 puntos)
    trafico = int(tienda_data.get("trafico", 0))
    trafico_norm = max(0, min(trafico / 10000 * 100, 100))
    detalle["trafico"] = round(trafico_norm, 1)

    # Cálculo ponderado
    for factor, peso in PESOS_SCORE.items():
        score += detalle[factor] * peso

    score = round(min(score, 100), 1)
    return score, detalle

# =========================================================
# OBTENER TIENDAS PARA EL MAPA
# =========================================================
def obtener_tiendas_para_mapa(anio=None, mes=None, ciudad=None, clima=None, tienda_id=None, dia_corte=None, periodo=None):
    """
    Devuelve listado de tiendas con coordenadas, ventas, cumplimiento y score.
    NO depende de APIs externas.
    """
    seleccion = resolver_periodo(anio, mes, dia_corte, periodo)
    if seleccion['anio'] is None:
        return []
    tiendas_query = Store.query.filter(
        Store.estado == "ACTIVA",
        Store.nombre != "TOTAL"
    )
    if ciudad:
        tiendas_query = tiendas_query.filter(Store.ciudad == ciudad)
    if clima:
        tiendas_query = tiendas_query.filter(Store.clima == clima)

    if tienda_id:
        tiendas_query = tiendas_query.filter(Store.id == int(tienda_id))
    tiendas = tiendas_query.all()
    if not tiendas:
        return []

    store_ids = [t.id for t in tiendas]
    registros = registros_del_corte(seleccion, store_ids)

    mapa_reg = {r.store_id: r for r in registros}

    tiendas_data = []
    for t in tiendas:
        reg = mapa_reg.get(t.id)
        if not reg:
            continue

        lat, lng, precision = _ubicacion(t)

        tienda_info = {
            "id": t.id,
            "nombre": t.nombre,
            "codigo": t.codigo,
            "ciudad": t.ciudad,
            "clima": t.clima,
            "lat": lat,
            "lng": lng,
            "precision_ubicacion": precision,
            "es_virtual": precision == 'virtual',
            "periodo": seleccion['label'],
            "venta_anterior": float(reg.venta_anterior or 0),
            "venta_actual": float(reg.venta_actual or 0),
            "cumplimiento_pct": float(reg.cumplimiento_pct or 0),
            "conversion": float(reg.conversion or 0),
            "trafico": int(reg.trafico or 0),
            "facturas": int(reg.facturas or 0),
            "ticket_promedio": float(reg.ticket_promedio or 0),
        }

        score, detalle = _calcular_score(tienda_info)
        tienda_info["score"] = score
        tienda_info["score_detalle"] = detalle

        tiendas_data.append(tienda_info)

    tiendas_data.sort(key=lambda x: x["score"], reverse=True)
    return tiendas_data

# =========================================================
# OBTENER CONTEXTO COMPLETO PARA UNA TIENDA
# =========================================================
def obtener_contexto_tienda(store_id, anio=None, mes=None, ciudad=None, clima=None, tienda_id=None, dia_corte=None, periodo=None, incluir_externo=True, solo_externo=False):
    """
    Devuelve datos comerciales y, opcionalmente, contexto externo bajo demanda.
    """
    tienda = Store.query.get(store_id)
    if (not tienda or tienda.estado != "ACTIVA" or tienda.nombre == 'TOTAL'
        or (ciudad and tienda.ciudad != ciudad) or (clima and tienda.clima != clima)
        or (tienda_id and tienda.id != int(tienda_id))):
        return None

    lat, lng, precision = _ubicacion(tienda)
    if solo_externo:
        return dict(id=tienda.id, **obtener_contexto_externo(lat, lng, precision == 'virtual'))
    seleccion = resolver_periodo(anio, mes, dia_corte, periodo)

    contexto = {
        "id": tienda.id,
        "nombre": tienda.nombre,
        "codigo": tienda.codigo,
        "ciudad": tienda.ciudad,
        "clima_zona": tienda.clima,
        "lat": lat,
        "lng": lng,
        "precision_ubicacion": precision,
        "es_virtual": precision == 'virtual',
        "score_pesos": PESOS_SCORE,
        "periodo_seleccionado": seleccion['periodo'],
        "clima": {"status": "unavailable"},
        "movilidad": {"status": "unavailable"},
        "eventos": [],
        "calidad_aire": {"status": "unavailable"},
    }

    registros = registros_del_corte(seleccion, [store_id])
    compliance = registros[0] if registros else None
    contexto['datos_disponibles'] = compliance is not None

    if compliance:
        contexto.update({
            "venta_actual": float(compliance.venta_actual or 0),
            "cumplimiento_pct": float(compliance.cumplimiento_pct or 0),
            "conversion": float(compliance.conversion or 0),
            "trafico": int(compliance.trafico or 0),
            "facturas": int(compliance.facturas or 0),
            "ticket_promedio": float(compliance.ticket_promedio or 0),
            "periodo": seleccion["label"],
        })
    else:
        contexto.update({
            "venta_actual": 0,
            "cumplimiento_pct": 0,
            "conversion": 0,
            "trafico": 0,
            "facturas": 0,
            "ticket_promedio": 0,
            "periodo": "Sin datos",
        })

    tienda_data_para_score = {
        "venta_actual": contexto["venta_actual"],
        "cumplimiento_pct": contexto["cumplimiento_pct"],
        "conversion": contexto["conversion"],
        "trafico": contexto["trafico"],
    }
    score, detalle = _calcular_score(tienda_data_para_score)
    contexto["score"] = score if compliance else None
    contexto["score_detalle"] = detalle

    # Radar
    radar = {}
    nombres = {
        "ventas": "Ventas",
        "cumplimiento": "Cumplimiento",
        "conversion": "Conversión",
        "trafico": "Tráfico",
    }
    for factor, valor in detalle.items():
        radar[nombres[factor]] = {
            "score": valor,
            "estado": "Favorable" if valor >= 70 else ("Desfavorable" if valor < 40 else "Neutral")
        }
    contexto["radar"] = radar if compliance else {}

    # Lectura automática simple
    lectura = f"La tienda {tienda.nombre} tiene un Opportunity Score de {score}/100."
    if contexto["cumplimiento_pct"] >= 1:
        lectura += " Meta alcanzada según el cumplimiento importado."
    else:
        lectura += " Cumplimiento inferior al 100%; revisar el avance esperado para este corte."
    if contexto["conversion"] < 3:
        lectura += " Conversión baja."
    elif contexto["conversion"] > 10:
        lectura += " Buena conversión."
    contexto["lectura"] = lectura if compliance else "Sin datos comerciales para el corte seleccionado."
    if incluir_externo:
        contexto.update(obtener_contexto_externo(lat, lng, precision == 'virtual'))

    return contexto

# =========================================================
# OBTENER OPORTUNIDADES AUTOMÁTICAS
# =========================================================
def obtener_oportunidades(**filtros):
    tiendas = obtener_tiendas_para_mapa(**filtros)
    oportunidades = []

    for t in tiendas:
        if t["trafico"] > 5000 and t["conversion"] < 10:
            oportunidades.append({
                "titulo": f"Alto tráfico con conversión baja en {t['nombre']}",
                "descripcion": f"{t['ciudad']} - {t['trafico']} visitas, conversión {t['conversion']:.1f}%.",
                "tipo": "warning"
            })
        if t["score"] >= 75:
            oportunidades.append({
                "titulo": f"{t['nombre']} con alto Opportunity Score",
                "descripcion": f"Score {t['score']}/100.",
                "tipo": "success"
            })
        if t["cumplimiento_pct"] >= 1:
            oportunidades.append({
                "titulo": f"{t['nombre']} cumple meta",
                "descripcion": f"Cumplimiento {t['cumplimiento_pct']*100:.1f}%.",
                "tipo": "success"
            })
        if not t['es_virtual'] and t['cumplimiento_pct'] >= 1 and 0 < t['trafico'] < 1000:
            oportunidades.append({'titulo': f"Buen cumplimiento con tráfico reducido en {t['nombre']}",
                'descripcion': f"{t['trafico']} visitas y cumplimiento {t['cumplimiento_pct']*100:.1f}%. Umbral de referencia: menos de 1.000 visitas por corte.", 'tipo': 'info'})
    for item in oportunidades:
        item['evidencia'] = 'Dato comercial'
        item['recomendacion'] = ('Revisar atención, disponibilidad de tallas y cierre de venta.'
            if item['tipo'] == 'warning' else 'Revisar prácticas replicables en tiendas comparables.')
    return oportunidades[:10]

# =========================================================
# OBTENER ALERTAS
# =========================================================
def obtener_alertas(**filtros):
    tiendas = obtener_tiendas_para_mapa(**filtros)
    alertas = []

    for t in tiendas:
        if t["cumplimiento_pct"] < 0.5:
            alertas.append({
                "titulo": f"Cumplimiento crítico en {t['nombre']}",
                "descripcion": f"{t['ciudad']} - cumplimiento {t['cumplimiento_pct']*100:.1f}%.",
                "tipo": "danger"
            })
        if t["trafico"] > 0 and t["conversion"] < 3:
            alertas.append({
                "titulo": f"Conversión muy baja en {t['nombre']}",
                "descripcion": f"{t['ciudad']} - conversión {t['conversion']:.1f}%.",
                "tipo": "warning"
            })
        anterior = t['venta_anterior']
        if anterior > 0 and t['venta_actual'] < anterior and t['cumplimiento_pct'] < 1:
            caida = (t['venta_actual'] / anterior - 1) * 100
            alertas.append({'titulo': f"Ventas en descenso en {t['nombre']}",
                'descripcion': f"Variación {caida:.1f}% frente a la base importada; cumplimiento {t['cumplimiento_pct']*100:.1f}%.",
                'tipo': 'danger'})
    ciudades = {}
    for t in tiendas:
        ciudad = t['ciudad'] or 'Sin ciudad'
        if t['es_virtual']:
            continue
        item = ciudades.setdefault(ciudad, {'ventas': 0, 'tiendas': 0})
        item['ventas'] += t['venta_actual']
        item['tiendas'] += 1
    total_fisico = sum(c['ventas'] for c in ciudades.values())
    if len(ciudades) > 1 and total_fisico > 0:
        for nombre, item in ciudades.items():
            participacion = item['ventas'] / total_fisico * 100
            if participacion >= 60:
                alertas.append({'titulo': f"Concentración de ventas en {nombre}",
                    'descripcion': f"{participacion:.1f}% de las ventas físicas de esta selección, con {item['tiendas']} tienda(s). Interpretar junto al tamaño de la red.",
                    'tipo': 'info'})
    alertas.sort(key=lambda a: 0 if a['tipo'] == 'danger' else 1)
    for item in alertas:
        item['evidencia'] = 'Dato comercial'
        item['recomendacion'] = 'Revisar el avance de la meta, el corte y la comparabilidad de la base antes de actuar.'
    return alertas[:10]

# =========================================================
# DATOS PARA GRÁFICO CLIMA VS VENTAS
# =========================================================
def obtener_analisis_clima_ventas(**filtros):
    tiendas = obtener_tiendas_para_mapa(**filtros)
    clima_ventas = {}
    for t in tiendas:
        clima = t.get("clima") or "Sin clima"
        if clima not in clima_ventas:
            clima_ventas[clima] = 0
        clima_ventas[clima] += t["venta_actual"]
    return {
        "nota": "Agrupación por clima de zona registrado; no mide el efecto del tiempo meteorológico sobre las ventas.",
        "labels": list(clima_ventas.keys()),
        "valores": list(clima_ventas.values())
    }

# =========================================================
# DATOS PARA GRÁFICO TRÁFICO VS VENTAS (SCATTER)
# =========================================================
def obtener_analisis_trafico_ventas(**filtros):
    tiendas = obtener_tiendas_para_mapa(**filtros)
    puntos = []
    for t in tiendas:
        puntos.append({
            "nombre": t["nombre"],
            "trafico": t["trafico"],
            "ventas": t["venta_actual"]
        })
    return {"puntos": puntos}

# =========================================================
# OBTENER COMPARACIÓN DE DOS O MÁS TIENDAS
# =========================================================
def obtener_comparacion(ids, **filtros):
    try:
        seleccionados = list(dict.fromkeys(int(i.strip()) for i in ids.split(',')))
    except (ValueError, AttributeError):
        raise ValueError('IDs inválidos') from None
    if not 2 <= len(seleccionados) <= 8 or any(i <= 0 for i in seleccionados):
        raise ValueError('Selecciona entre 2 y 8 tiendas diferentes')
    # Consulta comercial en bloque: comparar no desencadena llamadas meteorológicas.
    disponibles = {t['id']: t for t in obtener_tiendas_para_mapa(**filtros)}
    if any(i not in disponibles for i in seleccionados):
        raise ValueError('Alguna tienda no tiene datos en los filtros y corte seleccionados')
    tiendas = []
    for i in seleccionados:
        t = disponibles[i]
        tiendas.append({'id': i, 'nombre': t['nombre'], 'ventas': t['venta_actual'],
            'cumplimiento': t['cumplimiento_pct'], 'trafico': t['trafico'],
            'conversion': t['conversion'], 'facturas': t['facturas'],
            'ticket_promedio': t['ticket_promedio'], 'score': t['score'], 'periodo': t['periodo']})
    return {'tiendas': tiendas}
