from flask import Blueprint, render_template, request, session, abort
from sqlalchemy import func, or_

from app.extensions import db

from app.models.user import User
from app.models.store import Store
from app.models.compliance import Compliance
from app.models.archivo_importado import ArchivoImportado
from app.models import Advisor, AdvisorPerformance

from app.services.advisor_goal_service import (
    calcular_metas_asesoras,
    obtener_meta_tienda
)
from app.models import DailySales
from app.services.ventas_diarias_service import (
    construir_resumen_global,
    construir_resumen_tiendas,
    obtener_periodos_ventas_diarias,
)




# ==========================================================
# BLUEPRINT
# ==========================================================

app_pages_bp = Blueprint(
    "app_pages",
    __name__
)


# ==========================================================
# UTILIDADES GENERALES
# ==========================================================

def obtener_usuario_actual():
    """
    Obtiene el usuario actualmente autenticado.
    """

    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.get(user_id)


def obtener_rol_usuario(usuario):
    """
    Devuelve el nombre del rol normalizado.
    """

    if not usuario:
        return None

    if not usuario.role:
        return None

    if not usuario.role.nombre:
        return None

    return str(
        usuario.role.nombre
    ).upper().strip()


def es_usuario_tienda(usuario):
    """
    Determina si el usuario pertenece al rol TIENDA.
    """

    return (
        obtener_rol_usuario(usuario)
        == "TIENDA"
    )


def es_usuario_admin(usuario):
    """
    Determina si el usuario es administrador.
    """

    rol = obtener_rol_usuario(usuario)

    return rol in {
        "ADMIN",
        "ADMINISTRADOR"
    }


def verificar_acceso(roles_permitidos=None):
    """
    Verifica sesión y rol.

    Por defecto permite:

        ADMIN
        ADMINISTRADOR
        TIENDA
    """

    usuario = obtener_usuario_actual()

    if not usuario:
        abort(401)

    rol = obtener_rol_usuario(usuario)

    if not rol:
        abort(403)

    if roles_permitidos is None:
        roles_permitidos = {
            "ADMIN",
            "ADMINISTRADOR",
            "TIENDA"
        }

    if rol not in roles_permitidos:
        abort(403)

    return usuario


# ==========================================================
# PERÍODO
# ==========================================================

def obtener_periodo():
    """
    Obtiene año y mes enviados por GET.

    Si no se reciben, utiliza el período más reciente
    existente en Compliance.
    """

    anio = request.args.get(
        "anio",
        type=int
    )

    mes = request.args.get(
        "mes",
        type=int
    )

    # ------------------------------------------------------
    # Si ambos vienen completos, utilizarlos.
    # ------------------------------------------------------

    if anio and mes:
        return anio, mes

    # ------------------------------------------------------
    # Buscar último año disponible.
    # ------------------------------------------------------

    ultimo_anio = (
        db.session.query(
            func.max(
                Compliance.anio
            )
        )
        .scalar()
    )

    if ultimo_anio is None:
        return None, None

    anio = int(ultimo_anio)

    # ------------------------------------------------------
    # Buscar último mes de ese año.
    # ------------------------------------------------------

    ultimo_mes = (
        db.session.query(
            func.max(
                Compliance.mes
            )
        )
        .filter(
            Compliance.anio == anio
        )
        .scalar()
    )

    if ultimo_mes is None:
        return anio, None

    return (
        anio,
        int(ultimo_mes)
    )


def obtener_periodo_anterior(anio, mes):
    """
    Devuelve el período inmediatamente anterior.
    """

    if not anio or not mes:
        return None, None

    if mes == 1:
        return (
            anio - 1,
            12
        )

    return (
        anio,
        mes - 1
    )


# ==========================================================
# CORTES DISPONIBLES
# ==========================================================

def obtener_dias_corte(anio, mes):
    """
    Obtiene todos los días de corte disponibles para
    un período.

    IMPORTANTE:

    NO se filtra por estado ACTIVO.

    Esto es necesario porque al importar un nuevo archivo,
    los cortes anteriores pueden quedar inactivos, pero
    siguen siendo históricos y deben poder consultarse.

    Ejemplo:

        Agosto 2026

        [10, 13, 17, 23]

    """

    if not anio or not mes:
        return []

    # ------------------------------------------------------
    # IMPORTANTE:
    #
    # NO colocar:
    #
    # ArchivoImportado.estado == "ACTIVO"
    #
    # porque eso eliminaría los cortes históricos.
    # ------------------------------------------------------

    resultados = (
        db.session.query(
            ArchivoImportado.dia_corte
        )
        .filter(
            ArchivoImportado.anio == anio,
            ArchivoImportado.mes == mes
        )
        .distinct()
        .order_by(
            ArchivoImportado.dia_corte.asc()
        )
        .all()
    )

    dias = []

    for item in resultados:

        dia = item.dia_corte

        if dia is None:
            continue

        try:
            dia = int(dia)
        except (
            TypeError,
            ValueError
        ):
            continue

        if dia <= 0:
            continue

        if dia not in dias:
            dias.append(dia)

    return dias


