from flask import Blueprint, render_template, request, session, abort
from sqlalchemy import func, or_

from app.extensions import db

from app.models.user import User
from app.models.store import Store
from app.models.compliance import Compliance
from app.models.archivo_importado import ArchivoImportado
from app.models import Advisor, AdvisorPerformance, DailySales

from app.services.advisor_goal_service import (
    calcular_metas_asesoras,
    obtener_meta_tienda
)


# ==========================================================
# UTILIDAD PARA EXCLUIR S-24 DESDE AGOSTO 2026
# ==========================================================

def debe_excluir_s24(anio, mes):
    """
    Devuelve True si la tienda S-24 debe excluirse.

    S-24 cerró en agosto 2026, por lo tanto, desde ese período
    en adelante ya no aparece en listados.
    """
    if anio is None or mes is None:
        return False
    return (anio, mes) >= (2026, 8)


# ==========================================================
# BLUEPRINT
# ==========================================================

app_pages_bp = Blueprint("app_pages", __name__)


# ==========================================================
# UTILIDADES GENERALES
# ==========================================================

def obtener_usuario_actual():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def obtener_rol_usuario(usuario):
    if not usuario:
        return None
    if not usuario.role:
        return None
    if not usuario.role.nombre:
        return None
    return str(usuario.role.nombre).upper().strip()


def es_usuario_tienda(usuario):
    return obtener_rol_usuario(usuario) == "TIENDA"


def es_usuario_admin(usuario):
    rol = obtener_rol_usuario(usuario)
    return rol in {"ADMIN", "ADMINISTRADOR"}


def verificar_acceso(roles_permitidos=None):
    usuario = obtener_usuario_actual()
    if not usuario:
        abort(401)
    rol = obtener_rol_usuario(usuario)
    if not rol:
        abort(403)
    if roles_permitidos is None:
        roles_permitidos = {"ADMIN", "ADMINISTRADOR", "TIENDA"}
    if rol not in roles_permitidos:
        abort(403)
    return usuario


# ==========================================================
# PERÍODO
# ==========================================================

def obtener_periodo():
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    if anio and mes:
        return anio, mes

    ultimo_anio = db.session.query(func.max(Compliance.anio)).scalar()
    if ultimo_anio is None:
        return None, None
    anio = int(ultimo_anio)
    ultimo_mes = db.session.query(func.max(Compliance.mes)).filter(Compliance.anio == anio).scalar()
    if ultimo_mes is None:
        return anio, None
    return anio, int(ultimo_mes)


def obtener_periodo_anterior(anio, mes):
    if not anio or not mes:
        return None, None
    if mes == 1:
        return anio - 1, 12
    return anio, mes - 1


# ==========================================================
# CORTES DISPONIBLES
# ==========================================================

def obtener_dias_corte(anio, mes):
    if not anio or not mes:
        return []
    resultados = (
        db.session.query(ArchivoImportado.dia_corte)
        .filter(ArchivoImportado.anio == anio, ArchivoImportado.mes == mes)
        .distinct()
        .order_by(ArchivoImportado.dia_corte.asc())
        .all()
    )
    dias = []
    for item in resultados:
        dia = item.dia_corte
        if dia is None:
            continue
        try:
            dia = int(dia)
        except (TypeError, ValueError):
            continue
        if dia <= 0:
            continue
        if dia not in dias:
            dias.append(dia)
    return dias


def obtener_dia_corte_actual(anio, mes):
    dias_corte = obtener_dias_corte(anio, mes)
    dia_corte_parametro = request.args.get("dia_corte", default=None, type=int)
    if not dias_corte:
        return None, []
    if dia_corte_parametro is None:
        return dias_corte[-1], dias_corte
    if dia_corte_parametro in dias_corte:
        return dia_corte_parametro, dias_corte
    return dias_corte[-1], dias_corte


# ==========================================================
# METAS DE ASESORAS
# ==========================================================

