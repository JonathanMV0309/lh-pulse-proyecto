from calendar import monthrange

from sqlalchemy import func

from app.extensions import db

from app.models import (
    Store,
    Compliance,
    Advisor,
    AdvisorPerformance,
    ConversionDiaria,
    Line,
)

from app.models.meta_line import MetaLine
from app.models.sales_history_line import SalesHistoryLine

from app.services.advisor_goal_service import (
    calcular_metas_asesoras,
    obtener_meta_tienda,
)
from app.services.ventas_diarias_service import construir_resumen_tiendas
from app.services.vpt_service import indicadores_vpt


# ==========================================================
# CONSTANTES
# ==========================================================

ACTIVO = True


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

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


def _calcular_crecimiento(actual, anterior):
    actual = _float(actual)
    anterior = _float(anterior)

    if anterior > 0:
        return (actual - anterior) / anterior

    return 0.0


def _calcular_cumplimiento(venta, meta):
    venta = _float(venta)
    meta = _float(meta)

    if meta > 0:
        return venta / meta

    return 0.0


def _calcular_falta(venta, meta):
    venta = _float(venta)
    meta = _float(meta)

    return max(meta - venta, 0.0)


def _estado_meta(cumplimiento, meta):
    cumplimiento = _float(cumplimiento)
    meta = _float(meta)

    if meta <= 0:
        return "SIN META", "secondary"

    if cumplimiento >= 1:
        return "META SUPERADA", "success"

    if cumplimiento >= 0.90:
        return "CERCA DE LA META", "warning"

    if cumplimiento >= 0.80:
        return "EN PROGRESO", "warning"

    return "POR DEBAJO", "danger"


def debe_excluir_s24(anio, mes):
    """
    Devuelve True si la tienda S-24 debe excluirse.

    S-24 cerró en agosto 2026, por lo que desde ese período
    en adelante ya no aparece.
    """
    if anio is None or mes is None:
        return False

    return (anio, mes) >= (2026, 8)


# ==========================================================
# OBTENER CORTE ACTUAL
# ==========================================================

def _obtener_corte_actual(
    anio=None,
    mes=None,
    dia_corte=None,
    store_id=None,
    store_ids=None
):
    query = Compliance.query

    if store_id is not None:
        query = query.filter(
            Compliance.store_id == store_id
        )

    elif store_ids:
        query = query.filter(
            Compliance.store_id.in_(store_ids)
        )

    if anio is not None:
        query = query.filter(
            Compliance.anio == anio
        )

    if mes is not None:
        query = query.filter(
            Compliance.mes == mes
        )

    # ------------------------------------------------------
    # CORTE ESPECÍFICO
    # ------------------------------------------------------

    if (
        anio is not None
        and mes is not None
        and dia_corte is not None
    ):
        registro = (
            query
            .filter(
                Compliance.dia_corte == dia_corte
            )
            .order_by(
                Compliance.dia_corte.desc(),
                Compliance.id.desc()
            )
            .first()
        )

        if registro:
            return (
                _int(registro.anio),
                _int(registro.mes),
                _int(registro.dia_corte)
            )

        return (
            _int(anio),
            _int(mes),
            _int(dia_corte)
        )

    # ------------------------------------------------------
    # AÑO + MES SIN CORTE
    # ------------------------------------------------------

    if (
        anio is not None
        and mes is not None
    ):
        registro = (
            query
            .filter(
                Compliance.dia_corte.isnot(None)
            )
            .order_by(
                Compliance.dia_corte.desc(),
                Compliance.id.desc()
            )
            .first()
        )

        if registro:
            return (
                _int(registro.anio),
                _int(registro.mes),
                _int(registro.dia_corte)
            )

        return (
            _int(anio),
            _int(mes),
            None
        )

    # ------------------------------------------------------
    # SIN PERÍODO
    # ------------------------------------------------------

    registro = (
        query
        .filter(
            Compliance.anio.isnot(None),
            Compliance.mes.isnot(None),
            Compliance.dia_corte.isnot(None)
        )
        .order_by(
            Compliance.anio.desc(),
            Compliance.mes.desc(),
            Compliance.dia_corte.desc(),
            Compliance.id.desc()
        )
        .first()
    )

    if registro:
        return (
            _int(registro.anio),
            _int(registro.mes),
            _int(registro.dia_corte)
        )

    return None, None, None


# ==========================================================
# FILTRO COMPLIANCE
# ==========================================================

def _filtro_compliance(
    query,
    anio,
    mes,
    dia_corte=None,
    store_id=None,
    store_ids=None
):
    query = query.filter(
        Compliance.anio == anio,
        Compliance.mes == mes
    )

    # Si se selecciona un corte concreto se debe poder consultar
    # aunque esa versión esté marcada como inactiva.
    if dia_corte is not None:
        query = query.filter(
            Compliance.dia_corte == dia_corte
        )
    else:
        query = query.filter(
            Compliance.activo == ACTIVO
        )

    if store_id is not None:
        query = query.filter(
            Compliance.store_id == store_id
        )

    elif store_ids:
        query = query.filter(
            Compliance.store_id.in_(store_ids)
        )

    return query


# ==========================================================
# FILTRO PERFORMANCE
# ==========================================================

def _filtro_performance(
    query,
    anio,
    mes,
    dia_corte=None,
    store_id=None,
    store_ids=None
):
    query = query.filter(
        AdvisorPerformance.anio == anio,
        AdvisorPerformance.mes == mes
    )

    if dia_corte is not None:
        query = query.filter(
            AdvisorPerformance.dia_corte == dia_corte
        )
    else:
        query = query.filter(
            AdvisorPerformance.activo == ACTIVO
        )

    if store_id is not None:
        query = query.filter(
            AdvisorPerformance.store_id == store_id
        )

    elif store_ids:
        query = query.filter(
            AdvisorPerformance.store_id.in_(store_ids)
        )

    return query


# ==========================================================
# PERÍODO ACTUAL
# ==========================================================

def _periodo_actual():
    registro = (
        Compliance.query
        .order_by(
            Compliance.anio.desc(),
            Compliance.mes.desc(),
            Compliance.dia_corte.desc(),
            Compliance.id.desc()
        )
        .first()
    )

    if registro:
        return (
            registro.anio,
            registro.mes,
            registro.dia_corte
        )

    return None, None, None


# ==========================================================
# PERÍODOS DISPONIBLES
# ==========================================================

def obtener_periodos_disponibles(
    store_id=None,
    store_ids=None
):
    query = (
        db.session.query(
            Compliance.anio,
            Compliance.mes
        )
        .filter(
            Compliance.anio.isnot(None),
            Compliance.mes.isnot(None)
        )
        .distinct()
    )

    if store_id is not None:
        query = query.filter(
            Compliance.store_id == store_id
        )

    elif store_ids:
        query = query.filter(
            Compliance.store_id.in_(store_ids)
        )

    return (
        query
        .order_by(
            Compliance.anio.desc(),
            Compliance.mes.desc()
        )
        .all()
    )


# ==========================================================
# CORTES DISPONIBLES
# ==========================================================

def obtener_cortes_disponibles(
    anio,
    mes,
    store_id=None,
    store_ids=None
):
    if anio is None or mes is None:
        return []

    query = (
        db.session.query(
            Compliance.dia_corte
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.dia_corte.isnot(None)
        )
    )

    if store_id is not None:
        query = query.filter(
            Compliance.store_id == store_id
        )

    elif store_ids:
        query = query.filter(
            Compliance.store_id.in_(store_ids)
        )

    registros = (
        query
        .distinct()
        .order_by(
            Compliance.dia_corte.asc()
        )
        .all()
    )

    cortes = []

    for registro in registros:
        dia = _int(registro[0])

        if dia > 0 and dia not in cortes:
            cortes.append(dia)

    return cortes


# ==========================================================
# INFORMACIÓN DE CORTES
# ==========================================================

def obtener_cortes_periodo(
    anio,
    mes,
    store_id=None,
    store_ids=None
):
    dias = obtener_cortes_disponibles(
        anio,
        mes,
        store_id,
        store_ids
    )

    return [
        {
            "dia_corte": dia,
            "anio": anio,
            "mes": mes
        }
        for dia in dias
    ]