def obtener_dia_corte_actual(anio, mes):
    """
    Obtiene el día de corte seleccionado por GET.

    Comportamiento:

    ------------------------------------------------------
    SIN día seleccionado
    ------------------------------------------------------

    Si existen:

        [10, 13, 17, 23]

    devuelve:

        23

    Es decir, el último corte disponible.

    ------------------------------------------------------
    CON día seleccionado
    ------------------------------------------------------

    ?dia_corte=10

        -> 10

    ?dia_corte=13

        -> 13

    ?dia_corte=17

        -> 17

    ?dia_corte=23

        -> 23

    ------------------------------------------------------
    Si se recibe un día inválido
    ------------------------------------------------------

    Se devuelve el último corte disponible.
    """

    dias_corte = obtener_dias_corte(
        anio,
        mes
    )

    dia_corte_parametro = request.args.get(
        "dia_corte",
        default=None,
        type=int
    )

    # ------------------------------------------------------
    # No existen cortes
    # ------------------------------------------------------

    if not dias_corte:
        return None, []

    # ------------------------------------------------------
    # NO se seleccionó día
    #
    # Usar automáticamente el último corte.
    # ------------------------------------------------------

    if dia_corte_parametro is None:
        return (
            dias_corte[-1],
            dias_corte
        )

    # ------------------------------------------------------
    # Se seleccionó un corte válido
    # ------------------------------------------------------

    if dia_corte_parametro in dias_corte:

        return (
            dia_corte_parametro,
            dias_corte
        )

    # ------------------------------------------------------
    # Corte inválido
    #
    # Volvemos al último corte disponible.
    # ------------------------------------------------------

    return (
        dias_corte[-1],
        dias_corte
    )


# ==========================================================
# METAS DE ASESORAS
# ==========================================================

def obtener_metas_asesoras_por_tienda(
    store_id,
    anio,
    mes
):
    """
    Obtiene las metas individuales de las asesoras
    utilizando exclusivamente la lógica centralizada
    de advisor_goal_service.py.

    Devuelve:

        {
            advisor_id: meta
        }
    """

    metas = {}

    if not store_id:
        return metas

    if not anio:
        return metas

    if not mes:
        return metas

    try:

        meta_tienda = obtener_meta_tienda(
            store_id,
            anio,
            mes
        )

        resultado = calcular_metas_asesoras(
            store_id=store_id,
            anio=anio,
            mes=mes,
            meta_tienda=meta_tienda
        )

    except Exception:
        return metas

    if not resultado:
        return metas

    asesoras = resultado.get(
        "asesoras",
        []
    )

    if not asesoras:
        return metas

    for asesora in asesoras:

        if not isinstance(
            asesora,
            dict
        ):
            continue

        # --------------------------------------------------
        # ID
        # --------------------------------------------------

        advisor_id = (
            asesora.get("advisor_id")
            or asesora.get("asesor_id")
            or asesora.get("id")
        )

        if advisor_id is None:
            continue

        try:
            advisor_id = int(
                advisor_id
            )
        except (
            TypeError,
            ValueError
        ):
            continue

        # --------------------------------------------------
        # META
        # --------------------------------------------------

        meta = asesora.get("meta")

        if meta is None:
            meta = asesora.get(
                "meta_asesora"
            )

        if meta is None:
            meta = asesora.get(
                "meta_individual"
            )

        if meta is None:
            meta = asesora.get(
                "meta_por_asesora"
            )

        if meta is None:
            meta = asesora.get(
                "cuota"
            )

        if meta is None:
            meta = 0

        try:
            meta = float(
                meta or 0
            )
        except (
            TypeError,
            ValueError
        ):
            meta = 0

        metas[advisor_id] = meta

    return metas


# ==========================================================
# OBTENER METAS PARA VARIAS TIENDAS
# ==========================================================

def obtener_metas_por_tiendas(
    store_ids,
    anio,
    mes
):
    """
    Obtiene las metas de todas las tiendas necesarias.

    Devuelve:

        {
            store_id: {
                advisor_id: meta
            }
        }
    """

    resultado = {}

    if not anio or not mes:
        return resultado

    for store_id in store_ids:

        if not store_id:
            continue

        if store_id in resultado:
            continue

        resultado[store_id] = (
            obtener_metas_asesoras_por_tienda(
                store_id,
                anio,
                mes
            )
        )

    return resultado


# ==========================================================
# RANKING TIENDAS
# ==========================================================

@app_pages_bp.route("/ranking/tiendas")
def ranking_tiendas():

    usuario = verificar_acceso()

    anio, mes = obtener_periodo()

    busqueda = request.args.get(
        "buscar",
        "",
        type=str
    ).strip()

    es_tienda = es_usuario_tienda(
        usuario
    )

    # ======================================================
    # SUBQUERY: ÚLTIMO CORTE ACTIVO POR TIENDA
    # ======================================================

    ultimo_corte_por_tienda = (
        db.session.query(
            Compliance.store_id.label("store_id"),
            func.max(Compliance.dia_corte).label("max_corte")
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.activo == True
        )
        .group_by(Compliance.store_id)
        .subquery()
    )

    # ======================================================
    # CONSULTA PRINCIPAL
    # ======================================================

    query = (
        db.session.query(

            Store.id.label(
                "store_id"
            ),

            Store.codigo.label(
                "codigo"
            ),

            Store.nombre.label(
                "nombre"
            ),

            Compliance.venta_actual.label(
                "venta_actual"
            ),

            Compliance.cumplimiento_pct.label(
                "cumplimiento_pct"
            )
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
            Store.estado == "ACTIVA",
            Store.nombre != "TOTAL",
            Store.codigo != "TOTA"
        )
    )

    # ======================================================
    # PERÍODO
    # ======================================================

    if anio is not None:

        query = query.filter(
            Compliance.anio == anio
        )

    if mes is not None:

        query = query.filter(
            Compliance.mes == mes
        )

    # ======================================================
    # BÚSQUEDA
    # ======================================================

    if busqueda:

        termino = f"%{busqueda}%"

        query = query.filter(
            or_(
                Store.nombre.ilike(
                    termino
                ),
                Store.codigo.ilike(
                    termino
                )
            )
        )

    # ======================================================
    # EXCLUIR S-24 DESDE AGOSTO 2026
    # ======================================================

    if debe_excluir_s24(anio, mes):

        query = query.filter(
            Store.codigo != "S-24"
        )

    # ======================================================
    # RESULTADOS
    # ======================================================

    resultados = (
        query
        .order_by(
            Compliance.cumplimiento_pct.desc(),
            Compliance.venta_actual.desc()
        )
        .all()
    )

    # ======================================================
    # RANKING
    # ======================================================

    ranking = []

    for posicion, item in enumerate(
        resultados,
        start=1
    ):

        cumplimiento = float(
            item.cumplimiento_pct or 0
        )

        if es_tienda:
            venta = None
        else:
            venta = float(
                item.venta_actual or 0
            )

        ranking.append({

            "posicion":
                posicion,

            "store_id":
                item.store_id,

            "codigo":
                item.codigo,

            "nombre":
                item.nombre,

            "venta_actual":
                venta,

            "cumplimiento_pct":
                cumplimiento

        })

    # ======================================================
    # RENDER
    # ======================================================

    return render_template(
        "ranking/ranking_tiendas.html",
        usuario=usuario,
        ranking=ranking,
        anio=anio,
        mes=mes,
        busqueda=busqueda,
        es_tienda=es_tienda
    )

