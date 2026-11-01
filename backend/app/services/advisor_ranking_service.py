from app.utils.logs import log_debug
from sqlalchemy import func

from app.extensions import db

from app.models import (
    Advisor,
    AdvisorPerformance,
    Store,
)


# ==========================================================
# CONSTANTES
# ==========================================================

ACTIVO = True


# ==========================================================
# FUNCIONES AUXILIARES
# ==========================================================

def _float(valor):
    """
    Convierte Decimal / None / números a float de forma segura.
    """
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


# ==========================================================
# OBTENER ÚLTIMO CORTE DISPONIBLE
# ==========================================================

def obtener_ultimo_corte(
    anio=None,
    mes=None,
    store_id=None
):
    """
    Obtiene el último día de corte disponible para un período.

    Se consideran únicamente registros activos.

    Retorna:
        int | None
    """

    query = (
        db.session.query(
            AdvisorPerformance.dia_corte
        )
        .filter(
            AdvisorPerformance.activo == ACTIVO
        )
    )

    # ------------------------------------------------------
    # FILTRO AÑO
    # ------------------------------------------------------

    if anio is not None:

        query = query.filter(
            AdvisorPerformance.anio == anio
        )

    # ------------------------------------------------------
    # FILTRO MES
    # ------------------------------------------------------

    if mes is not None:

        query = query.filter(
            AdvisorPerformance.mes == mes
        )

    # ------------------------------------------------------
    # FILTRO TIENDA
    # ------------------------------------------------------

    if store_id is not None:

        query = query.filter(
            AdvisorPerformance.store_id == store_id
        )

    # ------------------------------------------------------
    # SOLO CORTES VÁLIDOS
    # ------------------------------------------------------

    query = query.filter(
        AdvisorPerformance.dia_corte.isnot(None)
    )

    # ------------------------------------------------------
    # ÚLTIMO CORTE
    # ------------------------------------------------------

    resultado = (
        query
        .order_by(
            AdvisorPerformance.dia_corte.desc()
        )
        .first()
    )

    if resultado:
        return resultado.dia_corte

    return None


# ==========================================================
# RESOLVER CORTE
# ==========================================================

def resolver_dia_corte(
    anio=None,
    mes=None,
    dia_corte=None,
    store_id=None
):
    """
    Determina qué corte debe utilizar el ranking.

    Si el usuario seleccionó un corte:
        utiliza ese corte.

    Si no:
        utiliza el último corte disponible.

    Retorna:
        dia_corte
    """

    if dia_corte is not None:

        return dia_corte

    return obtener_ultimo_corte(
        anio=anio,
        mes=mes,
        store_id=store_id
    )


# ==========================================================
# RANKING DE ASESORAS
# ==========================================================

