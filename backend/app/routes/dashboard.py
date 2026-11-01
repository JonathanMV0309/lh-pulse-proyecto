from app.utils.logs import log_debug
from datetime import datetime

from flask import Blueprint, render_template, request, session

from app.extensions import db
from app.models.user import User
from app.models.store import Store
from app.models import AdvisorPerformance

from app.services.dashboard_service import (
    obtener_dashboard_admin,
    obtener_dashboard_supervisora,
    obtener_dashboard_tienda,
    obtener_dashboard_tienda_por_id,
    obtener_periodos_disponibles,
)
from flask import send_file
from app.services.store_report_service import generar_informe_visita_tienda_excel   


dashboard_bp = Blueprint("dashboard", __name__)


# ======================================================
# ROLES
# ======================================================

ROLES_ADMIN = {"ADMIN", "ADMINISTRADOR"}
ROLES_SUPERVISORA = {"SUPERVISORA", "SUPERVISOR"}
ROLES_TIENDA = {"TIENDA"}


# ======================================================
# FUNCIÓN AUXILIAR DE SERIALIZACIÓN
# ======================================================

def _serializar_ranking_tiendas(lista):
    """
    Convierte las tuplas devueltas por las consultas de ranking
    en diccionarios con las claves que espera el template.
    Ahora incluye el código de tienda.
    """
    resultado = []
    for item in lista:
        # El orden esperado: compliance, codigo, nombre, venta, cumplimiento
        compliance, codigo, nombre, venta, cumplimiento = item
        resultado.append({
            "codigo": codigo,
            "nombre": nombre,
            "venta_actual": float(venta or 0),
            "cumplimiento_pct": float(cumplimiento or 0),
        })
    return resultado


# ======================================================
# DASHBOARD PRINCIPAL
# ======================================================