def debe_excluir_s24(anio, mes):
    """
    Devuelve True si S-24 debe excluirse desde agosto 2026.
    """
    if anio is None or mes is None:
        return False
    return (anio, mes) >= (2026, 8)


# ==========================================================
# RANKING ASESORAS
# ==========================================================

@app_pages_bp.route(
    "/ranking/asesoras"
)
def ranking_asesoras():

    usuario = verificar_acceso()

    anio, mes = obtener_periodo()

    # ======================================================
    # CORTE
    # ======================================================

    dia_corte, dias_corte = (
        obtener_dia_corte_actual(
            anio,
            mes
        )
    )

    busqueda = request.args.get(
        "buscar",
        "",
        type=str
    ).strip()

    es_tienda = es_usuario_tienda(
        usuario
    )

    # ======================================================
    # CONSULTA DE VENTAS DE ASESORAS
    # ======================================================

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

            Store.codigo.label(
                "codigo_tienda"
            ),

            Store.nombre.label(
                "tienda"
            ),

            func.coalesce(
                func.sum(
                    AdvisorPerformance.venta
                ),
                0
            ).label(
                "venta"
            ),

            func.coalesce(
                func.sum(
                    AdvisorPerformance.unidades
                ),
                0
            ).label(
                "unidades"
            ),

            func.coalesce(
                func.sum(
                    AdvisorPerformance.facturas
                ),
                0
            ).label(
                "facturas"
            )

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
        .filter(
            AdvisorPerformance.activo == True,
            Store.estado == "ACTIVA"
        )
    )

    # ======================================================
    # PERÍODO
    # ======================================================

    if anio is not None:

        query = query.filter(
            AdvisorPerformance.anio == anio
        )

    if mes is not None:

        query = query.filter(
            AdvisorPerformance.mes == mes
        )

    # ======================================================
    # DÍA DE CORTE
    #
    # SIEMPRE SE APLICA EL CORTE RESUELTO.
    #
    # Ejemplo:
    #
    # agosto sin parámetro
    # -> último corte, por ejemplo 23
    #
    # agosto?dia_corte=10
    # -> 10
    # ======================================================

    if dia_corte is not None:

        query = query.filter(
            AdvisorPerformance.dia_corte ==
            dia_corte
        )

    # ======================================================
    # BÚSQUEDA
    # ======================================================

    if busqueda:

        termino = f"%{busqueda}%"

        query = query.filter(
            or_(
                Advisor.nombre.ilike(
                    termino
                ),
                Store.nombre.ilike(
                    termino
                ),
                Store.codigo.ilike(
                    termino
                )
            )
        )

    # ======================================================
    # RESULTADOS
    # ======================================================

    resultados = (
        query
        .group_by(
            Advisor.id,
            Advisor.nombre,
            Store.id,
            Store.codigo,
            Store.nombre
        )
        .all()
    )

    # ======================================================
    # OBTENER TODAS LAS TIENDAS NECESARIAS
    # ======================================================

    store_ids = {
        item.store_id
        for item in resultados
        if item.store_id
    }

    metas_por_tienda = obtener_metas_por_tiendas(
        store_ids,
        anio,
        mes
    )

    # ======================================================
    # PREPARAR RANKING
    # ======================================================

    ranking_sin_posicion = []

    for item in resultados:

        # --------------------------------------------------
        # VENTA REAL
        # --------------------------------------------------

        venta_real = float(
            item.venta or 0
        )

        # --------------------------------------------------
        # UNIDADES
        # --------------------------------------------------

        unidades = float(
            item.unidades or 0
        )

        # --------------------------------------------------
        # FACTURAS
        # --------------------------------------------------

        facturas = float(
            item.facturas or 0
        )

        # --------------------------------------------------
        # TICKET
        # --------------------------------------------------

        if facturas > 0:

            ticket = (
                venta_real /
                facturas
            )

        else:

            ticket = 0

        # --------------------------------------------------
        # UPT
        # --------------------------------------------------

        if facturas > 0:

            upt = (
                unidades /
                facturas
            )

        else:

            upt = 0

        # ==================================================
        # META INDIVIDUAL
        # ==================================================

        metas_tienda = metas_por_tienda.get(
            item.store_id,
            {}
        )

        meta_asesora = metas_tienda.get(
            item.advisor_id,
            0
        )

        try:

            meta_asesora = float(
                meta_asesora or 0
            )

        except (
            TypeError,
            ValueError
        ):

            meta_asesora = 0

        # ==================================================
        # CUMPLIMIENTO
        # ==================================================

        if meta_asesora > 0:

            cumplimiento = (
                venta_real /
                meta_asesora
            )

        else:

            cumplimiento = 0

        # ==================================================
        # DATOS VISIBLES
        # ==================================================

        if es_tienda:

            venta_mostrar = None

            ticket_mostrar = None

        else:

            venta_mostrar = venta_real

            ticket_mostrar = ticket

        # ==================================================
        # REGISTRO
        # ==================================================

        ranking_sin_posicion.append({

            "advisor_id":
                item.advisor_id,

            "asesora":
                item.asesora,

            "tienda":
                item.tienda,

            "codigo_tienda":
                item.codigo_tienda,

            "store_id":
                item.store_id,

            "venta":
                venta_mostrar,

            "venta_real":
                venta_real,

            "unidades":
                unidades,

            "facturas":
                facturas,

            "ticket":
                ticket_mostrar,

            "upt":
                upt,

            "meta":
                meta_asesora,

            "cumplimiento":
                cumplimiento

        })

    # ======================================================
    # ORDEN DEL RANKING
    #
    # 1. Cumplimiento
    # 2. Venta
    # 3. Facturas
    # ======================================================

    ranking_sin_posicion.sort(
        key=lambda x: (
            x["cumplimiento"],
            x["venta_real"],
            x["facturas"]
        ),
        reverse=True
    )

    # ======================================================
    # POSICIONES
    # ======================================================

    ranking = []

    for posicion, item in enumerate(
        ranking_sin_posicion,
        start=1
    ):

        item["posicion"] = posicion

        ranking.append(
            item
        )

    # ======================================================
    # RENDER
    # ======================================================

    return render_template(
        "ranking/ranking_asesoras.html",
        usuario=usuario,
        ranking=ranking,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        dias_corte=dias_corte,
        busqueda=busqueda,
        es_tienda=es_tienda
    )