# ==========================================================
# METAS ASESORAS
# ==========================================================

def _obtener_metas_asesoras_tienda(store_id, anio, mes):
    if store_id is None:
        return {}
    if anio is None or mes is None:
        return {}

    metas = {}

    # ==================================================
    # 1. PRIORIDAD: METAS MANUALES DESDE advisor_goals
    # ==================================================
    try:
        from app.models.advisor_goal import AdvisorGoal

        goals_manuales = (
            AdvisorGoal.query
            .filter_by(
                store_id=store_id,
                anio=anio,
                mes=mes
            )
            .all()
        )

        for goal in goals_manuales:
            if not goal.advisor_id:
                continue

            meta_manual = _float(goal.meta_venta)

            if meta_manual > 0:
                metas[goal.advisor_id] = meta_manual

    except Exception as e:
        print("ERROR OBTENIENDO METAS MANUALES:", e)

    # ==================================================
    # 2. RELLENAR CON META AUTOMÁTICA SOLO SI NO HAY MANUAL
    # ==================================================
    try:
        meta_tienda = obtener_meta_tienda(store_id, anio, mes)

        resultado = calcular_metas_asesoras(
            store_id=store_id,
            anio=anio,
            mes=mes,
            meta_tienda=meta_tienda
        )

        for asesora in resultado.get("asesoras", []):
            advisor_id = asesora.get("advisor_id")
            if advisor_id is None:
                continue

            if advisor_id in metas:
                continue  # ya tiene meta manual

            meta_calculada = _float(asesora.get("meta", 0))
            metas[advisor_id] = meta_calculada

    except Exception as e:
        print("ERROR CALCULANDO METAS AUTOMÁTICAS:", e)

    return metas


# ==========================================================
# CONSTRUIR DATOS ASESORA
# ==========================================================
def _construir_datos_asesora(
    registro,
    meta_valor,
    posicion=None,
    meta_proporcional=None
):
    if hasattr(registro, "venta"):
        venta = _float(registro.venta)
    else:
        venta = _float(getattr(registro, "total_venta", 0))

    if hasattr(registro, "unidades"):
        unidades = _float(registro.unidades)
    else:
        unidades = _float(getattr(registro, "total_unidades", 0))

    if hasattr(registro, "facturas"):
        facturas = _float(registro.facturas)
    else:
        facturas = _float(getattr(registro, "total_facturas", 0))

    meta_valor = _float(meta_valor)

    ticket = venta / facturas if facturas > 0 else 0.0
    upt = unidades / facturas if facturas > 0 else 0.0

    cumplimiento_meta = _calcular_cumplimiento(venta, meta_valor)

    if meta_proporcional is None:
        meta_proporcional = meta_valor

    cumplimiento_corte = _calcular_cumplimiento(venta, meta_proporcional)

    falta_meta = _calcular_falta(venta, meta_valor)
    estado_meta, clase_meta = _estado_meta(cumplimiento_meta, meta_valor)

    asesor = getattr(registro, "advisor", None)
    if asesor is not None:
        advisor_id = asesor.id
        nombre = asesor.nombre or "Sin nombre"
        es_generico = bool(getattr(asesor, "es_generico", False))
        estado = getattr(asesor, "estado", None)
    else:
        advisor_id = getattr(registro, "advisor_id", None)
        nombre = getattr(registro, "nombre", "Sin nombre")
        es_generico = bool(getattr(registro, "es_generico", False))
        estado = getattr(registro, "estado", None)

    datos = {
        "id": advisor_id,
        "nombre": str(nombre or "Sin nombre"),
        "asesora": str(nombre or "Sin nombre"),
        "venta": venta,
        "unidades": unidades,
        "facturas": facturas,
        "ticket_promedio": ticket,
        "ticket": ticket,
        "upt": upt,
        "meta_valor": meta_valor,
        "meta_venta": meta_valor,
        "meta_corte": meta_proporcional,
        "cumplimiento_meta": cumplimiento_meta,
        "cumplimiento_corte": cumplimiento_corte,
        "cumplimiento_total": cumplimiento_meta,
        "falta_meta": falta_meta,
        "estado_meta": estado_meta,
        "clase_meta": clase_meta,
        "es_generico": es_generico,
        "estado": estado
    }

    if posicion is not None:
        datos["posicion"] = posicion

    return datos

# ==========================================================
# DASHBOARD ADMIN
# ==========================================================

