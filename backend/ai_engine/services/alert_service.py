"""
Servicio de alertas inteligentes.
Genera alertas consolidadas y relevantes para el dashboard IA.
Incluye alertas por tienda (críticas) y por línea (variaciones significativas).
"""

from sqlalchemy import text
from ai_engine.utils.db import get_engine


def _float(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def generar_alertas(anio, mes):
    """
    Genera alertas para el periodo anio/mes indicado.
    Devuelve una lista de diccionarios con:
        tipo, tienda, mensaje, severidad
    """
    engine = get_engine()
    alertas = []

    # ======================================================
    # 1. ALERTAS POR TIENDA (solo críticas)
    # ======================================================
    query_tiendas = text("""
        SELECT
            s.nombre AS tienda,
            c.store_id,
            c.venta_actual,
            c.cumplimiento_pct,
            c.trafico,
            c.facturas,
            c.ticket_promedio,
            c.conversion
        FROM compliance c
        JOIN stores s ON s.id = c.store_id
        WHERE c.anio = :anio
          AND c.mes = :mes
          AND c.activo = true
          AND s.nombre != 'TOTAL'
        ORDER BY c.cumplimiento_pct ASC
    """)

    with engine.connect() as conn:
        tiendas = conn.execute(query_tiendas, {"anio": anio, "mes": mes}).fetchall()

    for fila in tiendas:
        tienda = fila.tienda
        cumpl = _float(fila.cumplimiento_pct) * 100
        conversion = _float(fila.conversion) * 100
        ticket = _float(fila.ticket_promedio)
        venta = _float(fila.venta_actual)

        if cumpl < 40 and venta > 0:
            alertas.append({
                "tipo": "CUMPLIMIENTO CRITICO",
                "tienda": tienda,
                "mensaje": f"{tienda} tiene cumplimiento del {cumpl:.1f}%.",
                "severidad": "danger"
            })

        if conversion < 5 and venta > 0:
            alertas.append({
                "tipo": "CONVERSION MUY BAJA",
                "tienda": tienda,
                "mensaje": f"{tienda} tiene conversión del {conversion:.2f}%.",
                "severidad": "warning"
            })

        if venta == 0:
            alertas.append({
                "tipo": "SIN VENTAS",
                "tienda": tienda,
                "mensaje": f"{tienda} no registra ventas en el periodo.",
                "severidad": "danger"
            })

    # ======================================================
    # 2. ALERTAS POR LÍNEA (consolidadas globalmente)
    # ======================================================
    # Suma total por línea para el mes actual
    query_lineas_actual = text("""
        SELECT
            l.nombre AS linea,
            SUM(shl.venta) AS venta_total
        FROM sales_history_lines shl
        JOIN lines l ON l.id = shl.line_id
        WHERE shl.anio = :anio
          AND shl.mes = :mes
          AND shl.line_id IN (1,2,3,4)
        GROUP BY l.nombre
    """)

    with engine.connect() as conn:
        lineas_actual = conn.execute(query_lineas_actual, {"anio": anio, "mes": mes}).fetchall()

    # Suma total por línea para el año anterior mismo mes
    anio_ant = anio - 1
    query_lineas_ant = text("""
        SELECT
            l.nombre AS linea,
            SUM(shl.venta) AS venta_total
        FROM sales_history_lines shl
        JOIN lines l ON l.id = shl.line_id
        WHERE shl.anio = :anio_ant
          AND shl.mes = :mes
          AND shl.line_id IN (1,2,3,4)
        GROUP BY l.nombre
    """)

    with engine.connect() as conn:
        lineas_ant = conn.execute(query_lineas_ant, {"anio_ant": anio_ant, "mes": mes}).fetchall()

    # Convertir a diccionario
    ventas_ant = {fila[0]: _float(fila[1]) for fila in lineas_ant}

    for fila in lineas_actual:
        nombre = fila[0]
        venta_act = _float(fila[1])
        venta_ant = ventas_ant.get(nombre, 0)

        if venta_ant > 0:
            variacion = (venta_act - venta_ant) / venta_ant * 100
            if variacion < -15:
                alertas.append({
                    "tipo": "LINEA CAE",
                    "tienda": "Global",
                    "mensaje": f"Línea {nombre} cae {variacion:.1f}% respecto al año anterior (${venta_ant:,.0f} -> ${venta_act:,.0f}).",
                    "severidad": "danger"
                })
            elif variacion > 20:
                alertas.append({
                    "tipo": "LINEA SUBE",
                    "tienda": "Global",
                    "mensaje": f"Línea {nombre} crece {variacion:.1f}% respecto al año anterior (${venta_ant:,.0f} -> ${venta_act:,.0f}).",
                    "severidad": "success"
                })

    # ======================================================
    # 3. LIMITAR ALERTAS A LAS 15 MÁS IMPORTANTES
    # ======================================================
    orden = {"danger": 0, "warning": 1, "success": 2}
    alertas.sort(key=lambda x: orden.get(x["severidad"], 3))
    alertas = alertas[:15]

    return alertas