# ==========================================================
# TIENDAS
# ==========================================================

@app_pages_bp.route(
    "/tiendas"
)
def tiendas():
    usuario = verificar_acceso()
    es_tienda = es_usuario_tienda(usuario)

    periodos_db = (
        db.session.query(Compliance.anio, Compliance.mes)
        .join(Store, Store.id == Compliance.store_id)
        .filter(Store.estado == "ACTIVA")
        .distinct()
        .order_by(Compliance.anio.desc(), Compliance.mes.desc())
        .all()
    )
    periodos = [
        {"anio": int(item.anio), "mes": int(item.mes)}
        for item in periodos_db
        if item.anio and item.mes
    ]

    anio_solicitado = request.args.get("anio", type=int)
    mes_solicitado = request.args.get("mes", type=int)
    periodos_validos = {(item["anio"], item["mes"]) for item in periodos}
    if (anio_solicitado, mes_solicitado) in periodos_validos:
        anio, mes = anio_solicitado, mes_solicitado
    elif periodos:
        anio, mes = periodos[0]["anio"], periodos[0]["mes"]
    else:
        anio, mes = obtener_periodo()

    cortes_db = (
        db.session.query(Compliance.dia_corte)
        .join(Store, Store.id == Compliance.store_id)
        .filter(
            Store.estado == "ACTIVA",
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.dia_corte.isnot(None),
        )
        .distinct()
        .order_by(Compliance.dia_corte.asc())
        .all()
    )
    cortes_disponibles = sorted({
        int(item.dia_corte)
        for item in cortes_db
        if item.dia_corte is not None
    })
    corte_solicitado = request.args.get("dia_corte", type=int)
    dia_corte = (
        corte_solicitado
        if corte_solicitado in cortes_disponibles
        else (cortes_disponibles[-1] if cortes_disponibles else None)
    )

    def registros_del_corte(anio_consulta, mes_consulta, corte_consulta):
        consulta = (
            Compliance.query
            .join(Store, Store.id == Compliance.store_id)
            .filter(
                Store.estado == "ACTIVA",
                Compliance.anio == anio_consulta,
                Compliance.mes == mes_consulta,
            )
        )
        if corte_consulta is not None:
            consulta = consulta.filter(Compliance.dia_corte <= corte_consulta)

        seleccionados = {}
        for registro in consulta.order_by(
            Compliance.store_id.asc(),
            Compliance.dia_corte.asc(),
            Compliance.id.asc(),
        ).all():
            actual = seleccionados.get(registro.store_id)
            clave = (int(registro.dia_corte or 0), int(registro.id or 0))
            clave_actual = (
                int(actual.dia_corte or 0),
                int(actual.id or 0),
            ) if actual else (-1, -1)
            if clave >= clave_actual:
                seleccionados[registro.store_id] = registro
        return seleccionados

    registros_actuales = registros_del_corte(anio, mes, dia_corte)
    anio_anterior, mes_anterior = obtener_periodo_anterior(anio, mes)
    registros_anteriores = registros_del_corte(
        anio_anterior,
        mes_anterior,
        dia_corte,
    ) if anio_anterior and mes_anterior else {}

    ranking_actual = sorted(
        registros_actuales.values(),
        key=lambda item: float(item.cumplimiento_pct or 0),
        reverse=True,
    )
    ranking_anterior = sorted(
        registros_anteriores.values(),
        key=lambda item: float(item.cumplimiento_pct or 0),
        reverse=True,
    )
    posiciones_actuales = {
        item.store_id: posicion
        for posicion, item in enumerate(ranking_actual, start=1)
    }
    posiciones_anteriores = {
        item.store_id: posicion
        for posicion, item in enumerate(ranking_anterior, start=1)
    }

    tiendas_db = (
        Store.query
        .filter(Store.estado == "ACTIVA")
        .order_by(Store.codigo.asc())
        .all()
    )
    tarjetas = []

    for tienda in tiendas_db:
        actual = registros_actuales.get(tienda.id)
        anterior = registros_anteriores.get(tienda.id)
        venta = float(actual.venta_actual or 0) if actual else 0.0
        venta_anterior = float(actual.venta_anterior or 0) if actual else 0.0
        cumplimiento = float(actual.cumplimiento_pct or 0) if actual else 0.0
        cumplimiento_anterior = (
            float(anterior.cumplimiento_pct or 0) if anterior else 0.0
        )
        diferencia_venta = venta - venta_anterior
        variacion = (
            diferencia_venta / venta_anterior if venta_anterior > 0 else None
        )
        evolucion_cumplimiento = cumplimiento - cumplimiento_anterior
        evolucion_tipo = (
            "subio" if evolucion_cumplimiento > 0
            else "bajo" if evolucion_cumplimiento < 0
            else "igual"
        )
        posicion_actual = posiciones_actuales.get(tienda.id)
        posicion_anterior = posiciones_anteriores.get(tienda.id)
        movimiento = (
            posicion_anterior - posicion_actual
            if posicion_actual is not None and posicion_anterior is not None
            else 0
        )
        movimiento_tipo = (
            "subio" if movimiento > 0
            else "bajo" if movimiento < 0
            else "igual"
        )

        if not actual:
            estado, estado_clase = "Sin datos en el corte", "neutral"
        elif cumplimiento >= 1:
            estado, estado_clase = "Meta superada", "success"
        elif cumplimiento >= 0.9:
            estado, estado_clase = "Cerca de la meta", "warning"
        elif cumplimiento >= 0.8:
            estado, estado_clase = "En progreso", "info"
        else:
            estado, estado_clase = "Requiere atención", "danger"

        tarjetas.append({
            "id": tienda.id,
            "codigo": tienda.codigo,
            "nombre": tienda.nombre,
            "imagen": f"{str(tienda.codigo).strip()}.jpeg" if tienda.codigo else None,
            "venta": None if es_tienda else venta,
            "venta_anterior": None if es_tienda else venta_anterior,
            "diferencia_venta": None if es_tienda else diferencia_venta,
            "variacion": None if es_tienda else variacion,
            "cumplimiento": cumplimiento,
            "cumplimiento_anterior": cumplimiento_anterior,
            "evolucion_cumplimiento": evolucion_cumplimiento,
            "evolucion_tipo": evolucion_tipo,
            "posicion_actual": posicion_actual,
            "posicion_anterior": posicion_anterior,
            "movimiento": movimiento,
            "movimiento_tipo": movimiento_tipo,
            "estado": estado,
            "estado_clase": estado_clase,
            "tiene_datos": actual is not None,
            "cuota": None if es_tienda else float(actual.cuota_proporcional or 0) if actual else 0.0,
        })

    tarjetas.sort(key=lambda item: (
        item["posicion_actual"] is None,
        item["posicion_actual"] or 9999,
        item["codigo"] or "",
    ))

    registros_con_datos = list(registros_actuales.values())
    total_venta = sum(float(item.venta_actual or 0) for item in registros_con_datos)
    cumplimiento_promedio = (
        sum(float(item.cumplimiento_pct or 0) for item in registros_con_datos)
        / len(registros_con_datos)
        if registros_con_datos else 0.0
    )
    resumen = {
        "tiendas_activas": len(tiendas_db),
        "tiendas_con_datos": len(registros_con_datos),
        "venta_total": None if es_tienda else total_venta,
        "cumplimiento_promedio": cumplimiento_promedio,
        "metas_alcanzadas": sum(
            1 for item in registros_con_datos
            if float(item.cumplimiento_pct or 0) >= 1
        ),
        "requieren_atencion": sum(
            1 for item in registros_con_datos
            if float(item.cumplimiento_pct or 0) < 0.8
        ),
    }
    ultimo_registro = max(
        registros_con_datos,
        key=lambda item: int(item.id or 0),
        default=None,
    )

    return render_template(
        "admin/tiendas.html",
        usuario=usuario,
        tiendas=tarjetas,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        cortes_disponibles=cortes_disponibles,
        periodos=periodos,
        resumen=resumen,
        ultimo_archivo=ultimo_registro.nombre_archivo if ultimo_registro else None,
        ultima_carga=ultimo_registro.fecha_carga if ultimo_registro else None,
        es_tienda=es_tienda,
    )


