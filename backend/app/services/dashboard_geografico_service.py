from sqlalchemy import func

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
    clima=None
):
    """
    Dashboard geográfico de LH_SCORE.

    Filtros:
        ciudad:
            Todas / nombre de ciudad / Global

        clima:
            Todos / Frío / Templado / Cálido / Global

    Se utilizan únicamente registros Compliance activos.
    Se excluye la fila TOTAL.
    S-03 (Tienda Virtual) participa como Global.
    """

    # ==========================================================
    # 1. DETERMINAR PERÍODO
    # ==========================================================

    if anio is None or mes is None:

        periodo = (
            db.session.query(
                Compliance.anio,
                Compliance.mes
            )
            .filter(
                Compliance.activo.is_(True)
            )
            .order_by(
                Compliance.anio.desc(),
                Compliance.mes.desc()
            )
            .first()
        )

        if periodo:

            anio = periodo.anio
            mes = periodo.mes

        else:

            return {
                "periodo_anio": None,
                "periodo_mes": None,
                "ciudad_seleccionada": ciudad,
                "clima_seleccionado": clima,
                "tiendas": 0,
                "ventas": 0,
                "venta_anterior": 0,
                "variacion": 0,
                "cumplimiento": 0,
                "trafico": 0,
                "facturas": 0,
                "conversion": 0,
                "ticket_promedio": 0,
                "ranking_ciudades": [],
                "ranking_tiendas": [],
                "resumen_climas": [],
                "evolucion_lineas": [],
                "ciudades_disponibles": [],
                "climas_disponibles": []
            }

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

    if store_ids:

        registros = (
            Compliance.query
            .filter(
                Compliance.store_id.in_(store_ids),
                Compliance.anio == anio,
                Compliance.mes == mes,
                Compliance.activo.is_(True)
            )
            .all()
        )

    else:

        registros = []

    # ==========================================================
    # 5. KPIs
    # ==========================================================

    # ======================================================
    # CORRECCIÓN:
    # Usar la fila TOTAL para ventas y año anterior.
    # ======================================================

    total_compliance = (
        Compliance.query
        .join(Store, Store.id == Compliance.store_id)
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Store.nombre == "TOTAL",
            Compliance.activo == ACTIVO
        )
        .first()
    )

    ventas = _float(total_compliance.venta_actual) if total_compliance else 0.0
    venta_anterior = _float(total_compliance.venta_anterior) if total_compliance else 0.0

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
    # TRÁFICO Y FACTURAS (también desde TOTAL)
    # ----------------------------------------------------------

    trafico = _int(total_compliance.trafico) if total_compliance else 0
    facturas = _int(total_compliance.facturas) if total_compliance else 0

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
            )
        })

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

    if store_ids:

        lineas_2025 = (
            db.session.query(
                SalesHistoryLine.line_id,
                func.sum(SalesHistoryLine.venta).label("total_venta")
            )
            .filter(
                SalesHistoryLine.store_id.in_(store_ids),
                SalesHistoryLine.anio == 2025,
                SalesHistoryLine.mes == mes
            )
            .group_by(SalesHistoryLine.line_id)
            .all()
        )

        lineas_2026 = (
            db.session.query(
                SalesHistoryLine.line_id,
                func.sum(SalesHistoryLine.venta).label("total_venta")
            )
            .filter(
                SalesHistoryLine.store_id.in_(store_ids),
                SalesHistoryLine.anio == 2026,
                SalesHistoryLine.mes == mes
            )
            .group_by(SalesHistoryLine.line_id)
            .all()
        )

        ventas_2025 = {line_id: float(total or 0) for line_id, total in lineas_2025}
        ventas_2026 = {line_id: float(total or 0) for line_id, total in lineas_2026}

        todos_ids = set(ventas_2025.keys()) | set(ventas_2026.keys())

        if todos_ids:
            lineas_nombres = (
                db.session.query(Line.id, Line.nombre)
                .filter(Line.id.in_(todos_ids))
                .all()
            )
            nombres = {line_id: nombre for line_id, nombre in lineas_nombres}

            for line_id in sorted(todos_ids):
                venta_2025 = ventas_2025.get(line_id, 0)
                venta_2026 = ventas_2026.get(line_id, 0)

                diferencia = venta_2026 - venta_2025

                if venta_2025 > 0:
                    crecimiento = (diferencia / venta_2025) * 100
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
                    "venta_2025": venta_2025,
                    "venta_2026": venta_2026,
                    "diferencia": diferencia,
                    "crecimiento": crecimiento,
                    "estado": estado
                })

            evolucion_lineas.sort(
                key=lambda x: x["venta_2026"],
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

        "tiendas": len(tiendas),

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