def obtener_dashboard_admin(
    anio=None,
    mes=None,
    dia_corte=None
):
    (
        anio_actual,
        mes_actual,
        dia_corte_actual
    ) = _obtener_corte_actual(
        anio=anio,
        mes=mes,
        dia_corte=dia_corte
    )

    if anio_actual is None:
        return {
            "ventas": 0,
            "venta_anterior": 0,
            "variacion_porcentual": 0,
            "cumplimiento": 0,
            "tiendas": 0,
            "ranking": [],
            "ranking_completo": [],
            "top_ventas": [],
            "top_cumplimiento": [],
            "total_asesoras": 0,
            "venta_asesoras": 0,
            "unidades_asesoras": 0,
            "facturas_asesoras": 0,
            "ticket_promedio_asesoras": 0,
            "upt_asesoras": 0,
            "periodo_anio": None,
            "periodo_mes": None,
            "anio_seleccionado": None,
            "mes_seleccionado": None,
            "dia_corte": None,
            "dia_corte_seleccionado": None,
            "cortes_disponibles": [],
            "periodos_disponibles": obtener_periodos_disponibles(),
            "trafico_total": 0,
            "facturas_total": 0,
            "conversion_global": 0,
            "ticket_promedio_global": 0,
            "dif_acum_global": 0,
            "unidades_global": 0,
            "evolucion_lineas_global": [],
            "ranking_ciudades": [],
            "resumen_climas": [],
            "top_asesoras_global": [],
            "tiendas_criticas": []
        }

    # ======================================================
    # SUBQUERY ÚLTIMO CORTE POR TIENDA
    # ======================================================

    corte_por_tienda_query = (
        db.session.query(
            Compliance.store_id.label("store_id"),
            func.max(
                Compliance.dia_corte
            ).label("max_corte")
        )
        .filter(
            Compliance.anio == anio_actual,
            Compliance.mes == mes_actual
        )
    )

    if dia_corte_actual is not None:
        corte_por_tienda_query = corte_por_tienda_query.filter(
            Compliance.dia_corte == dia_corte_actual
        )
    else:
        corte_por_tienda_query = corte_por_tienda_query.filter(
            Compliance.activo == ACTIVO
        )

    ultimo_corte_por_tienda = (
        corte_por_tienda_query
        .group_by(
            Compliance.store_id
        )
        .subquery()
    )

    # ======================================================
    # VENTAS Y CUMPLIMIENTO TOTAL
    # ======================================================

    total_compliance = (
        _filtro_compliance(
            Compliance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .filter(
            Store.nombre == "TOTAL"
        )
        .order_by(
            Compliance.id.desc()
        )
        .first()
    )

    venta_actual = (
        _float(
            total_compliance.venta_actual
        )
        if total_compliance
        else 0.0
    )

    venta_anterior = (
        _float(
            total_compliance.venta_anterior
        )
        if total_compliance
        else 0.0
    )

    cumplimiento_promedio = (
        _float(
            total_compliance.cumplimiento_pct
        )
        if total_compliance
        else 0.0
    )

    compliance_base = (
        _filtro_compliance(
            Compliance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .filter(
            Store.nombre == "TOTAL"
        )
    )

    variacion_porcentual = _calcular_crecimiento(
        venta_actual,
        venta_anterior
    )

    # ======================================================
    # TIENDAS
    # ======================================================

    tiendas_query = Store.query.filter(
        Store.nombre != "TOTAL"
    )

    tiendas = tiendas_query.count()

    # ======================================================
    # RANKING TIENDAS
    # ======================================================

    ranking_query = (
        Compliance.query
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .join(
            ultimo_corte_por_tienda,
            db.and_(
                ultimo_corte_por_tienda.c.store_id
                == Compliance.store_id,
                ultimo_corte_por_tienda.c.max_corte
                == Compliance.dia_corte
            )
        )
        .add_columns(
            Store.codigo,
            Store.nombre,
            Compliance.venta_actual,
            Compliance.cumplimiento_pct
        )
        .filter(
            Compliance.anio == anio_actual,
            Compliance.mes == mes_actual,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        ranking_query = ranking_query.filter(
            Store.codigo != "S-24"
        )

    ranking = (
        ranking_query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .limit(10)
        .all()
    )

    # ======================================================
    # RANKING COMPLETO
    # ======================================================

    ranking_completo_query = (
        Compliance.query
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .join(
            ultimo_corte_por_tienda,
            db.and_(
                ultimo_corte_por_tienda.c.store_id
                == Compliance.store_id,
                ultimo_corte_por_tienda.c.max_corte
                == Compliance.dia_corte
            )
        )
        .add_columns(
            Store.codigo,
            Store.nombre,
            Compliance.venta_actual,
            Compliance.cumplimiento_pct
        )
        .filter(
            Compliance.anio == anio_actual,
            Compliance.mes == mes_actual,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        ranking_completo_query = ranking_completo_query.filter(
            Store.codigo != "S-24"
        )

    ranking_completo = (
        ranking_completo_query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .all()
    )

    # ======================================================
    # TOP VENTAS
    # ======================================================

    top_ventas_query = (
        Compliance.query
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .join(
            ultimo_corte_por_tienda,
            db.and_(
                ultimo_corte_por_tienda.c.store_id
                == Compliance.store_id,
                ultimo_corte_por_tienda.c.max_corte
                == Compliance.dia_corte
            )
        )
        .add_columns(
            Store.codigo,
            Store.nombre,
            Compliance.venta_actual,
            Compliance.cumplimiento_pct
        )
        .filter(
            Compliance.anio == anio_actual,
            Compliance.mes == mes_actual,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        top_ventas_query = top_ventas_query.filter(
            Store.codigo != "S-24"
        )

    top_ventas = (
        top_ventas_query
        .order_by(
            Compliance.venta_actual.desc()
        )
        .limit(10)
        .all()
    )

    # ======================================================
    # TOP CUMPLIMIENTO
    # ======================================================

    top_cumplimiento_query = (
        Compliance.query
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .join(
            ultimo_corte_por_tienda,
            db.and_(
                ultimo_corte_por_tienda.c.store_id
                == Compliance.store_id,
                ultimo_corte_por_tienda.c.max_corte
                == Compliance.dia_corte
            )
        )
        .add_columns(
            Store.codigo,
            Store.nombre,
            Compliance.venta_actual,
            Compliance.cumplimiento_pct
        )
        .filter(
            Compliance.anio == anio_actual,
            Compliance.mes == mes_actual,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        top_cumplimiento_query = top_cumplimiento_query.filter(
            Store.codigo != "S-24"
        )

    top_cumplimiento = (
        top_cumplimiento_query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .limit(10)
        .all()
    )

    # ======================================================
    # ASESORAS
    # ======================================================

    performance_query = _filtro_performance(
        AdvisorPerformance.query,
        anio_actual,
        mes_actual,
        dia_corte_actual
    )

    total_asesoras = (
        performance_query
        .with_entities(
            func.count(
                func.distinct(
                    AdvisorPerformance.advisor_id
                )
            )
        )
        .scalar()
        or 0
    )

    venta_asesoras = (
        _filtro_performance(
            AdvisorPerformance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .with_entities(
            func.sum(
                AdvisorPerformance.venta
            )
        )
        .scalar()
        or 0
    )

    unidades_asesoras = (
        _filtro_performance(
            AdvisorPerformance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .with_entities(
            func.sum(
                AdvisorPerformance.unidades
            )
        )
        .scalar()
        or 0
    )

    facturas_asesoras = (
        _filtro_performance(
            AdvisorPerformance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .with_entities(
            func.sum(
                AdvisorPerformance.facturas
            )
        )
        .scalar()
        or 0
    )

    ticket_promedio_asesoras = (
        _float(venta_asesoras)
        / _float(facturas_asesoras)
        if _float(facturas_asesoras) > 0
        else 0
    )

    upt_asesoras = (
        _float(unidades_asesoras)
        / _float(facturas_asesoras)
        if _float(facturas_asesoras) > 0
        else 0
    )

    # ======================================================
    # INDICADORES GLOBALES
    # ======================================================

    trafico_total = (
        compliance_base
        .with_entities(
            func.sum(
                Compliance.trafico
            )
        )
        .scalar()
        or 0
    )

    facturas_total = (
        compliance_base
        .with_entities(
            func.sum(
                Compliance.facturas
            )
        )
        .scalar()
        or 0
    )

    conversion_global = (
        (
            _float(facturas_total)
            / _float(trafico_total)
        ) * 100
        if _float(trafico_total) > 0
        else 0
    )

    ticket_promedio_global = (
        _float(venta_actual)
        / _float(facturas_total)
        if _float(facturas_total) > 0
        else 0
    )

    dif_acum_global = (
        compliance_base
        .with_entities(
            func.sum(
                Compliance.dif_acum
            )
        )
        .scalar()
        or 0
    )

    # ======================================================
    # VENTAS POR LÍNEA GLOBAL
    # ======================================================

    lineas_2025 = (
        db.session.query(
            SalesHistoryLine.line_id,
            func.sum(
                SalesHistoryLine.venta
            ).label("total_venta")
        )
        .filter(
            SalesHistoryLine.anio == 2025,
            SalesHistoryLine.mes == mes_actual,
            SalesHistoryLine.line_id.in_(
                [1, 2, 3, 4]
            )
        )
        .group_by(
            SalesHistoryLine.line_id
        )
        .all()
    )

    lineas_2026 = (
        db.session.query(
            SalesHistoryLine.line_id,
            func.sum(
                SalesHistoryLine.venta
            ).label("total_venta")
        )
        .filter(
            SalesHistoryLine.anio == 2026,
            SalesHistoryLine.mes == mes_actual,
            SalesHistoryLine.line_id.in_(
                [1, 2, 3, 4]
            )
        )
        .group_by(
            SalesHistoryLine.line_id
        )
        .all()
    )

    ventas_linea_2025 = {
        line_id: float(total or 0)
        for line_id, total in lineas_2025
    }

    ventas_linea_2026 = {
        line_id: float(total or 0)
        for line_id, total in lineas_2026
    }

    todos_ids = (
        set(ventas_linea_2025.keys())
        | set(ventas_linea_2026.keys())
    )

    lineas_nombres = {}

    if todos_ids:
        lineas_nombres = dict(
            db.session.query(
                Line.id,
                Line.nombre
            )
            .filter(
                Line.id.in_(todos_ids)
            )
            .all()
        )

    evolucion_lineas_global = []

    for line_id in sorted(todos_ids):

        venta_2025 = ventas_linea_2025.get(
            line_id,
            0
        )

        venta_2026 = ventas_linea_2026.get(
            line_id,
            0
        )

        diferencia = (
            venta_2026
            - venta_2025
        )

        crecimiento = (
            diferencia
            / venta_2025
            * 100
            if venta_2025 > 0
            else 0
        )

        evolucion_lineas_global.append({
            "line_id": line_id,
            "linea": lineas_nombres.get(
                line_id,
                "Sin línea"
            ),
            "venta_2025": venta_2025,
            "venta_2026": venta_2026,
            "diferencia": diferencia,
            "crecimiento": crecimiento
        })

    evolucion_lineas_global.sort(
        key=lambda x: x["venta_2026"],
        reverse=True
    )

    # ======================================================
    # RESUMEN POR CIUDAD Y CLIMA
    # ======================================================

    stores_geo = (
        db.session.query(
            Store.id,
            Store.nombre,
            Store.codigo,
            Store.ciudad,
            Store.clima
        )
        .filter(
            Store.estado == "ACTIVA",
            Store.nombre != "TOTAL"
        )
        .all()
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        stores_geo = [
            s for s in stores_geo
            if s.codigo != "S-24"
        ]

    geo_map = {
        s.id: {
            "ciudad": s.ciudad or "Sin ciudad",
            "clima": s.clima or "Sin clima",
            "nombre": s.nombre
        }
        for s in stores_geo
    }

    compliance_geo = (
        _filtro_compliance(
            Compliance.query,
            anio_actual,
            mes_actual,
            dia_corte_actual
        )
        .all()
    )

    geo_data = {}

    for reg in compliance_geo:

        info = geo_map.get(
            reg.store_id
        )

        if not info:
            continue

        ciudad = info["ciudad"]
        clima = info["clima"]

        if ciudad not in geo_data:
            geo_data[ciudad] = {
                "ciudad": ciudad,
                "tiendas": 0,
                "ventas": 0,
                "cumplimientos": []
            }

        geo_data[ciudad]["tiendas"] += 1

        geo_data[ciudad]["ventas"] += float(
            reg.venta_actual or 0
        )

        geo_data[ciudad]["cumplimientos"].append(
            float(
                reg.cumplimiento_pct or 0
            )
        )

        clima_key = f"__CLIMA__{clima}"

        if clima_key not in geo_data:
            geo_data[clima_key] = {
                "clima": clima,
                "tiendas": 0,
                "ventas": 0,
                "cumplimientos": []
            }

        geo_data[clima_key]["tiendas"] += 1

        geo_data[clima_key]["ventas"] += float(
            reg.venta_actual or 0
        )

        geo_data[clima_key]["cumplimientos"].append(
            float(
                reg.cumplimiento_pct or 0
            )
        )

    ranking_ciudades = []
    resumen_climas = []

    for key, item in geo_data.items():

        cumpl = (
            sum(item["cumplimientos"])
            / len(item["cumplimientos"])
            if item["cumplimientos"]
            else 0
        )

        if "ciudad" in item:

            ranking_ciudades.append({
                "ciudad": item["ciudad"],
                "tiendas": item["tiendas"],
                "ventas": item["ventas"],
                "cumplimiento": cumpl
            })

        else:

            resumen_climas.append({
                "clima": item["clima"],
                "tiendas": item["tiendas"],
                "ventas": item["ventas"],
                "cumplimiento": cumpl
            })

    ranking_ciudades.sort(
        key=lambda x: x["cumplimiento"],
        reverse=True
    )

    resumen_climas.sort(
        key=lambda x: x["ventas"],
        reverse=True
    )

    # ======================================================
    # RANKING GLOBAL ASESORAS
    # ======================================================

    top_global_query = (
        db.session.query(
            AdvisorPerformance.advisor_id,
            AdvisorPerformance.store_id,

            func.sum(
                AdvisorPerformance.venta
            ).label("total_venta"),

            func.sum(
                AdvisorPerformance.unidades
            ).label("total_unidades"),

            func.sum(
                AdvisorPerformance.facturas
            ).label("total_facturas"),

            Advisor.nombre,
            Advisor.es_generico,
            Advisor.estado,

            Store.nombre.label(
                "tienda_nombre"
            ),

            Store.codigo.label(
                "tienda_codigo"
            )
        )
        .join(
            Advisor,
            Advisor.id
            == AdvisorPerformance.advisor_id
        )
        .join(
            Store,
            Store.id
            == AdvisorPerformance.store_id
        )
        .filter(
            AdvisorPerformance.anio == anio_actual,
            AdvisorPerformance.mes == mes_actual,
            AdvisorPerformance.venta > 0,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio_actual,
        mes_actual
    ):
        top_global_query = top_global_query.filter(
            Store.codigo != "S-24"
        )

    if dia_corte_actual is not None:

        top_global_query = top_global_query.filter(
            AdvisorPerformance.dia_corte
            == dia_corte_actual
        )

    else:

        top_global_query = top_global_query.filter(
            AdvisorPerformance.activo
            == ACTIVO
        )

    top_asesoras_global_raw = (
        top_global_query
        .group_by(
            AdvisorPerformance.advisor_id,
            AdvisorPerformance.store_id,
            Advisor.nombre,
            Advisor.es_generico,
            Advisor.estado,
            Store.nombre,
            Store.codigo
        )
        .order_by(
            func.sum(
                AdvisorPerformance.venta
            ).desc()
        )
        .limit(50)
        .all()
    )

    metas_por_tienda = {}

    top_asesoras_global = []

    for reg in top_asesoras_global_raw:

        if reg.store_id not in metas_por_tienda:

            metas_por_tienda[
                reg.store_id
            ] = _obtener_metas_asesoras_tienda(
                reg.store_id,
                anio_actual,
                mes_actual
            )

        meta_valor = (
            metas_por_tienda[
                reg.store_id
            ].get(
                reg.advisor_id,
                0
            )
        )

        registro = _construir_datos_asesora(
            reg,
            meta_valor
        )

        registro.update({
            "tienda": reg.tienda_nombre,
            "codigo_tienda": reg.tienda_codigo
        })

        top_asesoras_global.append(
            registro
        )

        top_asesoras_global.sort(
        key=lambda x: (
            x.get(
                "cumplimiento_corte",
                0
            ),
            x.get(
                "venta",
                0
            )
        ),
        reverse=True
    )
    

    for i, asesora in enumerate(
        top_asesoras_global,
        start=1
    ):
        asesora["posicion"] = i

    # ======================================================
    # ALERTAS
    # ======================================================

    tiendas_criticas = []

    for item in ranking_completo:

        cumplimiento = float(
            item.cumplimiento_pct or 0
        )

        venta = float(
            item.venta_actual or 0
        )

        if (
            cumplimiento < 0.80
            or venta == 0
        ):
            tiendas_criticas.append({
                "nombre": item.nombre,
                "codigo": item.codigo,
                "cumplimiento": cumplimiento,
                "venta": venta
            })

    # ======================================================
    # PERÍODOS
    # ======================================================

    periodos_disponibles = (
        obtener_periodos_disponibles()
    )

    cortes_disponibles = (
        obtener_cortes_disponibles(
            anio_actual,
            mes_actual
        )
    )

    return {
        "ventas": _float(
            venta_actual
        ),

        "venta_anterior": _float(
            venta_anterior
        ),

        "variacion_porcentual": _float(
            variacion_porcentual
        ),

        "cumplimiento": _float(
            cumplimiento_promedio
        ),

        "tiendas": tiendas,

        "ranking": ranking,

        "ranking_completo": ranking_completo,

        "top_ventas": top_ventas,

        "top_cumplimiento": top_cumplimiento,

        "total_asesoras": total_asesoras,

        "venta_asesoras": _float(
            venta_asesoras
        ),

        "unidades_asesoras": _float(
            unidades_asesoras
        ),

        "facturas_asesoras": _float(
            facturas_asesoras
        ),

        "ticket_promedio_asesoras":
            ticket_promedio_asesoras,

        "upt_asesoras":
            upt_asesoras,

        "periodo_anio":
            anio_actual,

        "periodo_mes":
            mes_actual,

        "anio_seleccionado":
            anio_actual,

        "mes_seleccionado":
            mes_actual,

        "dia_corte":
            dia_corte_actual,

        "dia_corte_seleccionado":
            dia_corte_actual,

        "cortes_disponibles":
            cortes_disponibles,

        "periodos_disponibles":
            periodos_disponibles,

        "trafico_total":
            _float(trafico_total),

        "facturas_total":
            _float(facturas_total),

        "conversion_global":
            _float(conversion_global),

        "ticket_promedio_global":
            _float(ticket_promedio_global),

        "dif_acum_global":
            _float(dif_acum_global),

        "unidades_global":
            _float(unidades_asesoras),

        "evolucion_lineas_global":
            evolucion_lineas_global,

        "ranking_ciudades":
            ranking_ciudades,

        "resumen_climas":
            resumen_climas,

        "top_asesoras_global":
            top_asesoras_global,

        "tiendas_criticas":
            tiendas_criticas
    }


# ==========================================================
# DASHBOARD SUPERVISORA
# ==========================================================

def obtener_dashboard_supervisora(
    usuario,
    anio=None,
    mes=None,
    dia_corte=None
):
    tiendas = (
        Store.query
        .filter_by(
            supervisor_id=usuario.supervisor_id
        )
        .filter(
            Store.nombre != "TOTAL"
        )
        .all()
    )

    ids_tiendas = [
        tienda.id
        for tienda in tiendas
    ]

    if not ids_tiendas:
        return {
            "ventas": 0,
            "cumplimiento": 0,
            "tiendas": 0,
            "ranking": [],
            "periodo_anio": None,
            "periodo_mes": None,
            "dia_corte": None,
            "dia_corte_seleccionado": None,
            "cortes_disponibles": [],
            "periodos_disponibles": []
        }

    (
        anio_actual,
        mes_actual,
        dia_corte_actual
    ) = _obtener_corte_actual(
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        store_ids=ids_tiendas
    )

    if anio_actual is None:
        return {
            "ventas": 0,
            "cumplimiento": 0,
            "tiendas": len(tiendas),
            "ranking": [],
            "periodo_anio": None,
            "periodo_mes": None,
            "dia_corte": None,
            "dia_corte_seleccionado": None,
            "cortes_disponibles": [],
            "periodos_disponibles":
                obtener_periodos_disponibles(
                    store_ids=ids_tiendas
                )
        }

    cumplimiento_query = _filtro_compliance(
        Compliance.query,
        anio_actual,
        mes_actual,
        dia_corte_actual,
        store_ids=ids_tiendas
    )

    ventas_totales = (
        cumplimiento_query
        .with_entities(
            func.sum(
                Compliance.venta_actual
            )
        )
        .scalar()
        or 0
    )

    cumplimiento_promedio = (
        cumplimiento_query
        .with_entities(
            func.avg(
                Compliance.cumplimiento_pct
            )
        )
        .scalar()
        or 0
    )

    ranking_query = (
        Compliance.query
        .join(
            Store,
            Store.id == Compliance.store_id
        )
        .filter(
            Store.supervisor_id
            == usuario.supervisor_id,

            Compliance.anio
            == anio_actual,

            Compliance.mes
            == mes_actual,

            Store.nombre != "TOTAL"
        )
        .add_columns(
            Store.nombre,
            Compliance.venta_actual,
            Compliance.cumplimiento_pct
        )
    )

    if dia_corte_actual is not None:

        ranking_query = ranking_query.filter(
            Compliance.dia_corte
            == dia_corte_actual
        )

    else:

        ranking_query = ranking_query.filter(
            Compliance.activo
            == ACTIVO
        )

    ranking = (
        ranking_query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .all()
    )

    periodos_disponibles = (
        obtener_periodos_disponibles(
            store_ids=ids_tiendas
        )
    )

    cortes_disponibles = (
        obtener_cortes_disponibles(
            anio_actual,
            mes_actual,
            store_ids=ids_tiendas
        )
    )

    return {
        "ventas": _float(
            ventas_totales
        ),

        "cumplimiento": _float(
            cumplimiento_promedio
        ),

        "tiendas": len(tiendas),

        "ranking": ranking,

        "periodo_anio":
            anio_actual,

        "periodo_mes":
            mes_actual,

        "anio_seleccionado":
            anio_actual,

        "mes_seleccionado":
            mes_actual,

        "dia_corte":
            dia_corte_actual,

        "dia_corte_seleccionado":
            dia_corte_actual,

        "cortes_disponibles":
            cortes_disponibles,

        "periodos_disponibles":
            periodos_disponibles
    }


# ==========================================================
# DASHBOARD TIENDA POR ID
# ==========================================================
def obtener_dashboard_tienda_por_id(
    store_id,
    anio=None,
    mes=None,
    dia_corte=None
):
    """
    Dashboard completo específico para una tienda.

    IMPORTANTE:
    Esta función devuelve todas las variables que utiliza
    dashboard_tienda.html.
    """

    # ======================================================
    # BUSCAR TIENDA
    # ======================================================

    tienda = db.session.get(
        Store,
        store_id
    )

    if not tienda:
        return {
            "tienda": "Tienda no encontrada",
            "codigo_tienda": "",
            "anio": None,
            "mes": None,

            "ventas": 0,
            "venta_anterior": 0,
            "incremento": 0,
            "cumplimiento": 0,
            "cuota_total": 0,
            "cuota_proporcional": 0,
            "cumplimiento_total": 0,
            "falta_para_cuota": 0,
            "venta_promedio_dia": 0,

            "trafico": 0,
            "facturas": 0,
            "conversion": 0,
            "ticket_promedio": 0,

            "dif_acum": 0,

            "ranking_tienda": 0,
            "total_tiendas": 0,
            "ranking_tiendas": [],

            "asesoras": [],
            "total_asesoras": 0,
            "ventas_asesoras": 0,
            "unidades_asesoras": 0,
            "facturas_asesoras": 0,
            "ticket_asesoras": 0,
            "upt_asesoras": 0,

            "metas_lineas": [],
            "total_lineas": 0,
            "historico_lineas": [],

            "estado_cumplimiento":
                "SIN DATOS",

            "clase_cumplimiento":
                "secondary",

            "evolucion_diaria": [],
            "top_asesoras_global": [],

            "anio_seleccionado": None,
            "mes_seleccionado": None,

            "dia_corte": None,
            "dia_corte_seleccionado": None,

            "cortes_disponibles": [],

            "periodos_disponibles":
                obtener_periodos_disponibles(
                    store_id=store_id
                )
        }

    # ======================================================
    # DETERMINAR CORTE
    # ======================================================

    (
        anio,
        mes,
        dia_corte
    ) = _obtener_corte_actual(
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        store_id=store_id
    )

    # ======================================================
    # SIN DATOS
    # ======================================================

    if anio is None:

        return {
            "tienda": tienda.nombre,
            "codigo_tienda": tienda.codigo,

            "anio": None,
            "mes": None,

            "ventas": 0,
            "venta_anterior": 0,
            "incremento": 0,
            "cumplimiento": 0,

            "cuota_total": 0,
            "cuota_proporcional": 0,
            "cumplimiento_total": 0,
            "falta_para_cuota": 0,
            "venta_promedio_dia": 0,

            "trafico": 0,
            "facturas": 0,
            "conversion": 0,
            "ticket_promedio": 0,

            "dif_acum": 0,

            "ranking_tienda": 0,
            "total_tiendas": 0,
            "ranking_tiendas": [],

            "asesoras": [],
            "total_asesoras": 0,
            "ventas_asesoras": 0,
            "unidades_asesoras": 0,
            "facturas_asesoras": 0,
            "ticket_asesoras": 0,
            "upt_asesoras": 0,

            "metas_lineas": [],
            "total_lineas": 0,
            "historico_lineas": [],

            "estado_cumplimiento":
                "SIN DATOS",

            "clase_cumplimiento":
                "secondary",

            "evolucion_diaria": [],
            "top_asesoras_global": [],

            "anio_seleccionado": None,
            "mes_seleccionado": None,

            "dia_corte": None,
            "dia_corte_seleccionado": None,

            "cortes_disponibles": [],

            "periodos_disponibles":
                obtener_periodos_disponibles(
                    store_id=store_id
                )
        }

    # ======================================================
    # COMPLIANCE
    # ======================================================

    compliance_query = (
        Compliance.query
        .filter(
            Compliance.store_id == store_id,
            Compliance.anio == anio,
            Compliance.mes == mes
        )
    )

    if dia_corte is not None:

        compliance_query = compliance_query.filter(
            Compliance.dia_corte == dia_corte
        )

    else:

        compliance_query = compliance_query.filter(
            Compliance.activo == ACTIVO
        )

    compliance = (
        compliance_query
        .order_by(
            Compliance.dia_corte.desc(),
            Compliance.id.desc()
        )
        .first()
    )

    if compliance:

        venta_actual = _float(
            compliance.venta_actual
        )

        venta_anterior = _float(
            compliance.venta_anterior
        )

        cumplimiento_pct = _float(
            compliance.cumplimiento_pct
        )

        incremento = _float(
            compliance.incremento
        )

        cuota_proporcional = _float(
            compliance.cuota_proporcional
        )

        cuota_total = _float(
            compliance.cuota_total
        )

        # Si la cuota total no está disponible, intentar obtenerla de meta
        if cuota_total <= 0:
            meta_tienda = _float(obtener_meta_tienda(store_id, anio, mes))
            if meta_tienda > 0:
                cuota_total = meta_tienda

        falta_para_cuota = _float(
            compliance.falta_para_cuota
        )

        dif_acum = _float(
            getattr(
                compliance,
                "dif_acum",
                0
            )
        )

        trafico = _int(
            getattr(
                compliance,
                "trafico",
                0
            )
        )

        facturas = _int(
            getattr(
                compliance,
                "facturas",
                0
            )
        )

    else:

        venta_actual = 0.0
        venta_anterior = 0.0
        cumplimiento_pct = 0.0
        incremento = 0.0
        cuota_proporcional = 0.0
        cuota_total = 0.0
        falta_para_cuota = 0.0
        dif_acum = 0.0
        trafico = 0
        facturas = 0

    # ======================================================
    # FALLBACK CUOTA
    # ======================================================

    if cuota_total <= 0 and cumplimiento_pct > 0:

        cuota_total = (
            venta_actual
            / cumplimiento_pct
        )

    if cuota_proporcional <= 0:

        cuota_proporcional = cuota_total

    if falta_para_cuota <= 0:

        falta_para_cuota = _calcular_falta(
            venta_actual,
            cuota_total
        )

    # ======================================================
    # CUMPLIMIENTO TOTAL (contra cuota total mensual)
    # ======================================================

    try:
        cuota_total_float = float(cuota_total)
    except (TypeError, ValueError):
        cuota_total_float = 0.0

    cumplimiento_total = (
        venta_actual / cuota_total_float
        if cuota_total_float > 0
        else 0
    )

    # ======================================================
    # CRECIMIENTO
    # ======================================================

    if incremento == 0:

        incremento = _calcular_crecimiento(
            venta_actual,
            venta_anterior
        )

    # ======================================================
    # PROMEDIO DIARIO
    # ======================================================

    dias_mes = monthrange(
        int(anio),
        int(mes)
    )[1]

    dias_restantes = dias_mes - dia_corte if dia_corte else dias_mes

    venta_promedio_dia = (
        (cuota_total_float - venta_actual) / dias_restantes
        if dias_restantes > 0 and cuota_total_float > 0
        else 0
    )

    # ======================================================
    # CONVERSIÓN
    # ======================================================

    conversion_query = (
        ConversionDiaria.query
        .filter(
            ConversionDiaria.store_id == store_id,
            ConversionDiaria.anio == anio,
            ConversionDiaria.mes == mes
        )
    )

    if (
        hasattr(
            ConversionDiaria,
            "dia_corte"
        )
        and dia_corte is not None
    ):
        conversion_query = conversion_query.filter(
            ConversionDiaria.dia_corte
            == dia_corte
        )

    conversiones = (
        conversion_query
        .order_by(
            ConversionDiaria.dia.asc()
        )
        .all()
    )

    trafico_conversion = sum(
        _int(
            registro.trafico
        )
        for registro in conversiones
    )

    facturas_conversion = sum(
        _int(
            registro.facturas
        )
        for registro in conversiones
    )

    if trafico <= 0:
        trafico = trafico_conversion

    if facturas <= 0:
        facturas = facturas_conversion

    conversion = (
        facturas / trafico
        if trafico > 0
        else 0
    )

    evolucion_diaria = []

    for registro in conversiones:

        evolucion_diaria.append({
            "dia": _int(
                registro.dia
            ),

            "trafico": _int(
                registro.trafico
            ),

            "facturas": _int(
                registro.facturas
            ),

            "conversion": _float(
                registro.conversion
            )
        })

    ticket_promedio = (
        venta_actual / facturas
        if facturas > 0
        else 0
    )

    # ======================================================
    # ASESORAS
    # ======================================================

    registros_asesoras_query = (
        AdvisorPerformance.query
        .join(
            Advisor,
            Advisor.id
            == AdvisorPerformance.advisor_id
        )
        .filter(
            AdvisorPerformance.store_id
            == store_id,

            AdvisorPerformance.anio
            == anio,

            AdvisorPerformance.mes
            == mes,

            AdvisorPerformance.venta > 0
        )
    )

    if dia_corte is not None:

        registros_asesoras_query = (
            registros_asesoras_query
            .filter(
                AdvisorPerformance.dia_corte
                == dia_corte
            )
        )

    else:

        registros_asesoras_query = (
            registros_asesoras_query
            .filter(
                AdvisorPerformance.activo
                == ACTIVO
            )
        )

    registros_asesoras = (
        registros_asesoras_query
        .order_by(
            AdvisorPerformance.venta.desc()
        )
        .all()
    )

    # ======================================================
    # METAS ASESORAS
    # ======================================================

    metas_asesoras_tienda = (
        _obtener_metas_asesoras_tienda(
            store_id,
            anio,
            mes
        )
    )

    # ======================================================
    # RANKING ASESORAS
    # ======================================================

    asesoras = []

    # Novedades de Talento Humano: los días que no estuvo en la tienda no cuentan
    from app.services.novedades_metas import ajustes as ajustes_novedades, aplicar as aplicar_novedad
    ajustes_tienda = ajustes_novedades(
        {(store_id, r.advisor_id) for r in registros_asesoras}, anio, mes, dia_corte
    )

    for posicion, registro in enumerate(
        registros_asesoras,
        start=1
    ):

        meta_valor = (
            metas_asesoras_tienda.get(
                registro.advisor_id,
                0
            )
        )

        dias_mes = monthrange(
            int(anio),
            int(mes)
        )[1]

        ajuste = ajustes_tienda.get((store_id, registro.advisor_id))
        meta_valor, meta_proporcional = aplicar_novedad(meta_valor, ajuste, dia_corte, dias_mes)

        asesora = _construir_datos_asesora(
            registro,
            meta_valor,
            posicion,
            meta_proporcional
        )
        asesora["novedades"] = ajuste["etiquetas"] if ajuste else []

        asesoras.append(
            asesora
        )

    # ======================================================
    # TOTALES ASESORAS
    # ======================================================

    ventas_asesoras = sum(
        asesora["venta"]
        for asesora in asesoras
    )

    unidades_asesoras = sum(
        asesora["unidades"]
        for asesora in asesoras
    )

    facturas_asesoras = sum(
        asesora["facturas"]
        for asesora in asesoras
    )

    ticket_asesoras = (
        ventas_asesoras
        / facturas_asesoras
        if facturas_asesoras > 0
        else 0
    )

    upt_asesoras = (
        unidades_asesoras
        / facturas_asesoras
        if facturas_asesoras > 0
        else 0
    )

    # ======================================================
    # UNIDADES Y UPT DE LA TIENDA
    # Unidades de X DIA X TIENDA (las mismas de Ventas
    # diarias); si no hay, la suma de las asesoras.
    # ======================================================

    unidades_tienda = construir_resumen_tiendas(
        int(anio),
        int(mes),
        dia_corte,
        store_id
    )["total_unidades"] or unidades_asesoras

    upt_tienda = (
        unidades_tienda / facturas
        if facturas > 0
        else upt_asesoras
    )

    # ======================================================
    # RANKING GENERAL TIENDAS
    # ======================================================

    # Subconsulta: último corte activo por tienda
    ultimo_corte_por_tienda = (
        db.session.query(
            Compliance.store_id.label("store_id"),
            func.max(Compliance.dia_corte).label("max_corte")
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.activo == ACTIVO
        )
        .group_by(Compliance.store_id)
        .subquery()
    )

    ranking_tiendas_query = (
        db.session.query(
            Store.id,
            Store.codigo,
            Store.nombre,
            Compliance.venta_actual,
            Compliance.venta_anterior,
            Compliance.cumplimiento_pct
        )
        .join(
            Compliance,
            Compliance.store_id == Store.id
        )
        .join(
            ultimo_corte_por_tienda,
            db.and_(
                ultimo_corte_por_tienda.c.store_id == Compliance.store_id,
                ultimo_corte_por_tienda.c.max_corte == Compliance.dia_corte
            )
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(anio, mes):
        ranking_tiendas_query = ranking_tiendas_query.filter(
            Store.codigo != "S-24"
        )

    ranking_tiendas = (
        ranking_tiendas_query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .all()
    )

    ranking_general = []

    for posicion, registro in enumerate(
        ranking_tiendas,
        start=1
    ):

        venta_ranking = _float(
            registro.venta_actual
        )

        venta_anterior_ranking = _float(
            registro.venta_anterior
        )

        crecimiento_ranking = (
            _calcular_crecimiento(
                venta_ranking,
                venta_anterior_ranking
            )
        )

        ranking_general.append({
            "posicion": posicion,
            "id": registro.id,
            "codigo": registro.codigo,
            "nombre": registro.nombre,
            "ventas": venta_ranking,
            "venta_anterior":
                venta_anterior_ranking,
            "cumplimiento": _float(
                registro.cumplimiento_pct
            ),
            "crecimiento":
                crecimiento_ranking,
            "es_tienda_actual":
                registro.id == store_id
        })

    total_tiendas = len(
        ranking_general
    )

    ranking_tienda = 0

    for registro in ranking_general:

        if registro[
            "es_tienda_actual"
        ]:
            ranking_tienda = (
                registro["posicion"]
            )
            break

    # ======================================================
    # METAS POR LÍNEA
    # ======================================================

    registros_lineas = (
        MetaLine.query
        .filter(
            MetaLine.store_id == store_id,
            MetaLine.anio == anio,
            MetaLine.mes == mes
        )
        .join(
            MetaLine.line
        )
        .order_by(
            MetaLine.cumplimiento_pct.desc()
        )
        .all()
    )

    metas_lineas = []

    for registro in registros_lineas:

        meta = _float(
            registro.meta
        )

        meta_proporcional = _float(
            registro.meta_proporcional
        )

        # ✅ OBTENER VENTA REAL DESDE SalesHistoryLine
        venta = float(
            db.session.query(
                func.sum(SalesHistoryLine.venta)
            )
            .filter(
                SalesHistoryLine.store_id == store_id,
                SalesHistoryLine.line_id == registro.line_id,
                SalesHistoryLine.anio == anio,
                SalesHistoryLine.mes == mes
            )
            .scalar()
            or 0
        )

        cumplimiento_linea = _float(
            registro.cumplimiento_pct
        )

        falta = _calcular_falta(
            venta,
            meta
        )

        estado, clase = _estado_meta(
            cumplimiento_linea,
            meta
        )

        cumplimiento_total = (
            venta / meta
            if meta > 0
            else 0
        )

        cumplimiento_corte = (
            venta / meta_proporcional
            if meta_proporcional > 0
            else 0
        )

        metas_lineas.append({
            "id": registro.id,

            "line_id":
                registro.line_id,

            "linea":
                (
                    registro.line.nombre
                    if registro.line
                    else "Sin línea"
                ),

            "meta": meta,

            "meta_proporcional":
                meta_proporcional,

            "venta": venta,

            "cumplimiento":
                cumplimiento_linea,

            "cumplimiento_corte":
                cumplimiento_corte,

            "cumplimiento_total":
                cumplimiento_total,

            "falta": falta,

            "estado": estado,

            "clase": clase
        })

    total_lineas = len(metas_lineas)

    # ======================================================
    # HISTÓRICO DE LÍNEAS
    # ======================================================

    historico_lineas_db = (
        SalesHistoryLine.query
        .filter(
            SalesHistoryLine.store_id
            == store_id,

            SalesHistoryLine.anio.in_(
                [2025, 2026]
            ),

            SalesHistoryLine.mes
            == mes
        )
        .join(
            SalesHistoryLine.line
        )
        .order_by(
            SalesHistoryLine.line_id
        )
        .all()
    )

    historico_lineas_dict = {}

    for registro in historico_lineas_db:

        if registro.line_id not in historico_lineas_dict:

            historico_lineas_dict[
                registro.line_id
            ] = {
                "line_id":
                    registro.line_id,

                "linea":
                    (
                        registro.line.nombre
                        if registro.line
                        else "Sin línea"
                    ),

                "venta_2025": 0,

                "venta_2026": 0
            }

        venta = _float(
            registro.venta
        )

        if registro.anio == 2025:

            historico_lineas_dict[
                registro.line_id
            ]["venta_2025"] = venta

        elif registro.anio == 2026:

            historico_lineas_dict[
                registro.line_id
            ]["venta_2026"] = venta

    historico_lineas = []

    for datos_linea in (
        historico_lineas_dict.values()
    ):

        venta_2025 = _float(
            datos_linea[
                "venta_2025"
            ]
        )

        venta_2026 = _float(
            datos_linea[
                "venta_2026"
            ]
        )

        diferencia = (
            venta_2026
            - venta_2025
        )

        crecimiento = (
            _calcular_crecimiento(
                venta_2026,
                venta_2025
            )
        )

        if crecimiento > 0:

            estado = "CRECIMIENTO"
            clase = "success"

        elif crecimiento < 0:

            estado = "DISMINUCIÓN"
            clase = "danger"

        else:

            estado = "SIN VARIACIÓN"
            clase = "secondary"

        historico_lineas.append({
            "line_id":
                datos_linea["line_id"],

            "linea":
                datos_linea["linea"],

            "venta_2025":
                venta_2025,

            "venta_2026":
                venta_2026,

            "diferencia":
                diferencia,

            "crecimiento":
                crecimiento,

            "estado":
                estado,

            "clase":
                clase
        })

    # ======================================================
    # COMPLETAR HISTÓRICO DE LÍNEAS
    # ======================================================

    metas_lineas_por_id = {
        item.get("line_id"): item
        for item in metas_lineas
        if item.get("line_id") is not None
    }

    for linea in historico_lineas:

        meta_info = (
            metas_lineas_por_id.get(
                linea.get("line_id"),
                {}
            )
        )

        meta_linea = _float(
            meta_info.get(
                "meta",
                0
            )
        )

        meta_proporcional_linea = _float(
            meta_info.get(
                "meta_proporcional",
                0
            )
        )

        venta_linea = _float(
            linea.get(
                "venta_2026",
                0
            )
        )

        if meta_linea > 0:

            cumplimiento_linea = (
                venta_linea
                / meta_linea
            )

        else:

            cumplimiento_linea = 0.0

        falta_linea = max(
            meta_linea
            - venta_linea,
            0.0
        )

        estado_linea, clase_linea = _estado_meta(
            cumplimiento_linea,
            meta_linea
        )

        linea.update({

            "meta":
                meta_linea,

            "meta_proporcional":
                meta_proporcional_linea,

            "venta":
                venta_linea,

            "cumplimiento":
                cumplimiento_linea,

            "cumplimiento_corte":
                venta_linea / meta_proporcional_linea if meta_proporcional_linea > 0 else 0,

            "cumplimiento_total":
                cumplimiento_linea,

            "falta":
                falta_linea,

            "estado_meta":
                estado_linea,

            "clase_meta":
                clase_linea
        })

    historico_lineas.sort(
        key=lambda x: x["venta_2026"],
        reverse=True
    )

    # ======================================================
    # ESTADO CUMPLIMIENTO
    # ======================================================

    (
        estado_cumplimiento,
        clase_cumplimiento
    ) = _estado_meta(
        cumplimiento_pct,
        cuota_total_float
    )

    if cuota_total_float <= 0:

        estado_cumplimiento = (
            "SIN DATOS"
        )

        clase_cumplimiento = (
            "secondary"
        )

    # ======================================================
    # TOP GLOBAL ASESORAS
    # ======================================================

    top_global_query = (
        db.session.query(
            AdvisorPerformance.advisor_id,
            AdvisorPerformance.store_id,

            func.sum(
                AdvisorPerformance.venta
            ).label(
                "total_venta"
            ),

            func.sum(
                AdvisorPerformance.unidades
            ).label(
                "total_unidades"
            ),

            func.sum(
                AdvisorPerformance.facturas
            ).label(
                "total_facturas"
            ),

            Advisor.nombre,
            Advisor.es_generico,
            Advisor.estado,

            Store.nombre.label(
                "tienda_nombre"
            ),

            Store.codigo.label(
                "tienda_codigo"
            )
        )
        .join(
            Advisor,
            Advisor.id
            == AdvisorPerformance.advisor_id
        )
        .join(
            Store,
            Store.id
            == AdvisorPerformance.store_id
        )
        .filter(
            AdvisorPerformance.anio
            == anio,

            AdvisorPerformance.mes
            == mes,

            AdvisorPerformance.venta > 0,

            Store.nombre != "TOTAL"
        )
    )

    if debe_excluir_s24(
        anio,
        mes
    ):

        top_global_query = (
            top_global_query
            .filter(
                Store.codigo != "S-24"
            )
        )

    if dia_corte is not None:

        top_global_query = (
            top_global_query
            .filter(
                AdvisorPerformance.dia_corte
                == dia_corte
            )
        )

    else:

        top_global_query = (
            top_global_query
            .filter(
                AdvisorPerformance.activo
                == ACTIVO
            )
        )

    top_asesoras_global_raw = (
        top_global_query
        .group_by(
            AdvisorPerformance.advisor_id,
            AdvisorPerformance.store_id,
            Advisor.nombre,
            Advisor.es_generico,
            Advisor.estado,
            Store.nombre,
            Store.codigo
        )
        .having(
            func.sum(
                AdvisorPerformance.venta
            ) > 0
        )
        .order_by(
            func.sum(
                AdvisorPerformance.venta
            ).desc()
        )
        .all()
    )

    metas_asesoras_por_tienda = {}

    top_asesoras_global = []

    from app.services.novedades_metas import ajustes as ajustes_novedades, aplicar as aplicar_novedad
    ajustes_red = ajustes_novedades(
        {(r.store_id, r.advisor_id) for r in top_asesoras_global_raw}, anio, mes, dia_corte
    )

    for posicion, reg in enumerate(
        top_asesoras_global_raw,
        start=1
    ):

        if reg.store_id not in metas_asesoras_por_tienda:

            metas_asesoras_por_tienda[
                reg.store_id
            ] = _obtener_metas_asesoras_tienda(
                reg.store_id,
                anio,
                mes
            )

        metas_tienda = (
            metas_asesoras_por_tienda[
                reg.store_id
            ]
        )

        meta_valor = (
            metas_tienda.get(
                reg.advisor_id,
                0
            )
        )

        dias_mes = monthrange(
            int(anio),
            int(mes)
        )[1]

        ajuste = ajustes_red.get((reg.store_id, reg.advisor_id))
        meta_valor, meta_proporcional = aplicar_novedad(meta_valor, ajuste, dia_corte, dias_mes)

        registro_asesora = (
            _construir_datos_asesora(
                reg,
                meta_valor,
                posicion,
                meta_proporcional
            )
        )
        registro_asesora["novedades"] = ajuste["etiquetas"] if ajuste else []

        registro_asesora.update({
            "tienda":
                reg.tienda_nombre,

            "codigo_tienda":
                reg.tienda_codigo
        })

        top_asesoras_global.append(
            registro_asesora
        )

    # ✅ Ordenar por cumplimiento al corte
    top_asesoras_global.sort(
        key=lambda x: (
            x.get(
                "cumplimiento_corte",
                0
            ),
            x.get(
                "venta",
                0
            )
        ),
        reverse=True
    )

    # La posición se numera DESPUÉS de ordenar por cumplimiento
    # (antes quedaba la posición por ventas: la 1.ª salía como 5).
    for posicion, asesora_top in enumerate(
        top_asesoras_global,
        start=1
    ):
        asesora_top["posicion"] = posicion

    # ======================================================
    # PERÍODOS
    # ======================================================

    periodos_disponibles = (
        obtener_periodos_disponibles(
            store_id=store_id
        )
    )

    # ======================================================
    # CORTES
    # ======================================================

    cortes_disponibles = (
        obtener_cortes_disponibles(
            anio,
            mes,
            store_id=store_id
        )
    )

    # ======================================================
    # RETORNO COMPLETO
    # ======================================================

    return {

        # --------------------------------------------------
        # TIENDA
        # --------------------------------------------------

        "tienda":
            tienda.nombre,

        "codigo_tienda":
            tienda.codigo,

        "anio":
            anio,

        "mes":
            mes,

        # --------------------------------------------------
        # KPIs PRINCIPALES
        # --------------------------------------------------

        "ventas":
            venta_actual,

        "venta_anterior":
            venta_anterior,

        "incremento":
            incremento,

        "cumplimiento":
            cumplimiento_pct,

        "cuota_total":
            cuota_total_float,

        "cuota_proporcional":
            cuota_proporcional,

        "cumplimiento_total":
            cumplimiento_total,

        "falta_para_cuota":
            falta_para_cuota,

        "venta_promedio_dia":
            venta_promedio_dia,

        # --------------------------------------------------
        # CONVERSIÓN
        # --------------------------------------------------

        "trafico":
            trafico,

        "facturas":
            facturas,

        "conversion":
            conversion,

        "ticket_promedio":
            ticket_promedio,

        "unidades_tienda":
            unidades_tienda,

        "upt_tienda":
            upt_tienda,

        # VPT y UPT vs año anterior y meta mínima de VPT (services/vpt_service.py)
        **indicadores_vpt(
            store_id,
            anio,
            mes,
            dia_corte,
            venta_anterior,
            ticket_promedio,
            upt_tienda
        ),

        # --------------------------------------------------
        # DIF ACUM
        # --------------------------------------------------

        "dif_acum":
            dif_acum,

        # --------------------------------------------------
        # RANKING TIENDAS
        # --------------------------------------------------

        "ranking_tienda":
            ranking_tienda,

        "total_tiendas":
            total_tiendas,

        "ranking_tiendas":
            ranking_general,

        # --------------------------------------------------
        # ASESORAS
        # --------------------------------------------------

        "asesoras":
            asesoras,

        "total_asesoras":
            len(asesoras),

        "ventas_asesoras":
            ventas_asesoras,

        "unidades_asesoras":
            unidades_asesoras,

        "facturas_asesoras":
            facturas_asesoras,

        "ticket_asesoras":
            ticket_asesoras,

        "upt_asesoras":
            upt_asesoras,

        # --------------------------------------------------
        # LÍNEAS
        # --------------------------------------------------

        "metas_lineas":
            metas_lineas,

        "total_lineas":
            total_lineas,

        "historico_lineas":
            historico_lineas,

        # --------------------------------------------------
        # ESTADO
        # --------------------------------------------------

        "estado_cumplimiento":
            estado_cumplimiento,

        "clase_cumplimiento":
            clase_cumplimiento,

        # --------------------------------------------------
        # EVOLUCIÓN
        # --------------------------------------------------

        "evolucion_diaria":
            evolucion_diaria,

        # --------------------------------------------------
        # TOP GLOBAL
        # --------------------------------------------------

        "top_asesoras_global":
            top_asesoras_global,

        # --------------------------------------------------
        # FILTROS
        # --------------------------------------------------

        "anio_seleccionado":
            anio,

        "mes_seleccionado":
            mes,

        "dia_corte":
            dia_corte,

        "dia_corte_seleccionado":
            dia_corte,

        "cortes_disponibles":
            cortes_disponibles,

        "periodos_disponibles":
            periodos_disponibles
    }


# ==========================================================
# DASHBOARD TIENDA
# ==========================================================

def obtener_dashboard_tienda(
    usuario,
    anio=None,
    mes=None,
    dia_corte=None
):
    return obtener_dashboard_tienda_por_id(
        usuario.store_id,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte
    )