# ==========================================================
# HISTORIAL DE IMPORTACIONES
# ==========================================================

@app_pages_bp.route(
    "/importaciones/historial"
)
def historial_importaciones():

    usuario = verificar_acceso({
        "ADMIN",
        "ADMINISTRADOR"
    })

    return render_template(
        "historial_importaciones.html",
        usuario=usuario
    )


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

@app_pages_bp.route(
    "/configuracion"
)
def configuracion():

    usuario = verificar_acceso()

    return render_template(
        "configuracion.html",
        usuario=usuario
    )


# ==========================================================
# CUOTA / META POR TIENDA
# ==========================================================

@app_pages_bp.route("/metas/cuota-tienda")
def cuota_tienda():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    es_tienda = es_usuario_tienda(usuario)

    # Tiendas disponibles (igual que antes)
    if es_tienda:
        if not usuario.store_id:
            abort(403)
        tiendas = Store.query.filter(Store.id == usuario.store_id, Store.estado == "ACTIVA").order_by(Store.codigo).all()
    else:
        tiendas = Store.query.filter(Store.estado == "ACTIVA").order_by(Store.codigo).all()

    store_id = request.args.get("store_id", type=int)
    if es_tienda:
        store_id = usuario.store_id

    datos = None

    if store_id and anio and mes:
        tienda = Store.query.filter(Store.id == store_id, Store.estado == "ACTIVA").first()
        if es_tienda and (not tienda or tienda.id != usuario.store_id):
            abort(403)

        if tienda:
            meta_tienda_base = obtener_meta_tienda(store_id, anio, mes)
            resultado = calcular_metas_asesoras(store_id=store_id, anio=anio, mes=mes, meta_tienda=meta_tienda_base)
            if not resultado:
                resultado = {}

            meta_tienda = float(resultado.get("meta_tienda", meta_tienda_base or 0) or 0)
            cantidad_asesoras = int(resultado.get("cantidad_asesoras", 0) or 0)
            meta_por_asesora = float(resultado.get("meta_por_asesora", 0) or 0)

            # ====================================================
            # VENTAS DIARIAS (X DIA)
            # ====================================================
            daily_records = (
                DailySales.query
                .filter_by(store_id=tienda.id, anio=anio, mes=mes, activo=True)
                .order_by(DailySales.dia.asc())
                .all()
            )

            # Inicializar acumuladores
            ventas_diarias = []
            total_venta_2025 = 0.0
            total_venta_2026 = 0.0
            total_dias = 0
            ventas_por_dia_semana = {}

            meta_diaria_base = meta_tienda / 30 if meta_tienda > 0 else 0
            dia_corte_actual, _ = obtener_dia_corte_actual(anio, mes)

            for reg in daily_records:
                venta_2025 = float(reg.venta_2025 or 0)
                venta_2026 = float(reg.venta_2026 or 0)
                diferencia = venta_2026 - venta_2025
                incremento = float(reg.incremento_pct or 0)
                meta_diaria = meta_diaria_base
                cumplimiento_diario = (venta_2026 / meta_diaria * 100) if meta_diaria > 0 else 0

                total_venta_2025 += venta_2025
                total_venta_2026 += venta_2026
                total_dias += 1

                # Día de semana actual (2026 si existe, si no 2025)
                dia_semana = reg.dia_semana_2026 if venta_2026 > 0 else reg.dia_semana_2025
                if dia_semana:
                    if dia_semana not in ventas_por_dia_semana:
                        ventas_por_dia_semana[dia_semana] = {"venta_2025": 0, "venta_2026": 0, "dias": 0}
                    ventas_por_dia_semana[dia_semana]["venta_2025"] += venta_2025
                    ventas_por_dia_semana[dia_semana]["venta_2026"] += venta_2026
                    ventas_por_dia_semana[dia_semana]["dias"] += 1

                ventas_diarias.append({
                    "dia": reg.dia,
                    "venta_2025": venta_2025,
                    "venta_2026": venta_2026,
                    "diferencia": diferencia,
                    "incremento": incremento,
                    "meta_diaria": meta_diaria,
                    "cumplimiento_diario": cumplimiento_diario,
                    "es_dia_corte": reg.dia == dia_corte_actual,
                    "sin_dato_2026": venta_2026 == 0
                })

            # Totales y crecimiento
            total_diferencia = total_venta_2026 - total_venta_2025
            total_incremento = (total_diferencia / total_venta_2025 * 100) if total_venta_2025 > 0 else 0

            # Mejores y peores días (solo días con dato 2026)
            dias_con_2026 = [d for d in ventas_diarias if d["venta_2026"] > 0]
            mejores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"], reverse=True)[:5]
            peores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"])[:5]

            # Ventas por día de semana (ordenar lunes a domingo)
            orden_dias = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
            ventas_semana_ordenadas = []
            for dia_semana in orden_dias:
                if dia_semana in ventas_por_dia_semana:
                    item = ventas_por_dia_semana[dia_semana]
                    ventas_semana_ordenadas.append({
                        "dia": dia_semana,
                        "venta_2025": item["venta_2025"],
                        "venta_2026": item["venta_2026"],
                        "dias": item["dias"]
                    })

            datos = {
                "store_id": tienda.id,
                "codigo": tienda.codigo,
                "nombre": tienda.nombre,
                "meta_tienda": meta_tienda,
                "cantidad_asesoras": cantidad_asesoras,
                "meta_por_asesora": meta_por_asesora,
                "asesoras": resultado.get("asesoras", []),
                # Ventas diarias
                "ventas_diarias": ventas_diarias,
                "total_venta_2025": total_venta_2025,
                "total_venta_2026": total_venta_2026,
                "total_diferencia": total_diferencia,
                "total_incremento": total_incremento,
                "mejores_dias": mejores_dias,
                "peores_dias": peores_dias,
                "ventas_por_dia_semana": ventas_semana_ordenadas,
                "promedio_2025": total_venta_2025 / total_dias if total_dias > 0 else 0,
                "promedio_2026": total_venta_2026 / total_dias if total_dias > 0 else 0,
            }

    return render_template(
        "metas/cuota_tienda.html",
        usuario=usuario,
        tiendas=tiendas,
        store_id_actual=store_id,
        anio=anio,
        mes=mes,
        datos=datos,
        es_tienda=es_tienda
    )