def obtener_top_asesoras(
    limite=10,
    anio=None,
    mes=None,
    dia_corte=None,
    store_id=None
):
    """
    Obtiene el ranking de asesoras.

    Filtros soportados:

        año
        mes
        día de corte
        tienda

    Si limite=None:
        devuelve todas las asesoras.

    IMPORTANTE:
    El ranking utiliza exactamente el mismo corte
    seleccionado por el usuario.
    """

    # ======================================================
    # RESOLVER CORTE
    # ======================================================

    dia_corte = resolver_dia_corte(
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        store_id=store_id
    )

    log_debug("========================================")
    log_debug("DEBUG RANKING ASESORAS")
    log_debug("Año:", anio)
    log_debug("Mes:", mes)
    log_debug("Día corte:", dia_corte)
    log_debug("Store ID:", store_id)
    log_debug("========================================")

    # ======================================================
    # CONSTRUIR QUERY
    # ======================================================

    def construir_query(
        solo_activos=True
    ):

        query = (
            db.session.query(

                Advisor.id.label(
                    "advisor_id"
                ),

                Advisor.nombre.label(
                    "asesora"
                ),

                Store.id.label(
                    "store_id"
                ),

                Store.nombre.label(
                    "tienda"
                ),

                func.sum(
                    AdvisorPerformance.venta
                ).label(
                    "venta"
                ),

                func.sum(
                    AdvisorPerformance.unidades
                ).label(
                    "unidades"
                ),

                func.sum(
                    AdvisorPerformance.facturas
                ).label(
                    "facturas"
                ),
            )

            .join(
                AdvisorPerformance,
                Advisor.id ==
                AdvisorPerformance.advisor_id
            )

            .join(
                Store,
                Store.id ==
                AdvisorPerformance.store_id
            )
        )

        # --------------------------------------------------
        # AÑO
        # --------------------------------------------------

        if anio is not None:

            query = query.filter(
                AdvisorPerformance.anio == anio
            )

        # --------------------------------------------------
        # MES
        # --------------------------------------------------

        if mes is not None:

            query = query.filter(
                AdvisorPerformance.mes == mes
            )

        # --------------------------------------------------
        # DÍA DE CORTE
        # --------------------------------------------------

        if dia_corte is not None:

            query = query.filter(
                AdvisorPerformance.dia_corte ==
                dia_corte
            )

        # --------------------------------------------------
        # TIENDA
        # --------------------------------------------------

        if store_id is not None:

            query = query.filter(
                AdvisorPerformance.store_id ==
                store_id
            )

        # --------------------------------------------------
        # SOLO ACTIVOS
        # --------------------------------------------------

        if solo_activos:

            query = query.filter(
                AdvisorPerformance.activo.is_(True)
            )

        # --------------------------------------------------
        # EXCLUIR TOTAL
        # --------------------------------------------------

        query = query.filter(
            Store.nombre != "TOTAL"
        )

        # --------------------------------------------------
        # AGRUPACIÓN
        # --------------------------------------------------

        query = (
            query
            .group_by(

                Advisor.id,

                Advisor.nombre,

                Store.id,

                Store.nombre
            )

            .order_by(

                func.sum(
                    AdvisorPerformance.venta
                ).desc()
            )
        )

        return query

    # ======================================================
    # PRIMER INTENTO
    # ACTIVOS
    # ======================================================

    resultados = (
        construir_query(
            solo_activos=True
        )
        .all()
    )

    # ======================================================
    # RESPALDO
    # MISMO CORTE, SIN FILTRO ACTIVO
    # ======================================================

    if not resultados:

        log_debug(
            "RANKING: no hay registros activos."
        )

        log_debug(
            "RANKING: buscando registros del mismo corte."
        )

        resultados = (
            construir_query(
                solo_activos=False
            )
            .all()
        )

    # ======================================================
    # LIMITAR
    # ======================================================

    if limite is not None:

        resultados = resultados[
            :limite
        ]

    # ======================================================
    # CONSTRUIR RESPUESTA
    # ======================================================

    top = []

    for idx, row in enumerate(
        resultados,
        start=1
    ):

        venta = _float(
            row.venta
        )

        facturas = _float(
            row.facturas
        )

        unidades = _float(
            row.unidades
        )

        # --------------------------------------------------
        # TICKET
        # --------------------------------------------------

        ticket = (
            venta / facturas
            if facturas > 0
            else 0
        )

        # --------------------------------------------------
        # UPT
        # --------------------------------------------------

        upt = (
            unidades / facturas
            if facturas > 0
            else 0
        )

        top.append({

            "posicion":
                idx,

            "advisor_id":
                row.advisor_id,

            "asesora":
                row.asesora
                or "Sin nombre",

            "store_id":
                row.store_id,

            "tienda":
                row.tienda
                or "Sin tienda",

            "venta":
                venta,

            "facturas":
                facturas,

            "unidades":
                unidades,

            "ticket":
                ticket,

            "upt":
                upt,

            "dia_corte":
                dia_corte,

            "anio":
                anio,

            "mes":
                mes,
        })

    log_debug(
        "RANKING REGISTROS:",
        len(top)
    )

    return top


# ==========================================================
# RESUMEN DE ASESORAS
# ==========================================================

