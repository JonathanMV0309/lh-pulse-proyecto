"""Agregaciones exclusivas del V2, adaptadas del servicio original recibido.
El servicio original y sus consumidores permanecen intactos.
"""
from sqlalchemy import func
from app.services.dashboard_geografico_v2_periodos import resolver_periodo, registros_del_corte, opciones_periodo
from app.services.dashboard_geografico_v2_service import _calcular_score

from app.extensions import db
from app.models.store import Store
from app.models.compliance import Compliance
from app.models.sales_history_line import SalesHistoryLine
from app.models.line import Line

ACTIVO = True

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


def obtener_dashboard_geografico(
    anio=None,
    mes=None,
    ciudad=None,
    clima=None,
    tienda_id=None,
    dia_corte=None,
    periodo=None
):
    """
    Dashboard geográfico de LH_SCORE.

    Filtros:
        ciudad:
            Todas / nombre de ciudad / Global

        clima:
            Todos / Frío / Templado / Cálido / Global

    Se usa un corte común, incluyendo archivados cuando se seleccionan explícitamente.
    Se excluye la fila TOTAL.
    S-03 (Tienda Virtual) participa como Global.
    """

    # ==========================================================
    # 1. DETERMINAR PERÍODO
    # ==========================================================

    seleccion = resolver_periodo(anio, mes, dia_corte, periodo)
    anio, mes = seleccion['anio'], seleccion['mes']

    # ==========================================================
    # 2. NORMALIZAR FILTROS
    # ==========================================================

    if ciudad in ("", "Todas", "TODAS", None):
        ciudad = None

    if clima in ("", "Todos", "TODOS", None):
        clima = None

    # ==========================================================
    # 3. TIENDAS FÍSICAS / GLOBAL
    # ==========================================================

    tiendas_query = (
        Store.query
        .filter(
            Store.estado == "ACTIVA",
            Store.nombre != "TOTAL"
        )
    )

    if ciudad:
        tiendas_query = tiendas_query.filter(
            Store.ciudad == ciudad
        )

    if clima:
        tiendas_query = tiendas_query.filter(
            Store.clima == clima
        )

    if tienda_id:
        tiendas_query = tiendas_query.filter(Store.id == int(tienda_id))

    tiendas = (
        tiendas_query
        .order_by(Store.codigo)
        .all()
    )

    store_ids = [
        tienda.id
        for tienda in tiendas
    ]

    # ==========================================================
    # 4. DATOS DE COMPLIANCE DEL PERÍODO
    # ==========================================================

    registros = registros_del_corte(seleccion, store_ids)

    # ==========================================================
    # 5. KPIs
    # ==========================================================

    # ======================================================
    # TOTAL se mantiene sólo sin filtros; con filtros se agregan tiendas.
    # ======================================================

    totales = registros_del_corte(seleccion, solo_total=True)
    total_compliance = totales[0] if totales else None
    usar_total = not (ciudad or clima or tienda_id) and total_compliance is not None
    ventas = _float(total_compliance.venta_actual) if usar_total else sum(_float(r.venta_actual) for r in registros)
    venta_anterior = _float(total_compliance.venta_anterior) if usar_total else sum(_float(r.venta_anterior) for r in registros)

    # ----------------------------------------------------------
    # CUMPLIMIENTO
    # ----------------------------------------------------------

    cumplimiento_valores = [
        float(reg.cumplimiento_pct or 0)
        for reg in registros
    ]

    cumplimiento = (
        sum(cumplimiento_valores)
        / len(cumplimiento_valores)
        if cumplimiento_valores
        else 0
    )

    # ----------------------------------------------------------
    # VARIACIÓN
    # ----------------------------------------------------------

    if venta_anterior > 0:

        variacion = (
            (ventas - venta_anterior)
            / venta_anterior
        ) * 100

    else:

        variacion = 0

    # ----------------------------------------------------------
    # TRÁFICO Y FACTURAS (misma fuente que las ventas)
    # ----------------------------------------------------------

    trafico = _int(total_compliance.trafico) if usar_total else sum(_int(r.trafico) for r in registros)
    facturas = _int(total_compliance.facturas) if usar_total else sum(_int(r.facturas) for r in registros)

    # ----------------------------------------------------------
    # CONVERSIÓN
    # ----------------------------------------------------------

    conversion = (
        (facturas / trafico) * 100
        if trafico > 0
        else 0
    )

    # ----------------------------------------------------------
    # TICKET PROMEDIO
    # ----------------------------------------------------------

    ticket_promedio = (
        ventas / facturas
        if facturas > 0
        else 0
    )

    # ==========================================================
    # 6. RANKING DE TIENDAS
    # ==========================================================

    ranking_tiendas = []

    mapa_registros = {
        reg.store_id: reg
        for reg in registros
    }

    for tienda in tiendas:

        reg = mapa_registros.get(tienda.id)

        if not reg:
            continue

        ranking_tiendas.append({
            "id": tienda.id,
            "codigo": tienda.codigo,
            "nombre": tienda.nombre,
            "ciudad": tienda.ciudad,
            "clima": tienda.clima,
            "venta_actual": float(
                reg.venta_actual or 0
            ),
            "cumplimiento_pct": float(
                reg.cumplimiento_pct or 0
            ),
            "trafico": int(
                reg.trafico or 0
            ),
            "facturas": int(
                reg.facturas or 0
            ),
            "conversion": float(
                reg.conversion or 0
            ),
            "ticket_promedio": float(
                reg.ticket_promedio or 0
            ),
            "venta_anterior": float(
                reg.venta_anterior or 0
            )
        })

    for item in ranking_tiendas:
        # Mismo score y variación que el mapa, para que la tabla y el mapa coincidan.
        item["score"] = _calcular_score(item)[0]
        anterior = item["venta_anterior"]
        item["variacion"] = (item["venta_actual"] / anterior - 1) * 100 if anterior > 0 else None

    ranking_tiendas.sort(
        key=lambda x: (
            x["cumplimiento_pct"],
            x["venta_actual"]
        ),
        reverse=True
    )

    for posicion, item in enumerate(
        ranking_tiendas,
        start=1
    ):
        item["posicion"] = posicion

    # ==========================================================
    # 7. RANKING POR CIUDAD
    # ==========================================================

    ciudades = {}

    for tienda in tiendas:

        reg = mapa_registros.get(tienda.id)

        if not reg:
            continue

        nombre_ciudad = (
            tienda.ciudad
            or "Sin ciudad"
        )

        if nombre_ciudad not in ciudades:

            ciudades[nombre_ciudad] = {
                "ciudad": nombre_ciudad,
                "tiendas": 0,
                "ventas": 0,
                "venta_anterior": 0,
                "trafico": 0,
                "facturas": 0,
                "cumplimientos": []
            }

        item = ciudades[nombre_ciudad]

        item["tiendas"] += 1

        item["ventas"] += float(
            reg.venta_actual or 0
        )

        item["venta_anterior"] += float(
            reg.venta_anterior or 0
        )

        item["trafico"] += int(
            reg.trafico or 0
        )

        item["facturas"] += int(
            reg.facturas or 0
        )

        item["cumplimientos"].append(
            float(reg.cumplimiento_pct or 0)
        )

    ranking_ciudades = []

    for nombre, item in ciudades.items():

        cumplimiento_ciudad = (
            sum(item["cumplimientos"])
            / len(item["cumplimientos"])
            if item["cumplimientos"]
            else 0
        )

        if item["venta_anterior"] > 0:

            variacion_ciudad = (
                (
                    item["ventas"]
                    - item["venta_anterior"]
                )
                / item["venta_anterior"]
            ) * 100

        else:

            variacion_ciudad = 0

        conversion_ciudad = (
            (
                item["facturas"]
                / item["trafico"]
            ) * 100
            if item["trafico"] > 0
            else 0
        )

        ticket_ciudad = (
            item["ventas"]
            / item["facturas"]
            if item["facturas"] > 0
            else 0
        )

        ranking_ciudades.append({
            "ciudad": nombre,
            "tiendas": item["tiendas"],
            "ventas": item["ventas"],
            "venta_anterior": item["venta_anterior"],
            "variacion": variacion_ciudad,
            "cumplimiento": cumplimiento_ciudad,
            "trafico": item["trafico"],
            "facturas": item["facturas"],
            "conversion": conversion_ciudad,
            "ticket_promedio": ticket_ciudad
        })

    ranking_ciudades.sort(
        key=lambda x: (
            x["cumplimiento"],
            x["ventas"]
        ),
        reverse=True
    )

    for posicion, item in enumerate(
        ranking_ciudades,
        start=1
    ):
        item["posicion"] = posicion

    ventas_ciudades = sum(i["ventas"] for i in ranking_ciudades)
    for item in ranking_ciudades:
        item["venta_promedio"] = item["ventas"] / item["tiendas"] if item["tiendas"] else 0
        item["participacion"] = item["ventas"] / ventas_ciudades * 100 if ventas_ciudades > 0 else 0
        item["muestra_pequena"] = item["tiendas"] < 3
        item["base_comparable"] = item["venta_anterior"] > 0

    # ==========================================================
    # 8. RESUMEN POR CLIMA
    # ==========================================================

    climas = {}

    for tienda in tiendas:

        reg = mapa_registros.get(tienda.id)

        if not reg:
            continue

        nombre_clima = (
            tienda.clima
            or "Sin clima"
        )

        if nombre_clima not in climas:

            climas[nombre_clima] = {
                "clima": nombre_clima,
                "tiendas": 0,
                "ventas": 0,
                "trafico": 0,
                "facturas": 0,
                "cumplimientos": []
            }

        item = climas[nombre_clima]

        item["tiendas"] += 1

        item["ventas"] += float(
            reg.venta_actual or 0
        )

        item["trafico"] += int(
            reg.trafico or 0
        )

        item["facturas"] += int(
            reg.facturas or 0
        )

        item["cumplimientos"].append(
            float(reg.cumplimiento_pct or 0)
        )

    resumen_climas = []

    for nombre, item in climas.items():

        cumplimiento_clima = (
            sum(item["cumplimientos"])
            / len(item["cumplimientos"])
            if item["cumplimientos"]
            else 0
        )

        conversion_clima = (
            (
                item["facturas"]
                / item["trafico"]
            ) * 100
            if item["trafico"] > 0
            else 0
        )

        resumen_climas.append({
            "clima": nombre,
            "tiendas": item["tiendas"],
            "ventas": item["ventas"],
            "trafico": item["trafico"],
            "facturas": item["facturas"],
            "conversion": conversion_clima,
            "cumplimiento": cumplimiento_clima
        })

    resumen_climas.sort(
        key=lambda x: x["ventas"],
        reverse=True
    )

    # ==========================================================
    # 9. EVOLUCIÓN DE VENTAS POR LÍNEA
    # ==========================================================

    evolucion_lineas = []

    if store_ids and anio is not None:

        lineas_anteriores = (
            db.session.query(
                SalesHistoryLine.line_id,
                func.sum(SalesHistoryLine.venta).label("total_venta")
            )
            .filter(
                SalesHistoryLine.store_id.in_(store_ids),
                SalesHistoryLine.anio == anio - 1,
                SalesHistoryLine.mes == mes
            )
            .group_by(SalesHistoryLine.line_id)
            .all()
        )

        lineas_actuales = (
            db.session.query(
                SalesHistoryLine.line_id,
                func.sum(SalesHistoryLine.venta).label("total_venta")
            )
            .filter(
                SalesHistoryLine.store_id.in_(store_ids),
                SalesHistoryLine.anio == anio,
                SalesHistoryLine.mes == mes
            )
            .group_by(SalesHistoryLine.line_id)
            .all()
        )

        ventas_anteriores = {line_id: float(total or 0) for line_id, total in lineas_anteriores}
        ventas_actuales = {line_id: float(total or 0) for line_id, total in lineas_actuales}

        todos_ids = set(ventas_anteriores.keys()) | set(ventas_actuales.keys())

        if todos_ids:
            lineas_nombres = (
                db.session.query(Line.id, Line.nombre)
                .filter(Line.id.in_(todos_ids))
                .all()
            )
            nombres = {line_id: nombre for line_id, nombre in lineas_nombres}

            for line_id in sorted(todos_ids):
                venta_base = ventas_anteriores.get(line_id, 0)
                venta_comparada = ventas_actuales.get(line_id, 0)

                diferencia = venta_comparada - venta_base

                if venta_base > 0:
                    crecimiento = (diferencia / venta_base) * 100
                else:
                    crecimiento = 0

                if crecimiento > 0:
                    estado = "CRECIMIENTO"
                elif crecimiento < 0:
                    estado = "DISMINUCIÓN"
                else:
                    estado = "SIN VARIACIÓN"

                evolucion_lineas.append({
                    "line_id": line_id,
                    "linea": nombres.get(line_id, "Sin línea"),
                    "venta_anterior": venta_base,
                    "venta_actual": venta_comparada,
                    "diferencia": diferencia,
                    "crecimiento": crecimiento if venta_base > 0 else None,
                    "estado": estado if venta_base > 0 else "SIN BASE COMPARABLE"
                })

            evolucion_lineas.sort(
                key=lambda x: x["venta_actual"],
                reverse=True
            )

    # ==========================================================
    # 10. OPCIONES DE FILTRO
    # ==========================================================

    ciudades_disponibles = [
        row[0]
        for row in (
            db.session.query(Store.ciudad)
            .filter(
                Store.estado == "ACTIVA",
                Store.nombre != "TOTAL",
                Store.ciudad.isnot(None)
            )
            .distinct()
            .order_by(Store.ciudad)
            .all()
        )
    ]

    climas_disponibles = [
        row[0]
        for row in (
            db.session.query(Store.clima)
            .filter(
                Store.estado == "ACTIVA",
                Store.nombre != "TOTAL",
                Store.clima.isnot(None)
            )
            .distinct()
            .order_by(Store.clima)
            .all()
        )
    ]

    # ==========================================================
    # 11. RESULTADO
    # ==========================================================

    return {
        "periodo_anio": anio,
        "periodo_mes": mes,

        "ciudad_seleccionada": ciudad,
        "clima_seleccionado": clima,

        "tiendas": len(registros),
        "tiendas_sin_datos": len(tiendas) - len(registros),
        "tienda_seleccionada": tienda_id,
        "periodo_seleccionado": seleccion['periodo'],
        "periodo_label": seleccion['label'],
        "dia_corte": seleccion['dia_corte'],
        "periodos_disponibles": opciones_periodo(),
        "fuente_kpis": "Fila TOTAL del corte" if usar_total else "Tiendas seleccionadas con datos",
        "diferencia_total": ventas - sum(_float(r.venta_actual) for r in registros) if usar_total else 0,
        "base_comparable": venta_anterior > 0,
        "anio_anterior": anio - 1 if anio else None,
        "tiendas_disponibles": [{"id": t.id, "nombre": t.nombre} for t in Store.query.filter(Store.estado == "ACTIVA", Store.nombre != "TOTAL").order_by(Store.codigo).all()],

        "ventas": ventas,
        "venta_anterior": venta_anterior,
        "variacion": variacion,

        "cumplimiento": cumplimiento,

        "trafico": trafico,
        "facturas": facturas,
        "conversion": conversion,
        "ticket_promedio": ticket_promedio,

        "ranking_ciudades": ranking_ciudades,
        "ranking_tiendas": ranking_tiendas,
        "resumen_climas": resumen_climas,
        "evolucion_lineas": evolucion_lineas,

        "ciudades_disponibles": ciudades_disponibles,
        "climas_disponibles": climas_disponibles
    }