# ==========================================================
# VENDEDOR ÚNICO
# ==========================================================


@app_pages_bp.route(
    "/metas/vendedor-unico"
)
def vendedor_unico():

    usuario = verificar_acceso()

    es_tienda = es_usuario_tienda(
        usuario
    )

    # ======================================================
    # PERÍODO
    # ======================================================

    anio, mes = obtener_periodo()

    # ======================================================
    # CORTE
    # ======================================================

    dia_corte, dias_corte = obtener_dia_corte_actual(
        anio,
        mes
    )

    # ======================================================
    # FILTROS
    # ======================================================

    store_id = request.args.get(
        "store_id",
        type=int
    )

    buscar = request.args.get(
        "buscar",
        "",
        type=str
    ).strip()

    # ======================================================
    # TIENDAS
    # ======================================================

    if es_tienda:

        if not usuario.store_id:
            abort(403)

        tiendas = (
            Store.query
            .filter(
                Store.id ==
                usuario.store_id,
                Store.estado ==
                "ACTIVA"
            )
            .order_by(
                Store.codigo
            )
            .all()
        )

        store_id = usuario.store_id

    else:

        tiendas = (
            Store.query
            .filter(
                Store.estado ==
                "ACTIVA"
            )
            .order_by(
                Store.codigo
            )
            .all()
        )

    # ======================================================
    # SI NO EXISTE PERÍODO
    # ======================================================

    if not anio or not mes:

        return render_template(
            "vendedor_unico.html",

            usuario=usuario,

            tiendas=tiendas,

            store_id_actual=store_id,

            anio=anio,

            mes=mes,

            anio_actual=anio,

            mes_actual=mes,

            buscar=buscar,

            vendedores=[],

            total_venta=0,

            total_unidades=0,

            total_facturas=0,

            total_ticket=0,

            total_upt=0,

            es_tienda=es_tienda
        )

    # ======================================================
    # CONSULTA
    # ======================================================

    query = (
        db.session.query(
            AdvisorPerformance,
            Advisor,
            Store
        )
        .join(
            Advisor,
            Advisor.id ==
            AdvisorPerformance.advisor_id
        )
        .join(
            Store,
            Store.id ==
            AdvisorPerformance.store_id
        )
        .filter(
            Advisor.nombre ==
            "VENDEDOR UNICO",

            AdvisorPerformance.anio ==
            anio,

            AdvisorPerformance.mes ==
            mes,

            Store.estado ==
            "ACTIVA"
        )
    )

    # ======================================================
    # FILTRO DE CORTE
    # ======================================================

    if dia_corte is not None:

        query = query.filter(
            AdvisorPerformance.dia_corte == dia_corte
        )

    # ======================================================
    # FILTRO TIENDA
    # ======================================================

    if store_id:

        query = query.filter(
            AdvisorPerformance.store_id ==
            store_id
        )

    # ======================================================
    # SEGURIDAD TIENDA
    # ======================================================

    if es_tienda:

        query = query.filter(
            AdvisorPerformance.store_id ==
            usuario.store_id
        )

    # ======================================================
    # BÚSQUEDA
    # ======================================================

    if buscar:

        termino = f"%{buscar}%"

        query = query.filter(
            or_(
                Store.nombre.ilike(
                    termino
                ),
                Store.codigo.ilike(
                    termino
                )
            )
        )

    # ======================================================
    # REGISTROS
    # ======================================================

    registros = (
        query
        .order_by(
            Store.codigo.asc()
        )
        .all()
    )

    # ======================================================
    # VENDEDORES
    # ======================================================

    vendedores = []

    for performance, advisor, tienda in registros:

        venta = float(
            performance.venta or 0
        )

        unidades = float(
            performance.unidades or 0
        )

        facturas = float(
            performance.facturas or 0
        )

        # --------------------------------------------------
        # TICKET
        # --------------------------------------------------

        if facturas > 0:

            ticket = (
                venta /
                facturas
            )

        else:

            ticket = 0

        # --------------------------------------------------
        # UPT
        # --------------------------------------------------

        if facturas > 0:

            upt = (
                unidades /
                facturas
            )

        else:

            upt = 0

        vendedores.append({

            "advisor_id":
                advisor.id,

            "nombre":
                advisor.nombre,

            "codigo_tienda":
                tienda.codigo,

            "tienda":
                tienda.nombre,

            "venta":
                venta,

            "unidades":
                unidades,

            "facturas":
                facturas,

            "ticket":
                ticket,

            "upt":
                upt,

            "activo":
                performance.activo

        })

    # ======================================================
    # TOTALES
    # ======================================================

    total_venta = sum(
        vendedor["venta"]
        for vendedor in vendedores
    )

    total_unidades = sum(
        vendedor["unidades"]
        for vendedor in vendedores
    )

    total_facturas = sum(
        vendedor["facturas"]
        for vendedor in vendedores
    )

    # ======================================================
    # TICKET TOTAL
    # ======================================================

    if total_facturas > 0:

        total_ticket = (
            total_venta /
            total_facturas
        )

    else:

        total_ticket = 0

    # ======================================================
    # UPT TOTAL
    # ======================================================

    if total_facturas > 0:

        total_upt = (
            total_unidades /
            total_facturas
        )

    else:

        total_upt = 0

    # ======================================================
    # RENDER
    # ======================================================

    return render_template(
        "vendedor_unico.html",

        usuario=usuario,

        tiendas=tiendas,

        store_id_actual=store_id,

        anio=anio,

        mes=mes,

        anio_actual=anio,

        mes_actual=mes,

        buscar=buscar,

        vendedores=vendedores,

        total_venta=total_venta,

        total_unidades=total_unidades,

        total_facturas=total_facturas,

        total_ticket=total_ticket,

        total_upt=total_upt,

        es_tienda=es_tienda
    )
    