def obtener_resumen_asesoras(
    anio=None,
    mes=None,
    dia_corte=None,
    store_id=None
):
    """
    Obtiene el resumen general de asesoras.

    Utiliza exactamente el mismo período y corte
    que el ranking.
    """

    # ======================================================
    # RESOLVER CORTE
    # ======================================================

    dia_corte = resolver_dia_corte(
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        store_id=store_id
    )

    log_debug("========================================")
    log_debug("DEBUG RESUMEN ASESORAS")
    log_debug("Año:", anio)
    log_debug("Mes:", mes)
    log_debug("Día corte:", dia_corte)
    log_debug("Store ID:", store_id)
    log_debug("========================================")

    # ======================================================
    # TOTAL DE ASESORAS
    # ======================================================

    query_asesoras = (
        db.session.query(
            func.count(
                func.distinct(
                    AdvisorPerformance.advisor_id
                )
            )
        )
        .filter(
            AdvisorPerformance.activo == ACTIVO
        )
    )

    # ------------------------------------------------------
    # PERÍODO
    # ------------------------------------------------------

    if anio is not None:

        query_asesoras = query_asesoras.filter(
            AdvisorPerformance.anio == anio
        )

    if mes is not None:

        query_asesoras = query_asesoras.filter(
            AdvisorPerformance.mes == mes
        )

    # ------------------------------------------------------
    # CORTE
    # ------------------------------------------------------

    if dia_corte is not None:

        query_asesoras = query_asesoras.filter(
            AdvisorPerformance.dia_corte ==
            dia_corte
        )

    # ------------------------------------------------------
    # TIENDA
    # ------------------------------------------------------

    if store_id is not None:

        query_asesoras = query_asesoras.filter(
            AdvisorPerformance.store_id ==
            store_id
        )

    total_asesoras = (
        query_asesoras
        .scalar()
        or 0
    )

    # ======================================================
    # FUNCIÓN PARA OBTENER TOTALES
    # ======================================================

    def obtener_totales(
        solo_activos=True
    ):

        query_base = (
            db.session.query(

                func.sum(
                    AdvisorPerformance.venta
                ).label(
                    "venta"
                ),

                func.sum(
                    AdvisorPerformance.unidades
                ).label(
                    "unidades"
                ),

                func.sum(
                    AdvisorPerformance.facturas
                ).label(
                    "facturas"
                ),
            )
        )

        # --------------------------------------------------
        # AÑO
        # --------------------------------------------------

        if anio is not None:

            query_base = query_base.filter(
                AdvisorPerformance.anio ==
                anio
            )

        # --------------------------------------------------
        # MES
        # --------------------------------------------------

        if mes is not None:

            query_base = query_base.filter(
                AdvisorPerformance.mes ==
                mes
            )

        # --------------------------------------------------
        # CORTE
        # --------------------------------------------------

        if dia_corte is not None:

            query_base = query_base.filter(
                AdvisorPerformance.dia_corte ==
                dia_corte
            )

        # --------------------------------------------------
        # TIENDA
        # --------------------------------------------------

        if store_id is not None:

            query_base = query_base.filter(
                AdvisorPerformance.store_id ==
                store_id
            )

        # --------------------------------------------------
        # ACTIVOS
        # --------------------------------------------------

        if solo_activos:

            query_base = query_base.filter(
                AdvisorPerformance.activo.is_(True)
            )

        return query_base.first()

    # ======================================================
    # ACTIVOS
    # ======================================================

    resultado = obtener_totales(
        solo_activos=True
    )

    venta = _float(
        resultado.venta
    )

    unidades = _float(
        resultado.unidades
    )

    facturas = _float(
        resultado.facturas
    )

    # ======================================================
    # RESPALDO
    # MISMO CORTE
    # ======================================================

    if (
        venta == 0
        and unidades == 0
        and facturas == 0
    ):

        resultado = obtener_totales(
            solo_activos=False
        )

        venta = _float(
            resultado.venta
        )

        unidades = _float(
            resultado.unidades
        )

        facturas = _float(
            resultado.facturas
        )

    # ======================================================
    # UPT
    # ======================================================

    upt = (
        unidades / facturas
        if facturas > 0
        else 0
    )

    # ======================================================
    # TICKET
    # ======================================================

    ticket_promedio = (
        venta / facturas
        if facturas > 0
        else 0
    )

    # ======================================================
    # RETORNO
    # ======================================================

    return {

        "asesoras":
            total_asesoras,

        "venta_total":
            venta,

        "unidades_total":
            unidades,

        "facturas_total":
            facturas,

        "upt":
            upt,

        "ticket_promedio":
            ticket_promedio,

        "dia_corte":
            dia_corte,

        "anio":
            anio,

        "mes":
            mes,

        "store_id":
            store_id,
    }