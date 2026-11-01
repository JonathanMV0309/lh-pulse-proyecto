from calendar import monthrange

from flask import Blueprint, abort, render_template, request, session
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Advisor, AdvisorPerformance
from app.models.compliance import Compliance
from app.models.store import Store
from app.models.user import User
from app.services.advisor_goal_service import calcular_metas_asesoras, obtener_meta_tienda


ranking_desempeno_bp = Blueprint(
    "ranking_desempeno",
    __name__,
    url_prefix="/ranking/desempeno",
)

ROLES = {"ADMIN", "ADMINISTRADOR", "TIENDA"}

ESTADO_TIENDA_ACTIVA = "ACTIVA"

# El Excel de cumplimiento trae una fila de totales de la red que no es una tienda.
NOMBRE_FILA_TOTAL = "TOTAL"
CODIGO_FILA_TOTAL = "TOTA"

# La tienda S-24 dejó de participar en el ranking desde agosto de 2026.
CODIGO_TIENDA_RETIRADA = "S-24"
PERIODO_RETIRO_TIENDA = (2026, 8)


def _filtros_tiendas_de_la_red():
    """Condiciones de una tienda real y activa de la red (excluye la fila de totales)."""
    return (
        Store.estado == ESTADO_TIENDA_ACTIVA,
        Store.nombre != NOMBRE_FILA_TOTAL,
        Store.codigo != CODIGO_FILA_TOTAL,
    )


def _usuario_actual():
    usuario = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not usuario:
        abort(401)
    rol = usuario.role.nombre.strip().upper() if usuario.role and usuario.role.nombre else ""
    if not usuario.activo or rol not in ROLES:
        abort(403)
    return usuario, rol


def _periodos_disponibles():
    periodos = {
        (int(anio), int(mes))
        for anio, mes in db.session.query(Compliance.anio, Compliance.mes).distinct().all()
        if anio and mes
    }
    periodos.update({
        (int(anio), int(mes))
        for anio, mes in db.session.query(
            AdvisorPerformance.anio,
            AdvisorPerformance.mes,
        ).distinct().all()
        if anio and mes
    })
    return sorted(periodos, reverse=True)


def _resolver_periodo(periodos):
    anio = request.args.get("anio", type=int)
    mes = request.args.get("mes", type=int)
    if (anio, mes) in periodos:
        return anio, mes
    return periodos[0] if periodos else (None, None)


def _resolver_corte(anio, mes):
    if not anio or not mes:
        return None, []
    cortes = {
        int(valor)
        for (valor,) in db.session.query(Compliance.dia_corte).filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.dia_corte.isnot(None),
        ).distinct().all()
        if valor is not None
    }
    cortes.update({
        int(valor)
        for (valor,) in db.session.query(AdvisorPerformance.dia_corte).filter(
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.dia_corte.isnot(None),
        ).distinct().all()
        if valor is not None
    })
    cortes = sorted(cortes)
    solicitado = request.args.get("dia_corte", type=int)
    return (solicitado if solicitado in cortes else (cortes[-1] if cortes else None)), cortes


def _metas_por_tienda(store_ids, anio, mes):
    resultado = {}
    for store_id in store_ids:
        try:
            meta_tienda = obtener_meta_tienda(store_id, anio, mes)
            distribucion = calcular_metas_asesoras(
                store_id=store_id,
                anio=anio,
                mes=mes,
                meta_tienda=meta_tienda,
            ) or {}
            resultado[store_id] = {
                int(item.get("advisor_id") or item.get("asesor_id") or item.get("id")): float(
                    item.get("meta") or item.get("meta_venta") or item.get("valor_meta") or 0
                )
                for item in distribucion.get("asesoras", [])
                if item.get("advisor_id") or item.get("asesor_id") or item.get("id")
            }
        except Exception:
            resultado[store_id] = {}
    return resultado


def _ranking_tiendas(anio, mes, dia_corte, buscar):
    if not all((anio, mes, dia_corte is not None)):
        return []
    ultima_version = (
        db.session.query(
            Compliance.store_id.label("store_id"),
            func.max(Compliance.id).label("max_id"),
        )
        .filter(
            Compliance.anio == anio,
            Compliance.mes == mes,
            Compliance.dia_corte == dia_corte,
        )
        .group_by(Compliance.store_id)
        .subquery()
    )
    query = (
        db.session.query(Compliance, Store)
        .join(ultima_version, Compliance.id == ultima_version.c.max_id)
        .join(Store, Store.id == Compliance.store_id)
        .filter(*_filtros_tiendas_de_la_red())
    )
    if (anio, mes) >= PERIODO_RETIRO_TIENDA:
        query = query.filter(Store.codigo != CODIGO_TIENDA_RETIRADA)
    if buscar:
        termino = f"%{buscar}%"
        query = query.filter(or_(Store.nombre.ilike(termino), Store.codigo.ilike(termino)))
    filas = query.order_by(Compliance.cumplimiento_pct.desc(), Compliance.venta_actual.desc()).all()
    return [
        {
            "posicion": posicion,
            "store_id": tienda.id,
            "codigo": tienda.codigo,
            "nombre": tienda.nombre,
            "venta": float(registro.venta_actual or 0),
            "venta_anterior": float(registro.venta_anterior or 0),
            "cumplimiento": float(registro.cumplimiento_pct or 0),
            "crecimiento": float(registro.incremento or 0),
            "facturas": int(registro.facturas or 0),
            "ticket": float(registro.ticket_promedio or 0),
            # Meta al corte derivada de venta y cumplimiento; sin cumplimiento no se puede estimar.
            "meta_corte": float(registro.venta_actual or 0) / float(registro.cumplimiento_pct) if (registro.cumplimiento_pct or 0) > 0 else 0,
            "sin_meta": not (registro.cumplimiento_pct or 0) > 0,
        }
        for posicion, (registro, tienda) in enumerate(filas, start=1)
    ]


def _consultar_desempeno_asesoras(anio, mes, dia_corte, buscar, store_id):
    """Última versión cargada del desempeño de cada asesora en el corte (solo tiendas activas)."""
    ultima_version = (
        db.session.query(
            AdvisorPerformance.advisor_id.label("advisor_id"),
            AdvisorPerformance.store_id.label("store_id"),
            func.max(AdvisorPerformance.id).label("max_id"),
        )
        .filter(
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.dia_corte == dia_corte,
        )
        .group_by(AdvisorPerformance.advisor_id, AdvisorPerformance.store_id)
        .subquery()
    )
    query = (
        db.session.query(AdvisorPerformance, Advisor, Store)
        .join(ultima_version, AdvisorPerformance.id == ultima_version.c.max_id)
        .join(Advisor, Advisor.id == AdvisorPerformance.advisor_id)
        .join(Store, Store.id == AdvisorPerformance.store_id)
        .filter(Store.estado == ESTADO_TIENDA_ACTIVA)
    )
    if store_id:
        query = query.filter(Store.id == store_id)
    if buscar:
        termino = f"%{buscar}%"
        query = query.filter(or_(
            Advisor.nombre.ilike(termino),
            Store.nombre.ilike(termino),
            Store.codigo.ilike(termino),
        ))
    return query.all()


def _indicadores_asesora(venta, facturas, unidades, meta_total, meta_corte):
    """Ticket, UPT y cumplimiento de una asesora. Cálculo puro: no consulta la base."""
    return {
        "venta": venta,
        "unidades": unidades,
        "facturas": facturas,
        "ticket": venta / facturas if facturas > 0 else 0,
        "upt": unidades / facturas if facturas > 0 else 0,
        "meta": meta_total,
        "meta_corte": meta_corte,
        "cumplimiento": venta / meta_corte if meta_corte > 0 else 0,
        "sin_meta": meta_corte <= 0,
    }


def _asignar_posiciones(resultado):
    """Ordena por cumplimiento y numera. Las asesoras sin meta van al final y sin puesto:
    no se puede medir su cumplimiento."""
    resultado.sort(key=lambda item: (not item["sin_meta"], item["cumplimiento"], item["venta"], item["facturas"]), reverse=True)
    posicion = 0
    for item in resultado:
        if item["sin_meta"]:
            item["posicion"] = None
        else:
            posicion += 1
            item["posicion"] = posicion
    return resultado


def _ranking_asesoras(anio, mes, dia_corte, buscar, store_id):
    if not all((anio, mes, dia_corte is not None)):
        return []
    filas = _consultar_desempeno_asesoras(anio, mes, dia_corte, buscar, store_id)
    metas = _metas_por_tienda({tienda.id for _, _, tienda in filas}, anio, mes)
    dias_mes = monthrange(anio, mes)[1]
    # Novedades de Talento Humano: los días que no estuvo en la tienda no cuentan
    from app.services.novedades_metas import ajustes as ajustes_novedades, aplicar as aplicar_novedad
    ajustes = ajustes_novedades({(tienda.id, asesora.id) for _, asesora, tienda in filas}, anio, mes, dia_corte)
    resultado = []
    for registro, asesora, tienda in filas:
        ajuste = ajustes.get((tienda.id, asesora.id))
        meta_total, meta_corte = aplicar_novedad(float(metas.get(tienda.id, {}).get(asesora.id, 0) or 0), ajuste, dia_corte, dias_mes)
        resultado.append({
            "advisor_id": asesora.id,
            "asesora": asesora.nombre,
            "store_id": tienda.id,
            "codigo_tienda": tienda.codigo,
            "tienda": tienda.nombre,
            **_indicadores_asesora(
                venta=float(registro.venta or 0),
                facturas=float(registro.facturas or 0),
                unidades=float(registro.unidades or 0),
                meta_total=meta_total,
                meta_corte=meta_corte,
            ),
            "novedades": ajuste["etiquetas"] if ajuste else [],
        })
    return _asignar_posiciones(resultado)


@ranking_desempeno_bp.get("/")
def index():
    usuario, rol = _usuario_actual()
    periodos = _periodos_disponibles()
    anio, mes = _resolver_periodo(periodos)
    dia_corte, cortes = _resolver_corte(anio, mes)
    buscar = (request.args.get("buscar") or "").strip()
    store_id = request.args.get("store_id", type=int)
    tiendas_disponibles = Store.query.filter(*_filtros_tiendas_de_la_red()).order_by(Store.codigo).all()
    ids_validos = {tienda.id for tienda in tiendas_disponibles}
    if store_id not in ids_validos:
        store_id = None

    tiendas = _ranking_tiendas(anio, mes, dia_corte, buscar)
    asesoras = _ranking_asesoras(anio, mes, dia_corte, buscar, store_id)
    es_tienda = rol == "TIENDA"
    return render_template(
        "ranking/desempeno.html",
        usuario=usuario,
        ranking_tiendas=tiendas,
        ranking_asesoras=asesoras,
        periodos=periodos,
        anio=anio,
        mes=mes,
        dia_corte=dia_corte,
        dias_corte=cortes,
        buscar=buscar,
        store_id=store_id,
        tiendas_disponibles=tiendas_disponibles,
        es_tienda=es_tienda,
        mi_store_id=usuario.store_id if es_tienda else None,
    )