@app_pages_bp.route("/ventas-por-dia")
def ventas_por_dia():
    usuario = verificar_acceso()
    anio_actual, mes_actual = obtener_periodo()
    periodos = obtener_periodos_ventas_diarias()

    if periodos and (not anio_actual or not mes_actual):
        anio_actual = periodos[0]["anio"]
        mes_actual = periodos[0]["mes"]

    anio_sel = request.args.get("anio", type=int) or anio_actual
    mes_sel = request.args.get("mes", type=int) or mes_actual
    dia_corte_sel, cortes_disponibles = obtener_dia_corte_actual(
        anio_sel,
        mes_sel,
    )

    es_tienda = es_usuario_tienda(usuario)
    store_id_sel = request.args.get("store_id", type=int)
    if es_tienda:
        store_id_sel = usuario.store_id

    tiendas_disponibles = (
        Store.query
        .order_by(Store.codigo.asc())
        .all()
    )
    ids_validos = {tienda.id for tienda in tiendas_disponibles}
    if store_id_sel not in ids_validos:
        store_id_sel = usuario.store_id if es_tienda else None

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
        "Diciembre",
    ]
    resumen_global = construir_resumen_global(
        anio_sel,
        mes_sel,
        dia_corte_sel,
    )
    resumen_tiendas = construir_resumen_tiendas(
        anio_sel,
        mes_sel,
        dia_corte_sel,
        usuario.store_id if es_tienda else None,
    )
    detalle_tienda = (
        construir_resumen_tiendas(
            anio_sel,
            mes_sel,
            dia_corte_sel,
            store_id_sel,
        )
        if store_id_sel is not None
        else None
    )

    return render_template(
        "ventas_por_dia.html",
        usuario=usuario,
        anio=anio_sel,
        mes=mes_sel,
        dia_corte=dia_corte_sel,
        cortes_disponibles=cortes_disponibles,
        periodos=periodos,
        meses=meses,
        es_tienda=es_tienda,
        store_id_actual=store_id_sel,
        tiendas_disponibles=tiendas_disponibles,
        datos=resumen_global,
        tiendas=resumen_tiendas,
        detalle_tienda=detalle_tienda,
    )


def _ventas_por_dia_clasica():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    anio_sel = request.args.get("anio", type=int) or anio
    mes_sel = request.args.get("mes", type=int) or mes

    DIAS_SEMANA_ES = {
        "LUNES": "Lunes",
        "MARTES": "Martes",
        "MIERCOLES": "Miércoles",
        "JUEVES": "Jueves",
        "VIERNES": "Viernes",
        "SABADO": "Sábado",
        "DOMINGO": "Domingo",
        "MONDAY": "Lunes",
        "TUESDAY": "Martes",
        "WEDNESDAY": "Miércoles",
        "THURSDAY": "Jueves",
        "FRIDAY": "Viernes",
        "SATURDAY": "Sábado",
        "SUNDAY": "Domingo",
    }

    # Obtener TODOS los registros del período (sin filtrar activo)
    registros_brutos = (
        DailySales.query
        .filter_by(anio=anio_sel, mes=mes_sel)
        .order_by(DailySales.dia.asc())
        .all()
    )

    # Agrupar por (anio, mes, dia) y elegir el de mayor dia_corte
    mejores_por_dia = {}
    for reg in registros_brutos:
        clave = (reg.anio, reg.mes, reg.dia)
        if clave not in mejores_por_dia or reg.dia_corte > mejores_por_dia[clave].dia_corte:
            mejores_por_dia[clave] = reg

    daily_records = list(mejores_por_dia.values())
    daily_records.sort(key=lambda r: r.dia)

    ventas_diarias = []
    total_venta_2025 = 0.0
    total_venta_2026 = 0.0
    total_diferencia = 0.0
    total_incremento = 0.0
    ventas_por_dia_semana = {}
    dias_con_2026 = []

    for reg in daily_records:
        venta_2025 = float(reg.venta_2025 or 0)
        venta_2026 = float(reg.venta_2026 or 0)

        dia_semana_2025 = DIAS_SEMANA_ES.get(reg.dia_semana_2025, reg.dia_semana_2025 or "")
        dia_semana_2026 = DIAS_SEMANA_ES.get(reg.dia_semana_2026, reg.dia_semana_2026 or "")

        # Si no hay venta 2026, marcar sin dato y no calcular incremento
        if venta_2026 == 0:
            item = {
                "dia": reg.dia,
                "venta_2025": venta_2025,
                "venta_2026": None,
                "diferencia": None,
                "incremento": None,
                "sin_dato_2026": True,
                "dia_semana_2025": dia_semana_2025,
                "dia_semana_2026": dia_semana_2026,
            }
            ventas_diarias.append(item)
            continue

        diferencia = venta_2026 - venta_2025
        incremento = (diferencia / venta_2025 * 100) if venta_2025 > 0 else 0.0

        total_venta_2025 += venta_2025
        total_venta_2026 += venta_2026
        total_diferencia += diferencia

        dia_semana = dia_semana_2026 if dia_semana_2026 else dia_semana_2025
        if dia_semana:
            if dia_semana not in ventas_por_dia_semana:
                ventas_por_dia_semana[dia_semana] = {"venta_2025": 0.0, "venta_2026": 0.0, "dias": 0}
            ventas_por_dia_semana[dia_semana]["venta_2025"] += venta_2025
            ventas_por_dia_semana[dia_semana]["venta_2026"] += venta_2026
            ventas_por_dia_semana[dia_semana]["dias"] += 1

        item = {
            "dia": reg.dia,
            "venta_2025": venta_2025,
            "venta_2026": venta_2026,
            "diferencia": diferencia,
            "incremento": incremento,
            "sin_dato_2026": False,
            "dia_semana_2025": dia_semana_2025,
            "dia_semana_2026": dia_semana_2026,
        }
        ventas_diarias.append(item)
        dias_con_2026.append(item)

    if total_venta_2025 > 0:
        total_incremento = (total_diferencia / total_venta_2025) * 100

    mejores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"], reverse=True)[:5]
    peores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"])[:5]

    # Ordenar días de semana
    orden_dias = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
    ventas_semana_ordenadas = []
    for dia in orden_dias:
        if dia in ventas_por_dia_semana:
            item = ventas_por_dia_semana[dia]
            ventas_semana_ordenadas.append({
                "dia": dia,
                "venta_2025": item["venta_2025"],
                "venta_2026": item["venta_2026"],
                "dias": item["dias"],
            })

    promedio_2025 = total_venta_2025 / len(ventas_diarias) if ventas_diarias else 0
    promedio_2026 = total_venta_2026 / len(ventas_diarias) if ventas_diarias else 0

    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    return render_template(
        "ventas_por_dia.html",
        usuario=usuario,
        anio=anio_sel,
        mes=mes_sel,
        es_tienda=es_usuario_tienda(usuario),
        meses=meses,
        datos={
            "ventas_diarias": ventas_diarias,
            "total_venta_2025": total_venta_2025,
            "total_venta_2026": total_venta_2026,
            "total_diferencia": total_diferencia,
            "total_incremento": total_incremento,
            "mejores_dias": mejores_dias,
            "peores_dias": peores_dias,
            "ventas_por_dia_semana": ventas_semana_ordenadas,
            "promedio_2025": promedio_2025,
            "promedio_2026": promedio_2026,
        },
    )