def obtener_metas_asesoras_por_tienda(store_id, anio, mes):
    metas = {}
    if not store_id or not anio or not mes:
        return metas
    try:
        meta_tienda = obtener_meta_tienda(store_id, anio, mes)
        resultado = calcular_metas_asesoras(store_id=store_id, anio=anio, mes=mes, meta_tienda=meta_tienda)
    except Exception:
        return metas
    if not resultado:
        return metas
    asesoras = resultado.get("asesoras", [])
    if not asesoras:
        return metas
    for asesora in asesoras:
        if not isinstance(asesora, dict):
            continue
        advisor_id = asesora.get("advisor_id") or asesora.get("asesor_id") or asesora.get("id")
        if advisor_id is None:
            continue
        try:
            advisor_id = int(advisor_id)
        except (TypeError, ValueError):
            continue
        meta = asesora.get("meta")
        if meta is None:
            meta = asesora.get("meta_asesora")
        if meta is None:
            meta = asesora.get("meta_individual")
        if meta is None:
            meta = asesora.get("meta_por_asesora")
        if meta is None:
            meta = asesora.get("cuota")
        if meta is None:
            meta = 0
        try:
            meta = float(meta or 0)
        except (TypeError, ValueError):
            meta = 0
        metas[advisor_id] = meta
    return metas


def obtener_metas_por_tiendas(store_ids, anio, mes):
    resultado = {}
    if not anio or not mes:
        return resultado
    for store_id in store_ids:
        if not store_id or store_id in resultado:
            continue
        resultado[store_id] = obtener_metas_asesoras_por_tienda(store_id, anio, mes)
    return resultado


# ==========================================================
# RANKING TIENDAS
# ==========================================================

@app_pages_bp.route("/ranking/tiendas")
def ranking_tiendas():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    busqueda = request.args.get("buscar", "", type=str).strip()
    es_tienda = es_usuario_tienda(usuario)

    query = (
        db.session.query(
            Store.id.label("store_id"),
            Store.codigo.label("codigo"),
            Store.nombre.label("nombre"),
            func.coalesce(func.sum(Compliance.venta_actual), 0).label("venta_actual"),
            func.coalesce(func.avg(Compliance.cumplimiento_pct), 0).label("cumplimiento_pct"),
        )
        .join(Compliance, Compliance.store_id == Store.id)
        .filter(Store.estado == "ACTIVA")
    )

    if anio is not None:
        query = query.filter(Compliance.anio == anio)
    if mes is not None:
        query = query.filter(Compliance.mes == mes)
    if busqueda:
        termino = f"%{busqueda}%"
        query = query.filter(or_(Store.nombre.ilike(termino), Store.codigo.ilike(termino)))
    # Aplicar exclusión S-24 desde agosto 2026
    if debe_excluir_s24(anio, mes):
        query = query.filter(Store.codigo != "S-24")

    resultados = (
        query.group_by(Store.id, Store.codigo, Store.nombre)
        .order_by(func.avg(Compliance.cumplimiento_pct).desc())
        .all()
    )

    ranking = []
    for posicion, item in enumerate(resultados, start=1):
        cumplimiento = float(item.cumplimiento_pct or 0)
        venta = float(item.venta_actual or 0) if not es_tienda else None
        ranking.append({
            "posicion": posicion,
            "store_id": item.store_id,
            "codigo": item.codigo,
            "nombre": item.nombre,
            "venta_actual": venta,
            "cumplimiento_pct": cumplimiento,
        })

    return render_template(
        "ranking/ranking_tiendas.html",
        usuario=usuario,
        ranking=ranking,
        anio=anio,
        mes=mes,
        busqueda=busqueda,
        es_tienda=es_tienda,
    )


# ==========================================================
# RANKING ASESORAS
# ==========================================================