@dashboard_bp.route("/dashboard")
def dashboard():

    # ======================================================
    # VALIDAR SESIÓN
    # ======================================================

    if "user_id" not in session:
        return "NO HAY SESION", 401

    usuario = User.query.get(
        session["user_id"]
    )

    if not usuario:
        return "USUARIO NO EXISTE", 404

    # ======================================================
    # ROL
    # ======================================================

    rol = (
        usuario.role.nombre
        .upper()
        .strip()
    )

    log_debug("========================================")
    log_debug("DEBUG DASHBOARD")
    log_debug("Usuario:", usuario.nombre)
    log_debug("Role:", usuario.role.nombre)
    log_debug("Rol normalizado:", rol)
    log_debug("Store ID:", usuario.store_id)
    log_debug("========================================")

    # ======================================================
    # ADMINISTRADOR
    # ======================================================

    if rol in ROLES_ADMIN:

        # ==================================================
        # FILTROS
        # ==================================================

        anio = request.args.get(
            "anio",
            type=int
        )

        mes = request.args.get(
            "mes",
            type=int
        )

        dia_corte = request.args.get(
            "dia_corte",
            type=int
        )

        log_debug("========================================")
        log_debug("FILTRO DASHBOARD")
        log_debug("Año solicitado:", anio)
        log_debug("Mes solicitado:", mes)
        log_debug("Día/Corte solicitado:", dia_corte)
        log_debug("========================================")

        # ==================================================
        # OBTENER DASHBOARD
        # ==================================================

        datos = obtener_dashboard_admin(

            anio=anio,

            mes=mes,

            dia_corte=dia_corte
        )

        # ==================================================
        # PERÍODO REAL UTILIZADO
        # ==================================================

        anio_actual = datos.get(
            "periodo_anio"
        )

        mes_actual = datos.get(
            "periodo_mes"
        )

        dia_corte_actual = datos.get(
            "dia_corte"
        )

        log_debug("========================================")
        log_debug("PERIODO UTILIZADO")
        log_debug("Año:", anio_actual)
        log_debug("Mes:", mes_actual)
        log_debug("Día/Corte:", dia_corte_actual)
        log_debug("========================================")

        # ==================================================
        # NOMBRE MES
        # ==================================================

        nombres_meses = [
            "Enero",
            "Febrero",
            "Marzo",
            "Abril",
            "Mayo",
            "Junio",
            "Julio",
            "Agosto",
            "Septiembre",
            "Octubre",
            "Noviembre",
            "Diciembre"
        ]

        if (
            mes_actual
            and 1 <= mes_actual <= 12
        ):

            datos["mes_nombre"] = (
                nombres_meses[
                    mes_actual - 1
                ]
            )

        else:

            datos["mes_nombre"] = ""

        # ==================================================
        # SERIALIZAR TOP VENTAS
        # ==================================================

        datos["top_ventas"] = _serializar_ranking_tiendas(
            datos.get("top_ventas", [])
        )

        # ==================================================
        # SERIALIZAR TOP CUMPLIMIENTO
        # ==================================================

        datos["top_cumplimiento"] = _serializar_ranking_tiendas(
            datos.get("top_cumplimiento", [])
        )

        # ==================================================
        # SERIALIZAR RANKING COMPLETO
        # ==================================================

        datos["ranking_completo"] = _serializar_ranking_tiendas(
            datos.get("ranking_completo", [])
        )

        # ==================================================
        # RANKING ASESORAS
        #
        # CORRECCIÓN: Usar los datos de asesoras que ya
        # vienen calculados desde obtener_dashboard_admin.
        # ==================================================

        datos["top_asesoras"] = datos.get(
            "top_asesoras_global",
            []
        )

        # Los totales y KPIs de asesoras ya vienen en datos,
        # no es necesario recalcularlos aquí.

        # ==================================================
        # TIENDAS DISPONIBLES
        # ==================================================

        tiendas_disponibles = (
            Store.query
            .filter(
                Store.estado == "ACTIVA"
            )
            .order_by(
                Store.codigo
            )
            .all()
        )

        datos["tiendas_disponibles"] = (
            tiendas_disponibles
        )

        datos["store_id_actual"] = None

        # ==================================================
        # USUARIO
        # ==================================================

        datos["usuario"] = usuario

        # ==================================================
        # FECHA
        # ==================================================

        datos["fecha_actual"] = (
            datetime.now().strftime(
                "%B %Y"
            )
        )

        # ==================================================
        # FILTROS SELECCIONADOS
        # ==================================================

        datos["anio_seleccionado"] = (

            anio
            if anio is not None
            else anio_actual
        )

        datos["mes_seleccionado"] = (

            mes
            if mes is not None
            else mes_actual
        )

        datos["dia_corte_seleccionado"] = (

            dia_corte
            if dia_corte is not None
            else dia_corte_actual
        )

        datos["dia_corte"] = (
            datos["dia_corte_seleccionado"]
        )

        # ==================================================
        # PERÍODOS DISPONIBLES
        # ==================================================

        # CORRECCIÓN: no pasar 'datos' como argumento
        datos["periodos_disponibles"] = (
            obtener_periodos_disponibles()
        )

        # ==================================================
        # DEBUG
        # ==================================================

        log_debug("========================================")
        log_debug("PERIODOS DISPONIBLES")
        log_debug(
            datos["periodos_disponibles"]
        )
        log_debug("========================================")

        log_debug("========================================")
        log_debug("DEBUG FILTRO FINAL")
        log_debug("Año:", datos["anio_seleccionado"])
        log_debug("Mes:", datos["mes_seleccionado"])
        log_debug(
            "Día/Corte:",
            datos["dia_corte_seleccionado"]
        )
        log_debug("========================================")

        log_debug("========================================")
        log_debug("DEBUG ASESORAS")
        log_debug("Año:", anio_actual)
        log_debug("Mes:", mes_actual)
        log_debug(
            "Día/Corte:",
            dia_corte_actual
        )
        log_debug(
            "Ranking:",
            len(datos["top_asesoras"])
        )
        log_debug(
            "Total asesoras:",
            datos.get("total_asesoras")
        )
        log_debug(
            "Venta asesoras:",
            datos.get("venta_asesoras")
        )
        log_debug(
            "Facturas:",
            datos.get("facturas_asesoras")
        )
        log_debug(
            "UPT:",
            datos.get("upt_asesoras")
        )
        log_debug("========================================")

        # ==================================================
        # DEBUG BASE DE DATOS
        # ==================================================

        try:

            total_registros = (
                AdvisorPerformance.query.count()
            )

            registros_activos = (
                AdvisorPerformance.query
                .filter(
                    AdvisorPerformance.activo.is_(True)
                )
                .count()
            )

            registros_periodo = (
                AdvisorPerformance.query
                .filter(
                    AdvisorPerformance.activo.is_(True),
                    AdvisorPerformance.anio == anio_actual,
                    AdvisorPerformance.mes == mes_actual
                )
                .count()
            )

            query_corte = (
                AdvisorPerformance.query
                .filter(
                    AdvisorPerformance.activo.is_(True),
                    AdvisorPerformance.anio == anio_actual,
                    AdvisorPerformance.mes == mes_actual
                )
            )

            if dia_corte_actual is not None:

                query_corte = query_corte.filter(
                    AdvisorPerformance.dia_corte
                    == dia_corte_actual
                )

            registros_corte = (
                query_corte.count()
            )

            log_debug("========================================")
            log_debug("DEBUG ADVISOR PERFORMANCE")
            log_debug(
                "TOTAL:",
                total_registros
            )
            log_debug(
                "ACTIVOS:",
                registros_activos
            )
            log_debug(
                "PERIODO:",
                registros_periodo
            )
            log_debug(
                "CORTE:",
                registros_corte
            )
            log_debug("========================================")

        except Exception as e:

            print(
                "ERROR DEBUG "
                "ADVISOR PERFORMANCE:",
                e
            )

        # ==================================================
        # RENDER
        # ==================================================

        # Vista del administrador. La vista clásica se retiró; dashboard_v2.html
        # extiende dashboard.html, por eso ese archivo se conserva.
        template_dashboard = "dashboard_admin_v2/dashboard_v2.html"

        return render_template(
            template_dashboard,
            **datos
        )

    # ======================================================
    # SUPERVISORA
    # ======================================================

    elif rol in ROLES_SUPERVISORA:

        # --------------------------------------------------
        # FILTROS
        # --------------------------------------------------

        anio = request.args.get(
            "anio",
            type=int
        )

        mes = request.args.get(
            "mes",
            type=int
        )

        dia_corte = request.args.get(
            "dia_corte",
            type=int
        )

        datos = (
            obtener_dashboard_supervisora(

                usuario,

                anio=anio,

                mes=mes,

                dia_corte=dia_corte
            )
        )

        datos["usuario"] = usuario

        datos["fecha_actual"] = (
            datetime.now().strftime(
                "%B %Y"
            )
        )

        return render_template(
            "dashboard_supervisora.html",
            **datos
        )

    # ======================================================
    # TIENDA
    # ======================================================

    elif rol in ROLES_TIENDA:

        log_debug(
            "ENTRANDO DASHBOARD TIENDA"
        )

        # --------------------------------------------------
        # FILTROS
        # --------------------------------------------------

        anio = request.args.get(
            "anio",
            type=int
        )

        mes = request.args.get(
            "mes",
            type=int
        )

        dia_corte = request.args.get(
            "dia_corte",
            type=int
        )

        log_debug("========================================")
        log_debug("FILTRO DASHBOARD TIENDA")
        log_debug("Año:", anio)
        log_debug("Mes:", mes)
        log_debug("Día/Corte:", dia_corte)
        log_debug("========================================")

        datos = (
            obtener_dashboard_tienda(

                usuario,

                anio=anio,

                mes=mes,

                dia_corte=dia_corte
            )
        )

        datos["usuario"] = usuario

        datos["fecha_actual"] = (
            datetime.now().strftime(
                "%B %Y"
            )
        )

        return render_template(
            "dashboard_tienda.html",
            **datos
        )

    # ======================================================
    # ROL NO CONFIGURADO
    # ======================================================

    else:

        log_debug(
            "ROL SIN DASHBOARD:",
            rol
        )

        return (
            "Rol sin dashboard configurado",
            403
        )