@app_pages_bp.route("/ranking/asesoras")
def ranking_asesoras():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    dia_corte, dias_corte = obtener_dia_corte_actual(anio, mes)
    busqueda = request.args.get("buscar", "", type=str).strip()
    es_tienda = es_usuario_tienda(usuario)

    query = (
        db.session.query(
            Advisor.id.label("advisor_id"),
            Advisor.nombre.label("asesora"),
            Store.id.label("store_id"),
            Store.codigo.label("codigo_tienda"),
            Store.nombre.label("tienda"),
            func.coalesce(func.sum(AdvisorPerformance.venta), 0).label("venta"),
            func.coalesce(func.sum(AdvisorPerformance.unidades), 0).label("unidades"),
            func.coalesce(func.sum(AdvisorPerformance.facturas), 0).label("facturas"),
        )
        .join(AdvisorPerformance, Advisor.id == AdvisorPerformance.advisor_id)
        .join(Store, Store.id == AdvisorPerformance.store_id)
        .filter(AdvisorPerformance.activo == True, Store.estado == "ACTIVA")
    )
    if anio is not None:
        query = query.filter(AdvisorPerformance.anio == anio)
    if mes is not None:
        query = query.filter(AdvisorPerformance.mes == mes)
    if dia_corte is not None:
        query = query.filter(AdvisorPerformance.dia_corte == dia_corte)
    if busqueda:
        termino = f"%{busqueda}%"
        query = query.filter(or_(Advisor.nombre.ilike(termino), Store.nombre.ilike(termino), Store.codigo.ilike(termino)))
    # Excluir S-24 desde agosto 2026 en adelante
    if debe_excluir_s24(anio, mes):
        query = query.filter(Store.codigo != "S-24")

    resultados = (
        query.group_by(Advisor.id, Advisor.nombre, Store.id, Store.codigo, Store.nombre)
        .all()
    )

    store_ids = {item.store_id for item in resultados if item.store_id}
    metas_por_tienda = obtener_metas_por_tiendas(store_ids, anio, mes)

    ranking_sin_posicion = []
    for item in resultados:
        venta_real = float(item.venta or 0)
        unidades = float(item.unidades or 0)
        facturas = float(item.facturas or 0)
        ticket = (venta_real / facturas) if facturas > 0 else 0
        upt = (unidades / facturas) if facturas > 0 else 0

        metas_tienda = metas_por_tienda.get(item.store_id, {})
        meta_asesora = float(metas_tienda.get(item.advisor_id, 0) or 0)
        cumplimiento = (venta_real / meta_asesora) if meta_asesora > 0 else 0

        venta_mostrar = venta_real if not es_tienda else None
        ticket_mostrar = ticket if not es_tienda else None

        ranking_sin_posicion.append({
            "advisor_id": item.advisor_id,
            "asesora": item.asesora,
            "tienda": item.tienda,
            "codigo_tienda": item.codigo_tienda,
            "store_id": item.store_id,
            "venta": venta_mostrar,
            "venta_real": venta_real,
            "unidades": unidades,
            "facturas": facturas,
            "ticket": ticket_mostrar,
            "upt": upt,
            "meta": meta_asesora,
            "cumplimiento": cumplimiento,
        })

    ranking_sin_posicion.sort(key=lambda x: (x["cumplimiento"], x["venta_real"], x["facturas"]), reverse=True)

    ranking = []
    for posicion, item in enumerate(ranking_sin_posicion, start=1):
        item["posicion"] = posicion
        ranking.append(item)

    return render_template(
        "ranking/ranking_asesoras.html",
        usuario=usuario,
        ranking=ranking,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        dias_corte=dias_corte,
        busqueda=busqueda,
        es_tienda=es_tienda,
    )


# ==========================================================
# TIENDAS
# ==========================================================

@app_pages_bp.route("/tiendas")
def tiendas():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    es_tienda = es_usuario_tienda(usuario)

    tiendas_db = Store.query.filter(Store.estado == "ACTIVA").order_by(Store.codigo).all()
    if debe_excluir_s24(anio, mes):
        tiendas_db = [t for t in tiendas_db if t.codigo != "S-24"]

    anio_anterior, mes_anterior = obtener_periodo_anterior(anio, mes)

    posiciones_actuales = {}
    if anio and mes:
        ranking_actual = (
            db.session.query(Store.id.label("store_id"), func.avg(Compliance.cumplimiento_pct).label("cumplimiento"))
            .join(Compliance, Compliance.store_id == Store.id)
            .filter(Store.estado == "ACTIVA", Compliance.anio == anio, Compliance.mes == mes)
            .group_by(Store.id)
            .order_by(func.avg(Compliance.cumplimiento_pct).desc())
            .all()
        )
        for posicion, item in enumerate(ranking_actual, start=1):
            posiciones_actuales[item.store_id] = posicion

    posiciones_anteriores = {}
    if anio_anterior and mes_anterior:
        ranking_anterior = (
            db.session.query(Store.id.label("store_id"), func.avg(Compliance.cumplimiento_pct).label("cumplimiento"))
            .join(Compliance, Compliance.store_id == Store.id)
            .filter(Store.estado == "ACTIVA", Compliance.anio == anio_anterior, Compliance.mes == mes_anterior)
            .group_by(Store.id)
            .order_by(func.avg(Compliance.cumplimiento_pct).desc())
            .all()
        )
        for posicion, item in enumerate(ranking_anterior, start=1):
            posiciones_anteriores[item.store_id] = posicion

    tarjetas = []
    for tienda in tiendas_db:
        venta = 0
        venta_anterior = 0
        cumplimiento = 0
        compliance_actual = None
        compliance_anterior = None

        if anio and mes:
            compliance_actual = Compliance.query.filter_by(store_id=tienda.id, anio=anio, mes=mes).first()
            if compliance_actual:
                venta = float(compliance_actual.venta_actual or 0)
                cumplimiento = float(compliance_actual.cumplimiento_pct or 0)
                venta_anterior = float(compliance_actual.venta_anterior or 0)

        if anio_anterior and mes_anterior:
            compliance_anterior = Compliance.query.filter_by(store_id=tienda.id, anio=anio_anterior, mes=mes_anterior).first()
            if venta_anterior == 0 and compliance_anterior:
                venta_anterior = float(compliance_anterior.venta_actual or 0)

        variacion = ((venta - venta_anterior) / venta_anterior) if venta_anterior > 0 else 0
        cumplimiento_anterior = float(compliance_anterior.cumplimiento_pct or 0) if compliance_anterior else 0
        evolucion_cumplimiento = cumplimiento - cumplimiento_anterior
        evolucion_tipo = "subio" if evolucion_cumplimiento > 0 else ("bajo" if evolucion_cumplimiento < 0 else "igual")

        posicion_actual = posiciones_actuales.get(tienda.id)
        posicion_anterior = posiciones_anteriores.get(tienda.id)

        movimiento = 0
        movimiento_tipo = "igual"
        if posicion_actual is not None and posicion_anterior is not None:
            movimiento = posicion_anterior - posicion_actual
            if movimiento > 0:
                movimiento_tipo = "subio"
            elif movimiento < 0:
                movimiento_tipo = "bajo"

        if cumplimiento >= 1:
            estado, estado_clase = "Meta superada", "success"
        elif cumplimiento >= 0.9:
            estado, estado_clase = "Cerca de la meta", "warning"
        elif cumplimiento >= 0.8:
            estado, estado_clase = "En progreso", "info"
        else:
            estado, estado_clase = "Por debajo", "danger"

        imagen = f"{tienda.codigo.strip()}.jpeg" if tienda.codigo else None

        if es_tienda:
            venta_mostrar = None
            venta_anterior_mostrar = None
            variacion_mostrar = None
        else:
            venta_mostrar = venta
            venta_anterior_mostrar = venta_anterior
            variacion_mostrar = variacion

        tarjetas.append({
            "id": tienda.id,
            "codigo": tienda.codigo,
            "nombre": tienda.nombre,
            "imagen": imagen,
            "venta": venta_mostrar,
            "venta_anterior": venta_anterior_mostrar,
            "variacion": variacion_mostrar,
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
        })

    return render_template("admin/tiendas.html", usuario=usuario, tiendas=tarjetas, anio=anio, mes=mes, es_tienda=es_tienda)


# ==========================================================
# HISTORIAL DE IMPORTACIONES
# ==========================================================

@app_pages_bp.route("/importaciones/historial")
def historial_importaciones():
    usuario = verificar_acceso({"ADMIN", "ADMINISTRADOR"})
    return render_template("historial_importaciones.html", usuario=usuario)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

@app_pages_bp.route("/configuracion")
def configuracion():
    usuario = verificar_acceso()
    return render_template("configuracion.html", usuario=usuario)


# ==========================================================
# CUOTA / META POR TIENDA
# ==========================================================

@app_pages_bp.route("/metas/cuota-tienda")
def cuota_tienda():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    es_tienda = es_usuario_tienda(usuario)

    if es_tienda:
        if not usuario.store_id:
            abort(403)
        tiendas = Store.query.filter(Store.id == usuario.store_id, Store.estado == "ACTIVA").order_by(Store.codigo).all()
    else:
        tiendas = Store.query.filter(Store.estado == "ACTIVA").order_by(Store.codigo).all()
        if debe_excluir_s24(anio, mes):
            tiendas = [t for t in tiendas if t.codigo != "S-24"]

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

            datos = {
                "store_id": tienda.id,
                "codigo": tienda.codigo,
                "nombre": tienda.nombre,
                "meta_tienda": meta_tienda,
                "cantidad_asesoras": cantidad_asesoras,
                "meta_por_asesora": meta_por_asesora,
                "asesoras": resultado.get("asesoras", []),
            }

    return render_template(
        "metas/cuota_tienda.html",
        usuario=usuario,
        tiendas=tiendas,
        store_id_actual=store_id,
        anio=anio,
        mes=mes,
        datos=datos,
        es_tienda=es_tienda,
    )


# ==========================================================
# VENDEDOR ÚNICO
# ==========================================================

@app_pages_bp.route("/metas/vendedor-unico")
def vendedor_unico():
    usuario = verificar_acceso()
    es_tienda = es_usuario_tienda(usuario)
    anio, mes = obtener_periodo()
    store_id = request.args.get("store_id", type=int)
    buscar = request.args.get("buscar", "", type=str).strip()

    if es_tienda:
        if not usuario.store_id:
            abort(403)
        tiendas = Store.query.filter(Store.id == usuario.store_id, Store.estado == "ACTIVA").order_by(Store.codigo).all()
        store_id = usuario.store_id
    else:
        tiendas = Store.query.filter(Store.estado == "ACTIVA").order_by(Store.codigo).all()
        if debe_excluir_s24(anio, mes):
            tiendas = [t for t in tiendas if t.codigo != "S-24"]

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
            es_tienda=es_tienda,
        )

    query = (
        db.session.query(AdvisorPerformance, Advisor, Store)
        .join(Advisor, Advisor.id == AdvisorPerformance.advisor_id)
        .join(Store, Store.id == AdvisorPerformance.store_id)
        .filter(
            Advisor.nombre == "VENDEDOR UNICO",
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            Store.estado == "ACTIVA",
        )
    )
    if store_id:
        query = query.filter(AdvisorPerformance.store_id == store_id)
    if es_tienda:
        query = query.filter(AdvisorPerformance.store_id == usuario.store_id)
    if buscar:
        termino = f"%{buscar}%"
        query = query.filter(or_(Store.nombre.ilike(termino), Store.codigo.ilike(termino)))
    # Excluir S-24 desde agosto 2026
    if debe_excluir_s24(anio, mes):
        query = query.filter(Store.codigo != "S-24")

    registros = query.order_by(Store.codigo.asc()).all()

    vendedores = []
    for performance, advisor, tienda in registros:
        venta = float(performance.venta or 0)
        unidades = float(performance.unidades or 0)
        facturas = float(performance.facturas or 0)
        ticket = (venta / facturas) if facturas > 0 else 0
        upt = (unidades / facturas) if facturas > 0 else 0

        vendedores.append({
            "advisor_id": advisor.id,
            "nombre": advisor.nombre,
            "codigo_tienda": tienda.codigo,
            "tienda": tienda.nombre,
            "venta": venta,
            "unidades": unidades,
            "facturas": facturas,
            "ticket": ticket,
            "upt": upt,
            "activo": performance.activo,
        })

    total_venta = sum(v["venta"] for v in vendedores)
    total_unidades = sum(v["unidades"] for v in vendedores)
    total_facturas = sum(v["facturas"] for v in vendedores)
    total_ticket = (total_venta / total_facturas) if total_facturas > 0 else 0
    total_upt = (total_unidades / total_facturas) if total_facturas > 0 else 0

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
        es_tienda=es_tienda,
    )


# ==========================================================
# VENTAS POR DÍA (GLOBAL)
# ==========================================================

@app_pages_bp.route("/ventas-por-dia")
def ventas_por_dia():
    usuario = verificar_acceso()
    anio, mes = obtener_periodo()
    anio_sel = request.args.get("anio", type=int) or anio
    mes_sel = request.args.get("mes", type=int) or mes

    registros_brutos = (
        DailySales.query
        .filter_by(anio=anio_sel, mes=mes_sel)
        .order_by(DailySales.dia.asc())
        .all()
    )

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

        if venta_2026 == 0:
            item = {
                "dia": reg.dia,
                "venta_2025": venta_2025,
                "venta_2026": None,
                "diferencia": None,
                "incremento": None,
                "sin_dato_2026": True,
                "dia_semana_2025": reg.dia_semana_2025 or "",
                "dia_semana_2026": reg.dia_semana_2026 or "",
            }
            ventas_diarias.append(item)
            continue

        diferencia = venta_2026 - venta_2025
        incremento = (diferencia / venta_2025 * 100) if venta_2025 > 0 else 0.0

        total_venta_2025 += venta_2025
        total_venta_2026 += venta_2026
        total_diferencia += diferencia

        dia_semana = reg.dia_semana_2026 if reg.dia_semana_2026 else reg.dia_semana_2025
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
            "dia_semana_2025": reg.dia_semana_2025 or "",
            "dia_semana_2026": reg.dia_semana_2026 or "",
        }
        ventas_diarias.append(item)
        dias_con_2026.append(item)

    if total_venta_2025 > 0:
        total_incremento = (total_diferencia / total_venta_2025) * 100

    mejores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"], reverse=True)[:5]
    peores_dias = sorted(dias_con_2026, key=lambda x: x["incremento"])[:5]

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