# ==========================================================
# RUTA PARA VER DASHBOARD DE TIENDA INDIVIDUAL (ADMIN)
# ==========================================================

@dashboard_bp.route("/dashboard/tienda/<int:store_id>")
def dashboard_tienda_admin(store_id):

    # Validar sesión y rol admin
    if "user_id" not in session:
        return "NO HAY SESION", 401

    usuario = User.query.get(session["user_id"])
    if not usuario:
        return "USUARIO NO EXISTE", 404

    rol = usuario.role.nombre.upper().strip()
    if rol not in ROLES_ADMIN:
        return "ACCESO NO AUTORIZADO", 403

    # Filtros opcionales
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    dia_corte = request.args.get("dia_corte", type=int)

    datos = obtener_dashboard_tienda_por_id(
        store_id,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte
    )

    datos["usuario"] = usuario
    datos["fecha_actual"] = datetime.now().strftime("%B %Y")

    # ======================================================
    # VARIABLES PARA MODO ADMIN
    # ======================================================
    datos["modo_admin"] = True
    datos["store_id_actual"] = store_id

    tiendas_disponibles = (
        Store.query
        .filter(Store.estado == "ACTIVA")
        .order_by(Store.codigo)
        .all()
    )
    datos["tiendas_disponibles"] = tiendas_disponibles

    # Asegurar que existan los campos de filtro
    datos["anio_seleccionado"] = anio if anio is not None else datos.get("anio")
    datos["mes_seleccionado"] = mes if mes is not None else datos.get("mes")
    datos["dia_corte_seleccionado"] = dia_corte if dia_corte is not None else datos.get("dia_corte")

    return render_template(
        "dashboard_tienda.html",
        **datos
    )



@dashboard_bp.route("/dashboard/tienda/<int:store_id>/informe-excel")
def generar_informe_tienda_excel_route(store_id):
    # Validar sesión y rol admin
    if "user_id" not in session:
        return "NO HAY SESION", 401
    usuario = User.query.get(session["user_id"])
    if not usuario:
        return "USUARIO NO EXISTE", 404
    rol = usuario.role.nombre.upper().strip()
    if rol not in ROLES_ADMIN:
        return "ACCESO NO AUTORIZADO", 403

    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    dia_corte = request.args.get("dia_corte", type=int)

    if not all([anio, mes, dia_corte]):
        return "Faltan parámetros", 400

    try:
        output = generar_informe_visita_tienda_excel(store_id, anio, mes, dia_corte)
    except Exception as e:
        print(f"Error generando Excel: {e}")
        return "Error generando informe", 500

    tienda = db.session.get(Store, store_id)
    codigo = tienda.codigo if tienda else f"T{store_id}"
    nombre_mes = [
        "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
        "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
    ][mes-1] if 1 <= mes <= 12 else f"MES{mes}"

    filename = f"INFORME_GESTION_{codigo}_{nombre_mes}_{anio}_CORTE{dia_corte}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )